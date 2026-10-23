"""Datas reais, deduplicação entre processos, retry e privacidade dos lembretes."""
from datetime import datetime, timedelta
from io import BytesIO
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile
from confeitaria.notifications import (Ledger, _dpapi, check_reminders, due_reminders,
    get_password, save_password, send_email, validate_settings)
from confeitaria.storage import Store


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name)
        self.store=Store(root/'dados',root/'midia')
        self.settings={**self.store.settings(),'reminders_enabled':True,'email_enabled':True,
            'notification_email':'cozinha@example.com','smtp_sender':'loja@example.com','smtp_username':'loja@example.com'}
        self.store.save_settings(self.settings)
        self.now=datetime(2026,12,29,9,0)
        self.quotes=[{'id':1,'event_at':'2027-01-01T14:00:00','customer':{'name':'Ana'},'status':'Aprovado / Data Reservada','delivered':False}]
    def tearDown(self):self.temp.cleanup()

    def test_calendar_days_threshold_catchup_reschedule_and_delivery(self):
        self.assertEqual(due_reminders(self.quotes,self.settings,self.now-timedelta(seconds=1)),[])
        first=due_reminders(self.quotes,self.settings,self.now)[0]
        self.assertIn('01/01/2027 às 14:00',first.text)
        second=due_reminders(self.quotes,self.settings,self.now+timedelta(days=1))[0]
        self.assertNotEqual(first.key,second.key)
        self.assertEqual(first.key,due_reminders(self.quotes,{**self.settings,'alert_time':'08:00'},self.now)[0].key)
        # Ao ligar depois de vários dias, somente o aviso mais recente é elegível.
        self.assertEqual(len(due_reminders(self.quotes,self.settings,self.now+timedelta(days=2))),1)
        self.assertEqual(due_reminders(self.quotes,self.settings,datetime(2027,1,1,14)),[])
        self.quotes[0]['event_at']='2027-01-02T14:00:00'
        changed=due_reminders(self.quotes,self.settings,self.now+timedelta(days=1))[0]
        self.assertNotEqual(first.key,changed.key)
        for status,delivered in [('Em Aberto',False),('Vencido',False),('Entregue',True)]:
            self.quotes[0].update(status=status,delivered=delivered)
            self.assertEqual(due_reminders(self.quotes,self.settings,self.now+timedelta(days=1)),[])

    def test_claim_deduplicates_workers_and_recovers_abandoned_lease(self):
        first,second=Ledger(self.store),Ledger(self.store)
        self.assertTrue(first.claim('q1','email',self.now))
        self.assertFalse(second.claim('q1','email',self.now))
        self.assertTrue(second.claim('q1','email',self.now+timedelta(minutes=6)))
        second.finish('q1','email',self.now+timedelta(minutes=6))
        self.assertFalse(first.claim('q1','email',self.now+timedelta(days=1)))

    def test_success_failure_retry_channels_and_changed_destination(self):
        mailer,notifier=Mock(side_effect=OSError('Não expor detalhes ou credenciais')),Mock()
        with patch.object(self.store,'quotes',return_value=self.quotes),patch.dict(os.environ,{'DOCE_SMTP_PASSWORD':'senha-ficticia'}):
            check_reminders(self.store,self.now,mailer,notifier)
            self.assertEqual(notifier.call_count,1);self.assertEqual(mailer.call_count,1)
            check_reminders(self.store,self.now+timedelta(minutes=5),mailer,notifier)
            self.assertEqual(mailer.call_count,1)
            mailer.side_effect=None
            check_reminders(self.store,self.now+timedelta(minutes=16),mailer,notifier)
            check_reminders(self.store,self.now+timedelta(minutes=30),mailer,notifier)
            self.assertEqual(mailer.call_count,2);self.assertEqual(notifier.call_count,1)
            self.store.save_settings({'notification_email':'outra@example.com'})
            check_reminders(self.store,self.now+timedelta(minutes=31),mailer,notifier)
            self.assertEqual(mailer.call_count,3)
            self.store.save_settings({'reminders_enabled':False})
            check_reminders(self.store,self.now+timedelta(days=1),mailer,notifier)
            self.assertEqual(mailer.call_count,3)
        self.assertNotIn('senha-ficticia',json.dumps(Ledger(self.store).status()))

    def test_configuration_and_backup_do_not_contain_smtp_password(self):
        for values in [{'alert_days':[]},{'alert_time':'24:00'},{'notification_email':'x\r\nBcc:hacker@example.com'},{'smtp_security':'NONE'}]:
            with self.assertRaises(ValueError):validate_settings({**self.settings,**values})
        self.store.save_settings({'name':'Doce e Afeto'})
        self.assertEqual(self.store.settings()['notification_email'],'cozinha@example.com')
        (self.store.data_dir/'.smtp-password').write_bytes(b'credencial-privada-ficticia')
        with zipfile.ZipFile(BytesIO(self.store.backup())) as backup:
            self.assertFalse(any('smtp-password' in path for path in backup.namelist()))
        self.assertNotIn('password',json.dumps(self.store.settings()))

    def test_smtp_requires_verified_tls_and_does_not_resend_when_quit_fails(self):
        for security in ['SSL/TLS','STARTTLS']:
            connection=Mock();connection.quit.side_effect=OSError('Desconectou após aceitar o e-mail')
            with patch('smtplib.SMTP_SSL',return_value=connection) as ssl_constructor,patch('smtplib.SMTP',return_value=connection) as start_constructor:
                send_email({**self.settings,'smtp_security':security},'senha-ficticia','Lembrete','Encomenda')
                constructor=ssl_constructor if security=='SSL/TLS' else start_constructor
                self.assertTrue(constructor.called)
                context=constructor.call_args.kwargs.get('context') if security=='SSL/TLS' else connection.starttls.call_args.kwargs['context']
                self.assertTrue(context.check_hostname);self.assertEqual(context.verify_mode,2)
                self.assertEqual(connection.login.call_args.args,('loja@example.com','senha-ficticia'))
                self.assertEqual(connection.send_message.call_count,1)
                if security=='STARTTLS':
                    names=[call[0] for call in connection.mock_calls]
                    self.assertLess(names.index('starttls'),names.index('login'))

    @unittest.skipUnless(sys.platform=='win32','DPAPI pertence ao Windows')
    def test_windows_password_is_encrypted_and_recoverable(self):
        save_password(self.store,'senha-ficticia-123')
        raw=(self.store.data_dir/'.smtp-password').read_bytes()
        self.assertNotIn(b'senha-ficticia-123',raw)
        with patch.dict(os.environ):
            os.environ.pop('DOCE_SMTP_PASSWORD',None)
            self.assertEqual(get_password(self.store),'senha-ficticia-123')

    @unittest.skipUnless(sys.platform=='win32','Agendador de Tarefas pertence ao Windows')
    def test_windows_background_task_registered_for_same_data_and_removed(self):
        import uuid
        from confeitaria.notifications import configure_background, _powershell
        name='DoceAtelie-Teste-'+uuid.uuid4().hex
        with patch('confeitaria.notifications.TASK_NAME',name):
            try:
                configure_background(True,self.store)
                result=_powershell("$task=Get-ScheduledTask -TaskName '"+name+"'; $task.Actions | ConvertTo-Json -Compress")
                self.assertEqual(result.returncode,0)
                action=json.loads(result.stdout.decode('utf-8-sig'))
                self.assertIn('--notificar',action['Arguments'])
                self.assertIn(str(self.store.data_dir.resolve()),action['Arguments'])
            finally:
                configure_background(False,self.store)
