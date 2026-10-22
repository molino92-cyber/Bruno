# Doce Ateliê · Gestão de Confeitaria

Sistema local em Python + Streamlit, com banco SQLite e fotos locais. A interface abre no navegador do próprio computador. Não depende de servidor remoto, Excel ou serviços pagos.

## Instalador Windows para clientes

O projeto inclui um inicializador com janela própria, empacotamento PyInstaller e instalador Inno Setup. O cliente instala pelo `.exe` e abre por um atalho, **sem instalar Python ou usar terminal**. Os dados ficam em `%LOCALAPPDATA%\DoceAtelie`, preservados nas atualizações. A interface permanece no navegador local.

Consulte [como gerar e distribuir o instalador](packaging/README.md). O `.exe` precisa ser compilado e validado no Windows; há um workflow manual no GitHub Actions preparado para isso.

## Interface renovada · versão 1.1

Navegação lateral, cartões com fotos, pesquisa de clientes, ações de cadastro visíveis e controles de calendário e upload em português. As telas se adaptam a janelas menores.

- **Clientes:** lista com busca por nome, telefone, e-mail ou CPF; botões Ver cadastro, Editar e Excluir. Formulário com nome, CPF, WhatsApp, telefone adicional, e-mail, CEP, rua, número, complemento, bairro, cidade, UF, ponto de referência, foto e observações.
- **Exclusão com confirmação:** clientes sem pedidos podem ser excluídos. Com pedidos, a ação passa a Arquivar e mantém o histórico financeiro. Use o filtro Arquivados para restaurar um cadastro.
- **Novo orçamento em quatro etapas:** Cliente → Produtos → Pagamento → Revisão. O resumo acompanha o preenchimento; é possível voltar sem perder os dados e editar ou remover os itens antes de salvar.
- **Novo cliente dentro do orçamento:** o cadastro abre em uma janela, sem abandonar o pedido; ao salvar, o cliente fica selecionado.
- **Atualização dos dados:** bancos da versão anterior são migrados automaticamente, com cópia do banco antes da mudança em `dados/copias_antes_atualizacao/`. Os endereços antigos permanecem disponíveis, sem tentativa de separação automática. Preencha os novos campos quando editar o cliente. Fotos, pedidos e pagamentos existentes são preservados.

As imagens em `docs/imagens/` usam dados fictícios para mostrar as telas.

## Executar

Instale **Python 3.10+** (recomendado: 3.12). No terminal, dentro desta pasta:

```bash
python iniciar.py
```

No Windows também é possível usar `py iniciar.py`; no Linux/macOS, `python3 iniciar.py`. O inicializador cria `.venv`, instala as versões de `requirements.txt` e inicia o Streamlit apenas na interface de rede local do computador. A primeira instalação requer internet. O aplicativo e os dados funcionam offline depois da instalação. Encerre com **Ctrl+C** no terminal.

Opções:

```bash
python iniciar.py --sem-navegador --porta 8501
```

Instalação e execução manuais:

```bash
python -m venv .venv
# Linux/macOS
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run app.py
# Windows: use .venv\Scripts\python.exe em vez de .venv/bin/python
```

## Primeiro uso

1. Em **Configurações**, cadastre nome, telefone, documento, endereço, logo e prazo de alterações da confeitaria.
2. Em **Catálogo**, revise os produtos iniciais. Bolo Simples começa em **R$ 75/kg** e Bolo Especial em **R$ 85/kg**. Os outros produtos começam **sem preço**, para você definir seus valores reais. Preço zero só permite adicionar como cortesia. Cadastre variantes separadas para brigadeiros Tradicionais, Especiais ou Personalizados com preços diferentes.
3. Em **Clientes → Novo cliente**, preencha contato e endereço nos campos separados. Nome e WhatsApp são obrigatórios; CPF e os demais campos são opcionais. CPF, CEP e e-mail preenchidos são validados.
4. Cadastre insumos em **Insumos e estoque**. O valor pago é **por embalagem**; o custo unitário é esse valor dividido pelo conteúdo em g, ml ou unidade. Ex.: R$ 5,00 por 1.000 ml = R$ 0,0050/ml. Quantidade em estoque corresponde ao número de embalagens da unidade indicada.
5. Em **Novo orçamento**, selecione o cliente (ou cadastre um novo ali mesmo), informe data e entrega, adicione os produtos, defina o pagamento e revise. Finalize com **Salvar orçamento e abrir pedido**.
6. Em **Pedidos e pagamentos**, abra o pedido, baixe os PDFs e registre apenas os pagamentos efetivamente recebidos.
7. Em **Agenda de produção**, clique no dia para visualizar os pedidos reservados em ordem de horário e baixar as fichas da cozinha.

## Regras implementadas

