"""Lembretes locais e SMTP com deduplicação persistente e horário do dispositivo."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
import base64
import os
from pathlib import Path
import re
import smtplib
import ssl
import subprocess
import sys
import threading
from xml.sax.saxutils import escape

ALLOWED_DAYS = [0, 1, 2, 3, 7]
TASK_NAME = 'DoceAtelie-Lembretes'
EMAIL = re.compile(r'^[^\s<>@,;\r\n]+@[^\s<>@,;\r\n]+\.[^\s<>@,;\r\n]+$')


def validate_settings(values):
    result = dict(values)
    days = result.get('alert_days', [3, 2])
    if not isinstance(days, list) or not days or any(type(d) is not int or d not in ALLOWED_DAYS for d in days):
        raise ValueError('Escolha pelo menos uma antecedência para os alertas.')
    result['alert_days'] = sorted(set(days), reverse=True)
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', result.get('alert_time', '')):
        raise ValueError('Informe um horário válido para os avisos.')
    recipient = result.get('notification_email', '').strip()
    if recipient and not EMAIL.fullmatch(recipient):
        raise ValueError('Informe um e-mail válido para receber as notificações.')
    result['notification_email'] = recipient
    if result.get('email_enabled'):
        if not recipient or not EMAIL.fullmatch(result.get('smtp_sender', '').strip()):
            raise ValueError('Preencha o e-mail de notificação e o e-mail do remetente.')
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?', result.get('smtp_host', '')):
            raise ValueError('Informe o servidor SMTP, sem https:// nem espaços.')
        if type(result.get('smtp_port')) is not int or not 1 <= result['smtp_port'] <= 65535 or result.get('smtp_security') not in ('SSL/TLS', 'STARTTLS'):
            raise ValueError('Confira a porta e a segurança do serviço de e-mail.')
        if not result.get('smtp_username', '').strip() or any(c in result['smtp_username'] for c in '\r\n'):
            raise ValueError('Informe o usuário do serviço de e-mail.')
    return result


@dataclass(frozen=True)
class Reminder:
    key: str
    quote_id: int
    title: str
    text: str
    due_at: datetime


def due_reminders(quotes, settings, now=None):
    now = now or datetime.now()
    if not settings.get('reminders_enabled'):
        return []
    hour, minute = map(int, settings.get('alert_time', '09:00').split(':'))
    result = []
    for q in quotes:
        if q.get('delivered') or 'Data Reservada' not in q.get('status', ''):
            continue
        event = datetime.fromisoformat(q['event_at'])
        if event <= now:
            continue
        times = [(datetime.combine(event.date() - timedelta(days=d), datetime.min.time()).replace(hour=hour, minute=minute), d) for d in settings.get('alert_days', [3, 2])]
        elapsed = [(at, d) for at, d in times if at <= now]
        if not elapsed:
            continue
        # Recuperar somente o aviso mais recente; não disparar todos os dias perdidos.
        due, days = max(elapsed)
        text = f"Encomenda #{q['id']:04d} · {q['customer']['name']}\nSaída: {event:%d/%m/%Y às %H:%M}.\nConfira os detalhes e a ficha de produção no sistema."
        key = f"{q['id']}|{event.isoformat()}|{days}"
        result.append(Reminder(key, q['id'], settings['name'] + ' · Lembrete de encomenda', text, due))
    return result


class Ledger:
    def __init__(self, store):
        self.store = store
        with store.db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS reminder_deliveries (
                reminder_key TEXT NOT NULL, channel TEXT NOT NULL, sent_at TEXT,
                lease_until TEXT NOT NULL DEFAULT '', next_try TEXT NOT NULL DEFAULT '',
                error TEXT NOT NULL DEFAULT '', PRIMARY KEY(reminder_key,channel))''')

    def claim(self, key, channel, now):
        stamp = now.isoformat()
        with self.store.db() as db:
            db.execute('INSERT OR IGNORE INTO reminder_deliveries(reminder_key,channel) VALUES(?,?)', (key, channel))
            return db.execute('''UPDATE reminder_deliveries SET lease_until=? WHERE reminder_key=? AND channel=?
                AND sent_at IS NULL AND lease_until<=? AND next_try<=?''', ((now + timedelta(minutes=5)).isoformat(), key, channel, stamp, stamp)).rowcount == 1

    def finish(self, key, channel, now, error=''):
        with self.store.db() as db:
            db.execute('''UPDATE reminder_deliveries SET sent_at=?,lease_until='',next_try=?,error=? WHERE reminder_key=? AND channel=?''',
                       (None if error else now.isoformat(), (now + timedelta(minutes=15)).isoformat() if error else '', error, key, channel))

    def status(self):
        with self.store.db() as db:
            return [dict(row) for row in db.execute('SELECT channel,sent_at,error FROM reminder_deliveries ORDER BY rowid DESC LIMIT 10')]


def _dpapi(raw, decrypt=False):
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ValueError('Não foi possível acessar a senha protegida neste usuário do Windows.')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.WinDLL('kernel32').LocalFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(target.data, ctypes.c_void_p))


def save_password(store, password):
    if not password:
        return
    if sys.platform != 'win32':
        raise ValueError('Neste servidor, configure DOCE_SMTP_PASSWORD no ambiente. A senha não é gravada no banco.')
    encrypted = _dpapi(password.encode('utf-8'))
    path = store.data_dir / '.smtp-password'
    temp = path.with_suffix('.tmp')
    temp.write_bytes(encrypted)
    temp.replace(path)


def get_password(store):
    if os.environ.get('DOCE_SMTP_PASSWORD'):
        return os.environ['DOCE_SMTP_PASSWORD']
    path = store.data_dir / '.smtp-password'
    if sys.platform == 'win32' and path.is_file():
        return _dpapi(path.read_bytes(), decrypt=True).decode('utf-8')
    return ''


def send_email(settings, password, title, text):
    if not password:
        raise ValueError('Cadastre a senha de aplicativo do serviço de e-mail.')
    validate_settings({**settings, 'email_enabled': True})
    message = EmailMessage()
    message['From'] = settings['smtp_sender'].strip()
    message['To'] = settings['notification_email'].strip()
    message['Subject'] = title.replace('\r', ' ').replace('\n', ' ')
    message.set_content(text)
    context = ssl.create_default_context()
    if settings['smtp_security'] == 'SSL/TLS':
        connection = smtplib.SMTP_SSL(settings['smtp_host'], settings['smtp_port'], timeout=20, context=context)
    else:
        connection = smtplib.SMTP(settings['smtp_host'], settings['smtp_port'], timeout=20)
    smtp = connection
    try:
        smtp.ehlo()
        if settings['smtp_security'] == 'STARTTLS':
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings['smtp_username'], password)
        smtp.send_message(message)
    finally:
        try:
            smtp.quit()
        except Exception:
            smtp.close()


def _powershell(script):
    encoded = base64.b64encode(script.encode('utf-16le')).decode('ascii')
    return subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                          capture_output=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def show_notification(title, text):
    if sys.platform != 'win32':
        raise ValueError('Notificações do computador estão disponíveis no instalador Windows.')
    xml = '<toast><visual><binding template="ToastGeneric"><text>' + escape(title) + '</text><text>' + escape(text) + '</text></binding></visual></toast>'
    encoded = base64.b64encode(xml.encode('utf-8')).decode('ascii')
    result = _powershell("""$ErrorActionPreference='Stop'; [Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime] > $null;
    [Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,ContentType=WindowsRuntime] > $null;
    $xml=New-Object Windows.Data.Xml.Dom.XmlDocument;
    $xml.LoadXml([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('""" + encoded + """')));
    $notifier=[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('DoceAtelie.Pedidos');
    if($notifier.Setting -ne 'Enabled'){throw 'Notificações bloqueadas no Windows'};
    $notifier.Show([Windows.UI.Notifications.ToastNotification]::new($xml));""")
    if result.returncode:
        raise ValueError('Confira a permissão de notificações do Doce Ateliê nas configurações do Windows.')


def configure_background(enabled, store=None):
    if sys.platform != 'win32':
        return
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    if not enabled:
        script = f"$task=Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue; if($task){{Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction Stop}}"
    else:
        arguments = [] if getattr(sys, 'frozen', False) else [str(Path(__file__).resolve().parent.parent / 'desktop.py')]
        arguments += ['--notificar']
        if store is not None:
            arguments += ['--dados', str(store.data_dir.resolve()), '--midia', str(store.media_dir.resolve())]
        args = subprocess.list2cmdline(arguments)
        script = f"""$ErrorActionPreference='Stop';
        $user=[Security.Principal.WindowsIdentity]::GetCurrent().Name;
        $action=New-ScheduledTaskAction -Execute {quote(sys.executable)} -Argument {quote(args)};
        $trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15);
        $logon=New-ScheduledTaskTrigger -AtLogOn -User $user;
        $principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited;
        $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5);
        Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger @($trigger,$logon) -Principal $principal -Settings $settings -Force > $null;"""
    result = _powershell(script)
    if result.returncode:
        raise ValueError('Não foi possível ativar os avisos com o aplicativo fechado. Os avisos continuam disponíveis com o sistema aberto. Confira as permissões do Agendador de Tarefas do Windows.')


def check_reminders(store, now=None, mailer=send_email, notifier=show_notification):
    now = now or datetime.now()
    settings = store.settings()
    if not settings['reminders_enabled']:
        return
    ledger = Ledger(store)
    for reminder in due_reminders(store.quotes(), settings, now):
        for channel, enabled in [('local', settings['local_notifications']), ('email', settings['email_enabled'])]:
            # Alterar destinatário permite avisar a nova caixa sem repetir no dispositivo.
            delivery_channel = channel + (':' + settings['notification_email'] if channel == 'email' else '')
            if not enabled or not ledger.claim(reminder.key, delivery_channel, now):
                continue
            error = ''
            try:
                if channel == 'email':
                    mailer(settings, get_password(store), reminder.title, reminder.text)
                else:
                    notifier(reminder.title, reminder.text)
            except Exception:
                error = ('E-mail não enviado. Confira a internet, o servidor SMTP e a senha de aplicativo.' if channel == 'email'
                         else 'Notificação não exibida. Confira a permissão de notificações do Windows.')
            ledger.finish(reminder.key, delivery_channel, now, error)


_workers = set()
_worker_lock = threading.Lock()


def ensure_worker(store):
    if not store.settings()['reminders_enabled']:
        return
    key = str(store.db_path.resolve())
    with _worker_lock:
        if key in _workers:
            return
        _workers.add(key)
    def work():
        while store.db_path.is_file():
            try:
                check_reminders(store)
            except Exception:
                pass
            threading.Event().wait(60)
        with _worker_lock:
            _workers.discard(key)
    threading.Thread(target=work, name='Lembretes da confeitaria', daemon=True).start()
