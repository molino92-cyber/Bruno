"""Preferências de lembretes; credenciais não integram os cadastros ou backups."""
from datetime import datetime
import sys
import streamlit as st
from .notifications import (ALLOWED_DAYS, Ledger, configure_background, ensure_worker,
                            get_password, save_password, send_email, validate_settings)


def notification_settings(store, demo=False):
    s = store.settings()
    st.write('Receba lembretes das encomendas com data reservada. Pedidos entregues deixam de gerar avisos.')
    if demo:
        st.info('A demonstração não envia notificações nem e-mails. Configure nos seus dados reais.')
        return
    try:
        has_password = bool(get_password(store))
    except ValueError:
        has_password = False
    with st.form('notification_settings'):
        enabled = st.checkbox('Ativar lembretes de encomendas', value=s['reminders_enabled'])
        local = st.checkbox('Mostrar notificações neste computador', value=s['local_notifications'] if sys.platform == 'win32' else False, disabled=sys.platform != 'win32')
        days = st.multiselect('Antecedência dos alertas (dias)', ALLOWED_DAYS, default=s['alert_days'], format_func=lambda d: 'No dia' if d == 0 else f'{d} dia(s) antes')
        hour = st.time_input('Horário dos avisos', datetime.strptime(s['alert_time'], '%H:%M').time())
        st.caption('Horário local. No Windows, o computador precisa estar ligado e seu usuário conectado; os avisos podem chegar após sair da suspensão.')
        email = st.text_input('E-mail para receber notificações', s['notification_email'], placeholder='seuemail@exemplo.com')
        email_on = st.checkbox('Enviar também por e-mail', value=s['email_enabled'])
        st.caption('Configure uma conta de envio abaixo. O destinatário pode ser diferente do remetente. A senha de aplicativo não entra no backup.')
        a, b = st.columns(2)
        host = a.text_input('Servidor SMTP', s['smtp_host'])
        port = b.number_input('Porta SMTP', min_value=1, max_value=65535, value=s['smtp_port'])
        security = a.selectbox('Segurança do e-mail', ['SSL/TLS', 'STARTTLS'], index=0 if s['smtp_security'] == 'SSL/TLS' else 1)
        username = b.text_input('Usuário SMTP', s['smtp_username'])
        sender = st.text_input('E-mail do remetente', s['smtp_sender'])
        password = st.text_input('Senha de aplicativo do e-mail', type='password', help='Deixe em branco para manter a senha já salva. No Gmail, use uma senha de aplicativo gerada na Conta Google com verificação em duas etapas.')
        if has_password:
            st.caption('Senha de envio já configurada neste dispositivo.')
        if sys.platform != 'win32':
            st.caption('Na edição hospedada, a senha é configurada pelo administrador em DOCE_SMTP_PASSWORD. O servidor precisa permanecer ligado. Para executar sem a interface aberta, agende desktop.py --notificar com as pastas de dados do servidor a cada 15 minutos.')
        if st.form_submit_button('Salvar alertas', type='primary'):
            try:
                values = validate_settings({**s, 'reminders_enabled': enabled, 'local_notifications': local, 'alert_days': days,
                    'alert_time': hour.strftime('%H:%M'), 'notification_email': email.strip(), 'email_enabled': email_on,
                    'smtp_host': host.strip(), 'smtp_port': int(port), 'smtp_security': security,
                    'smtp_username': username.strip(), 'smtp_sender': sender.strip()})
                if enabled and email_on and not (password or has_password):
                    raise ValueError('Cadastre a senha de aplicativo para ativar os e-mails automáticos.')
                save_password(store, password)
                store.save_settings(values)
                try:
                    configure_background(enabled, store)
                except ValueError as exc:
                    st.warning(str(exc))
                ensure_worker(store)
                st.success('Preferências de alertas salvas. O nome e a logo da loja foram preservados.')
            except ValueError as exc:
                st.error(str(exc))
    if st.button('Enviar e-mail de teste'):
        try:
            current = store.settings()
            send_email(current, get_password(store), current['name'] + ' · Teste de notificações', 'Seu e-mail de notificações está configurado. Os avisos das encomendas reservadas serão enviados conforme os dias e o horário escolhidos.')
            st.success('E-mail de teste enviado. Confira também a pasta de spam.')
        except Exception:
            st.error('Não foi possível enviar. Salve as configurações e confira a internet, o destinatário e a senha de aplicativo do serviço de e-mail.')
    for row in Ledger(store).status()[:3]:
        if row['error']:
            st.warning(row['error'] + ' O sistema tentará novamente após 15 minutos, enquanto o pedido ainda estiver no prazo.')