- Galeria local de **até 3 fotos por produto**, descrição e sete categorias. JPG, PNG e WEBP, até 10 MB por foto; as imagens são normalizadas em PNG, com resolução máxima de 1.800 × 1.800 e nomes aleatórios. Metadados EXIF são removidos.
- Promoção com preço e intervalo inclusivo de início/fim. O preço vigente é registrado ao adicionar o item ao orçamento; pedidos salvos preservam esse preço mesmo após editar o catálogo.
- Bolo Simples: **mínimo de 2 kg** e apenas Chocolate, Ninho, Chocolate Branco ou Dois Amores. Bolo Especial: apenas a lista de recheios especiais. Como não foi definido mínimo para o especial, a interface permite a partir de 0,1 kg.
- Adicionais de massa, brigadeiros, frutas, recheios extras, andar e topo têm **preço manual pelo item inteiro**, sem multiplicação por kg. Qualquer item ou adicional pode ser **[BRINDE]**, com cobrança zero. Outros produtos são cobrados por unidade; brigadeiros por cento inteiro.
- Brigadeiros: categoria Tradicional/Especial/Personalizado; cento inteiro ou **50 de cada sabor por cento**. A categoria descreve a produção; o preço vem do produto/variante cadastrado.
- PIX/Dinheiro **desativado por padrão**. Para aplicar, marque a opção e informe o percentual. Há aviso quando o pedido inclui promoção; acumular é uma decisão explícita do usuário. Cartão não permite o desconto PIX.
- Cálculo: `subtotal − desconto geral + frete = preço cartão`. O desconto PIX incide sobre `subtotal − desconto geral`, **sem descontar o frete**. O desconto geral não pode superar o subtotal. Valores monetários são armazenados em centavos; multiplicações e percentuais usam `Decimal` com arredondamento comercial.
- Validade de **7 dias**. O pedido começa **Em Aberto**; após a validade fica **Vencido** se ainda não reservou a data. Pode ser renovado por mais 7 dias antes do recebimento.
- Pagamentos parciais são somados. O sinal mínimo de 50% é arredondado para cima no centavo indivisível. Ao atingir esse valor, o pedido vira **Aprovado / Data Reservada**. Quitação integral gera **Quitado / Data Reservada**. Entrega só é registrada após quitação. O saldo corresponde ao total menos os recebimentos reais; pode diferir de 50% se o sinal recebido for outro valor.
- A caixa “Entrada de 50% recebida” identifica o lançamento; a aprovação depende do **valor efetivamente recebido**, não apenas da marcação. O campo de recebimento sugere o valor que falta para o sinal, ou o saldo final se já aprovado. É preciso confirmar o recebimento.
- A agenda mostra apenas pedidos aprovados/quitados ainda não entregues. Permite vários pedidos no mesmo horário; não impõe capacidade de produção nem bloqueia horários automaticamente.
- Orçamentos sem pagamento podem ser editados. No assistente, cada item tem ações de edição e remoção. Após qualquer recebimento, composição e valores ficam preservados. Não há exclusão de lançamentos, estorno, cancelamento financeiro ou alteração de pedidos pagos nesta versão.
- Dados da loja, cliente, preços e condições são copiados para o pedido ao salvar. Alterações cadastrais posteriores não reescrevem documentos históricos. Ao editar um pedido sem pagamentos, os dados cadastrais são atualizados nessa nova gravação.

## Documentos

**Orçamento do cliente:** logo e dados da loja, cliente, itens discriminados, sabores, adicionais, brindes, preço cartão, valor PIX quando ativado, frete, descontos, sinal, recebimentos, saldo, validade e observações. Inclui o texto jurídico solicitado e o prazo de alteração configurável.

**Ficha de produção:** nome e contato do cliente, saída/retirada, endereço, foto de referência, quantidades, sabores, recheios, adicionais, decoração, alergias e transporte. Não inclui campos de preço, desconto, pagamentos ou saldo. Informações que a cozinha precisa devem ser colocadas no campo **Decoração, alergias, restrições e transporte**; o campo comercial “Observações gerais” aparece apenas no orçamento.

Os PDFs são gerados pelo ReportLab, com paginação, sem serviços externos. Baixe o arquivo e imprima pelo leitor de PDFs.

## Dados, privacidade e backup

```text
dados/confeitaria.sqlite3   # clientes, produtos, insumos, pedidos, pagamentos e configurações
midia/                     # fotos de produtos, clientes, insumos, referências e logos
```

As pastas são criadas automaticamente e ignoradas pelo Git, assim como `.venv/`. Fotos retiradas de um cadastro não são apagadas fisicamente, preservando referências históricas. Faça backup periódico e controle o espaço em disco.

Em **Configurações → Preparar cópia de segurança**, baixe o ZIP com snapshot consistente do SQLite e todas as mídias. **Para restaurar**, encerre todos os processos do aplicativo, preserve uma cópia das pastas atuais e extraia `dados/` e `midia/` do backup na pasta do projeto. Reinicie e confira os pedidos. Nunca substitua o banco enquanto o aplicativo estiver em execução.

Para separar dados do código, defina `CONFEITARIA_DATA_DIR` e `CONFEITARIA_MEDIA_DIR` com diretórios locais de sua escolha. Na restauração, use esses diretórios correspondentes. Não use diretórios compartilhados por rede para o banco SQLite.

Os dados incluem CPF, endereço e foto. O aplicativo não oferece login nem criptografia própria: destina-se a **uso local por pessoas autorizadas**, mantendo o servidor em `127.0.0.1`. Proteja o computador e os backups. Não exponha a porta à internet. Não são necessárias chaves de API nem credenciais.

## Validação e desenvolvimento

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
```

Os testes usam bancos e imagens temporários e não alteram dados reais. Cobrem cálculos, promoções, brindes, recheios, divisão 50/50, persistência, validade, pagamentos, reserva/entrega, backup e extração de texto dos dois PDFs para verificar a ausência de campos financeiros na ficha da cozinha. Os testes de interface usam o AppTest oficial do Streamlit.

Estrutura: `app.py` contém a navegação e as telas gerais; `confeitaria/ui_customers.py` e `ui_quotes.py`, os cadastros e o assistente; `presentation.py`, os componentes visuais; `domain.py`, as regras; `storage.py`, a persistência/mídia; e `pdf.py`, os documentos. O estoque é uma estrutura manual para análise futura: não há ficha técnica de receitas nem consumo automático dos insumos.
