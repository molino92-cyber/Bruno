# Doce Ateliê · APK Android local

O aplicativo Android **instala por APK e funciona sozinho no celular**, sem Python, sem hospedagem e sem depender do computador ligado. Requer Android 8.0 ou superior e Android System WebView atualizado. O banco SQLite e as fotos ficam na área privada do aplicativo.

## Instalar

1. No Android, baixe [`DoceAtelie-Android-1.0.2.apk`](distribuicao/DoceAtelie-Android-1.0.2.apk).
2. Abra o arquivo baixado. Se o Android solicitar, permita que o navegador ou gerenciador de arquivos usado instale este aplicativo. Não é necessário desativar o Play Protect.
3. Toque em **Instalar** e abra **Doce Ateliê** pelo ícone.
4. Em **Mais → Configurações e backup**, cadastre a identidade e a logo da loja. Confira os preços do catálogo: R$ 75/kg para o Simples e R$ 85/kg para o Especial; os demais preços reais ficam para cadastrar.

Para atualizar, instale um APK mais recente da mesma assinatura sobre o aplicativo existente. Faça backup antes. **Não desinstale para atualizar**, pois isso apaga os dados locais. A assinatura e o identificador `br.com.doceatelie` devem ser preservados.

O APK é para Android. iPhone não instala arquivos APK.

## Atualização 1.0.2

Em **Mais → Configurações e backup**, altere **Nome da confeitaria** e envie sua **Logo da confeitaria · cabeçalho e PDFs**. Ao salvar, a identidade substitui o nome e o cupcake do cabeçalho. A logo mantém a proporção em um quadro pequeno. Nome e imagem permanecem salvos ao fechar e reabrir o aplicativo. Remover a logo restaura o ícone padrão. Pedidos anteriores preservam a identidade registrada no orçamento; os próximos usam a nova.

## Correção incluída desde 1.0.1

Correção da área segura da tela: cabeçalho abaixo da barra de status e menu acima da navegação Android, tanto por gestos quanto por três botões. O teclado reduz a área do aplicativo sem somar os espaços duas vezes. Ícones vetoriais e textos do menu têm contraste maior. A assinatura e o banco são mantidos; instale por cima da versão 1.0.0.

## Recursos

- Catálogo com sete categorias, até três fotos por item, descrições, promoções por período e quatro kits festa com composição editável.
- Fotos padronizadas em quadros de 145 px no celular e 170 px em telas maiores; proporção preservada, sem estourar o layout.
- Clientes em tabela compacta com busca, paginação, cadastro completo, edição e exclusão com confirmação. Clientes com pedidos são arquivados, preservando o histórico. CEP preenche rua, bairro, cidade e UF quando há internet; número e complemento são manuais.
- Orçamento em quatro etapas, com recheios específicos de cada tipo de bolo. Simples e Especial têm mínimo padrão de 2 kg. Abaixo disso, um recheio; a partir de 2 kg, até dois. Exceções de peso e recheios precisam de confirmação e justificativa.
- Adicionais por quantidade × preço unitário, brindes, sabores tradicionais/especiais/personalizados e divisão do cento em 50/50. Imagens de inspiração por item e topo.
- Desconto PIX manual, desconto geral, frete, observações e orientações da cozinha.
- Pedidos listados sem abrir automaticamente os detalhes. Sinal de 50%, recebimentos, saldo real, quitação e entrega; agenda de pedidos reservados.
- Orçamento PDF com logo e valores, ficha da cozinha sem preços e com referências; salvar pelo seletor de arquivos Android ou compartilhar em outro aplicativo.
- Demonstração com dados fictícios em banco separado. Backup JSON com fotos, restauração confirmada e cópia anterior à restauração.

## Dados e backup

Esta edição possui **banco próprio no Android**. Não há sincronização automática com Windows, PWA ou outros celulares. Para compartilhar uma base entre aparelhos, use a edição hospedada descrita em [deploy/README.md](../deploy/README.md).

Em **Mais → Configurações e backup → Salvar backup completo**, escolha uma pasta e guarde uma cópia fora do aparelho. O backup pode conter CPF, endereço, fotos e histórico financeiro. O aplicativo local usa o acesso do próprio celular, sem senha adicional: proteja-o com o bloqueio de tela.

O JSON do Android é exclusivo desta edição e não importa o ZIP do Windows. Desinstalar ou limpar o armazenamento apaga os cadastros e fotos; o APK não contém dados pessoais. Ao restaurar, o aplicativo pede confirmação e guarda uma cópia anterior no armazenamento privado. Ela pode ser recuperada pelo botão correspondente, mas não substitui um backup externo.

A consulta de CEP envia somente o CEP ao ViaCEP. Todos os outros recursos de gestão, imagens e PDFs funcionam sem internet. A permissão de internet existe para essa consulta. Não há anúncios nem envio automático de cadastros a servidores.

## Compilar e preservar a assinatura

Ferramentas de desenvolvimento: JDK 17, Gradle 8.10.2, SDK Android 35 e Build Tools 35.0.0. A edição Android usa Java e uma interface HTML/JavaScript local; não empacota o Streamlit nem executa um servidor no telefone.

```bash
node --test android/tests/logic.test.cjs
gradle -p android assembleDebug assembleDebugAndroidTest lintDebug
```

O APK de teste usa identificador `br.com.doceatelie.teste` e não substitui a instalação principal. O workflow **Validar APK Android** compila, executa testes em emulador API 35 e instala o APK distribuído.

O APK distribuído usa assinatura própria de release, sem chave de depuração. A chave privada e `keystore.properties` ficam em `android/assinatura/`, ignorada pelo Git; nunca envie essa pasta ao repositório público. Preserve uma cópia privada segura desses arquivos para gerar atualizações. Não gere uma chave nova para uma atualização do mesmo aplicativo. A CI verifica o APK existente e gera um APK de teste separado; não tem acesso à chave privada de release.

Para compilar release, crie `android/assinatura/keystore.properties` com `storeFile`, `storePassword`, `keyAlias` e `keyPassword`; o arquivo `storeFile` fica nessa mesma pasta. Execute `gradle -p android assembleRelease lintRelease`, valide com `apksigner verify --print-certs`, atualize o APK em `distribuicao/` e seu SHA-256. Distribua somente o APK, nunca a chave.

Dependências locais de PDF: jsPDF 4.2.1 e jsPDF-AutoTable 5.0.9, com licenças MIT em `app/src/main/assets/vendor/`. Elas acompanham o APK e não usam CDN durante o funcionamento.
