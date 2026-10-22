"""Jornada pelo navegador em perfil temporário. Sirva app/src/main/assets na porta 8508. Requer Playwright e Chromium."""
from playwright.sync_api import sync_playwright
import re
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=b.new_page(viewport={'width':390,'height':844},accept_downloads=True);page.set_default_timeout(10000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 try:
  page.goto('http://127.0.0.1:8508');page.get_by_role('heading',name='Sua confeitaria em dia').wait_for()
  page.get_by_role('button',name='Clientes',exact=True).click();page.get_by_role('button',name='Novo cliente',exact=True).click()
  page.get_by_label('Nome completo *',exact=True).fill('Maria do Android');page.get_by_label('Telefone / WhatsApp *',exact=True).fill('92999998888');page.get_by_label('E-mail',exact=True).fill('maria@example.com');page.get_by_label('Rua / avenida',exact=True).fill('Rua das Flores');page.get_by_label('Número',exact=True).fill('42');page.get_by_label('Cidade',exact=True).fill('Manaus');page.get_by_label('Estado (UF)',exact=True).select_option('AM')
  page.get_by_role('button',name='Salvar cliente',exact=True).click();page.get_by_role('heading',name='Maria do Android').wait_for()
  page.get_by_role('button',name='Editar cliente',exact=True).click();page.get_by_label('Número',exact=True).fill('80');page.get_by_role('button',name='Salvar cliente',exact=True).click()
  assert page.get_by_text('Rua das Flores, 80',exact=False).count()
  page.get_by_role('button',name='Novo orçamento',exact=True).click();page.get_by_label('Recebimento',exact=True).select_option('Entrega')
  page.get_by_role('button',name='Continuar para produtos').click();page.get_by_label('Ninho',exact=True).check();page.get_by_role('button',name='Adicionar ao pedido').click()
  page.get_by_role('button',name='Continuar para pagamento').click();page.get_by_label('Conceder desconto PIX / Dinheiro').check();page.get_by_label('Desconto PIX / Dinheiro (%)').fill('10');page.get_by_label('Desconto geral (R$)').fill('10');page.get_by_label('Entrega / frete (R$)').fill('20');page.get_by_label('Orientações para a cozinha').fill('Tema jardim. Sem castanhas.');page.get_by_role('button',name='Revisar orçamento').click()
  page.get_by_role('button',name='Salvar orçamento',exact=True).click();page.get_by_role('heading',name='Pedidos e pagamentos').wait_for();page.get_by_role('button',name='Ver pedido').click();assert page.get_by_text('R$ 146,00',exact=True).count()
  with page.expect_download() as download:page.get_by_role('button',name='Salvar orçamento PDF').click()
  download.value.save_as('/tmp/doce-android-cliente.pdf')
  with page.expect_download() as download:page.get_by_role('button',name='Salvar ficha da cozinha').click()
  download.value.save_as('/tmp/doce-android-cozinha.pdf')
  page.get_by_label('Confirmo que este valor já foi recebido').check();page.get_by_role('button',name='Registrar recebimento').click();assert page.get_by_text('Aprovado / Data Reservada',exact=True).count()
  page.get_by_label('Confirmo que este valor já foi recebido').check();page.get_by_role('button',name='Registrar recebimento').click();page.get_by_role('button',name='Concluir entrega / retirada').click();page.get_by_role('button',name='Confirmar',exact=True).click();assert page.get_by_text('Entregue',exact=True).count()
  page.reload();page.get_by_role('button',name='Pedidos',exact=True).click();assert page.get_by_text('Maria do Android',exact=False).count();assert not errors,errors
  page.screenshot(path='/tmp/doce-android-pedidos.png',full_page=True)
  print('OK: cadastro, edição, orçamento, desconto manual, saldo, recebimentos, entrega, PDFs, persistência e JavaScript sem erros.')
 except Exception:
  print('ERRO:',page.locator('body').inner_text()[-4000:]);page.screenshot(path='/tmp/doce-android-erro.png',full_page=True);raise
 finally:b.close()
