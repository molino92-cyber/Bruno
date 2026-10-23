# Alertas de encomendas e e-mail

Disponíveis no instalador Windows 1.3.0 e no APK Android 1.1.0. As configurações e os bancos de cada dispositivo são independentes.

## Ativar

- **Windows:** Configurações → Alertas de encomendas e e-mail.
- **Android:** Mais → Alertas e e-mail.

Marque **Ativar lembretes de encomendas**, escolha os dias (padrão: três e dois dias antes) e o horário local (padrão: 09:00). É possível escolher sete, três, dois, um dia antes e no próprio dia. Salve as preferências. No Android 13 ou superior, permita as notificações quando o sistema pedir; se já estiverem bloqueadas, use **Abrir permissões**.

Os lembretes acompanham pedidos com pelo menos 50% recebidos, incluindo os quitados, que ainda não foram entregues. Orçamentos em aberto ou vencidos não entram. Ao alterar a data/horário, os próximos avisos acompanham a nova saída. Avisos já recebidos permanecem na central do sistema até serem removidos.

O aplicativo registra separadamente os envios de cada pedido, data, antecedência e canal. Se um dispositivo ficou desligado, recupera apenas o lembrete mais recente que ainda faz sentido antes da saída, sem disparar todos os dias perdidos. Pedidos entregues ou com horário de saída ultrapassado não geram novos avisos. Notificações emitidas anteriormente podem continuar na central do sistema.

## E-mail automático

Preencha **E-mail para receber notificações** com o endereço da confeitaria. Marque **Enviar também por e-mail**, configure a conta de envio e salve. O endereço destinatário pode ser diferente do remetente. Os e-mails desta versão são enviados à confeitaria, não aos clientes.

Exemplo de conta Gmail:

| Campo | Valor |
|---|---|
| Servidor SMTP | `smtp.gmail.com` |
| Porta | `465` |
| Segurança | `SSL/TLS` |
| Usuário SMTP | E-mail completo da conta de envio |
| E-mail do remetente | Mesmo endereço da conta de envio |
| Senha | Senha de aplicativo gerada na Conta Google |

Para Gmail, ative a verificação em duas etapas e gere uma **senha de aplicativo** na segurança da Conta Google. O provedor pode restringir essa opção conforme o tipo de conta. Outros provedores podem usar porta `587` com `STARTTLS`, usuário e senha de aplicativo próprios. A conexão sempre usa TLS com verificação do certificado e do nome do servidor; não existe modo de envio sem criptografia.

Clique em **Enviar e-mail de teste** e confira a caixa de entrada e o spam. O envio automático exige internet e uma conta SMTP que permita autenticação por senha de aplicativo. Se houver falha temporária, os próximos ciclos tentam novamente, sem repetir o canal que já foi entregue. Um pedido entregue ou cujo horário passou interrompe as tentativas pendentes. A aceitação pelo servidor SMTP não garante que o provedor destinatário entregue na caixa de entrada.

A senha fica protegida pela conta do Windows (DPAPI) ou pelo Android Keystore. Ela não integra o SQLite de cadastros, JSON de backup Android ou ZIP de backup Windows, e não acompanha instaladores. Ao migrar para outro dispositivo, cadastre a senha novamente. Deixar a senha em branco mantém a credencial que já está naquele dispositivo.

## Quando o sistema está fechado

**Windows:** ao ativar os lembretes, o aplicativo registra a tarefa `DoceAtelie-Lembretes` no Agendador de Tarefas, para seu usuário, sem executar como administrador. Ela verifica aproximadamente a cada 15 minutos e ao entrar no Windows. O computador precisa estar ligado e o usuário conectado. Suspensão, computador desligado, modo Não incomodar ou permissões do Windows podem atrasar ou ocultar os avisos. A interface não precisa ficar aberta. Desativar os lembretes remove a tarefa; desinstalar o programa também a remove. Se uma política do computador impedir o agendamento, a tela mostra o erro e o aplicativo continua verificando com o servidor local aberto.

**Android:** o APK registra uma verificação periódica persistente no JobScheduler. Ela funciona após fechar a interface e é recuperada pelo Android após reiniciar/desbloquear o aparelho. A execução segue a economia de bateria e as cotas do Android; o horário escolhido é uma referência, não um alarme de precisão. Após **Forçar parada** ou aplicar restrições severas de bateria, abra o aplicativo novamente. Os avisos no próprio celular funcionam sem internet; e-mails ficam sujeitos à conexão. Tocar na notificação abre o pedido correspondente.

**Edição hospedada:** o servidor precisa continuar ligado para enviar e-mails; ela não ganha notificações push de iOS por esta atualização. Configure `DOCE_SMTP_PASSWORD` no ambiente do servidor, sem gravar a senha no formulário. Para verificação contínua após reinícios, agende a execução do comando abaixo com o mesmo usuário e as mesmas pastas de dados, a cada 15 minutos:

```bash
python desktop.py --notificar --dados /caminho/dados --midia /caminho/midia
```

As notificações nativas desta atualização pertencem ao instalador Windows e ao APK Android. Não existe sincronização automática entre seus bancos ou deduplicação entre aparelhos independentes.

## Validação técnica

Os testes cobrem mudança de mês/ano, horário limite, recuperação após período desligado, alteração de data, pedidos entregues/em aberto, registro persistente para evitar repetições, canais independentes, tentativas após falha, TLS antes da autenticação, proteção da senha e exclusão da credencial nos backups. A CI Windows verifica DPAPI e registro/remoção da tarefa; a CI Android valida a tarefa persistente e a notificação real na central de um emulador Android 15, com a permissão concedida. Sem uma conta SMTP fornecida pelo usuário, os testes de protocolo usam transportes simulados; o botão de teste confirma a configuração real no dispositivo do cliente.
