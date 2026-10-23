"""Preferências reais no navegador; ponte simulada apenas para credenciais nativas."""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=b.new_page(viewport={'width':390,'height':844});page.set_default_timeout(10000)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://127.0.0.1:8508');page.get_by_role('button',name='Mais',exact=True).click();page.get_by_role('button',name='Alertas e e-mail',exact=True).click()
 page.get_by_label('Ativar lembretes de encomendas',exact=True).check();page.get_by_label('E-mail para receber notificações',exact=True).fill('cozinha@example.com')
 page.get_by_label('Horário dos avisos',exact=True).fill('08:00');page.get_by_role('button',name='Salvar alertas',exact=True).click()
 assert page.evaluate('state.settings.reminders_enabled') is True
 assert page.evaluate('state.settings.alert_days')==[3,2]
 page.reload();page.get_by_role('button',name='Mais',exact=True).click();page.get_by_role('button',name='Alertas e e-mail',exact=True).click()
 assert page.get_by_label('E-mail para receber notificações',exact=True).input_value()=='cozinha@example.com'
 assert page.get_by_label('Ativar lembretes de encomendas',exact=True).is_checked()
 page.get_by_label('Enviar também por e-mail',exact=True).check();page.locator('summary').filter(has_text='Configurar o envio de e-mail').click()
 page.get_by_label('Usuário SMTP',exact=True).fill('loja@example.com');page.get_by_label('E-mail do remetente',exact=True).fill('loja@example.com')
 page.get_by_role('button',name='Salvar alertas',exact=True).click();assert page.get_by_role('alert').inner_text().startswith('Cadastre a senha')
 # Usar o mesmo armazenamento do navegador; só a senha e a permissão pertencem à ponte.
 page.evaluate("window.Android={saveState:(mode,raw)=>{localStorage.setItem('doce-android-'+mode,raw);return '';},reminderStatus:()=>JSON.stringify({permission:true,has_password:false}),saveMailPassword:password=>{window.passwordWasSaved=password==='senha-ficticia';return '';},requestNotifications:()=>{},testReminderEmail:()=>{}}")
 page.get_by_label('Senha de aplicativo do e-mail',exact=True).fill('senha-ficticia');page.get_by_role('button',name='Salvar alertas',exact=True).click()
 assert page.evaluate('window.passwordWasSaved') is True
 assert page.evaluate('state.settings.email_enabled') is True
 assert 'senha-ficticia' not in page.evaluate('JSON.stringify(state)')
 assert 'senha-ficticia' not in page.evaluate('JSON.stringify(localStorage)')
 for width in [320,390,768]:
  page.set_viewport_size({'width':width,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.set_viewport_size({'width':390,'height':844});page.screenshot(path='/tmp/doce-android-alertas.png',full_page=True)
 assert not errors,errors
 b.close();print('OK: preferências persistidas, dias/horário, destinatário, validação SMTP e senha fora do banco/backup; layout sem transbordar.')
