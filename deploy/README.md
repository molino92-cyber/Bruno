# Doce Ateliê no Android e no iPhone

A versão 1.2 inclui um **aplicativo web instalável (PWA)**. Android, iPhone, iPad e computadores acessam a mesma base no servidor. O ícone abre uma janela própria, com login, clientes, produtos, orçamentos, pagamentos, fotos e PDFs.

O acesso móvel **precisa de conexão com o servidor**. O instalador Windows continua funcionando localmente, inclusive sem internet, com banco próprio. Não existe sincronização automática entre um banco local do Windows e o banco hospedado. Para compartilhar os dados, todos os aparelhos, incluindo o computador, devem acessar a mesma URL hospedada. O PWA não é um APK nem um aplicativo publicado na App Store.

## Instalar no celular

Depois da hospedagem, abra a URL HTTPS da confeitaria e entre com a senha configurada:

- **Android:** Chrome → menu ⋮ → Instalar aplicativo ou Adicionar à tela inicial. Quando disponível, o botão **Instalar no celular** faz a mesma instalação.
- **iPhone / iPad:** Safari → Compartilhar → Adicionar à Tela de Início → Adicionar. Se a opção não aparecer dentro de outro aplicativo, abra o endereço diretamente no Safari.

Use **Ir para**, no topo do sistema, para navegar nas telas pequenas. A lista de clientes permite rolagem horizontal dentro da tabela. Fotos usam quadros de altura fixa. Uploads de foto podem usar a galeria ou a câmera, conforme o seletor de arquivos do aparelho. PDFs são baixados pelo navegador para compartilhar ou imprimir.

O sistema não armazena clientes, pedidos, imagens privadas nem PDFs no cache offline do celular. Sem conexão, exibe um aviso; não aceita alterações offline. A sessão dura até oito horas e usa cookie assinado. A senha é compartilhada pela equipe: esta versão não possui contas individuais nem permissões por funcionário.

## Hospedar com HTTPS

Requisitos: servidor Linux com Docker + Docker Compose, domínio/subdomínio apontando para o IP do servidor, portas 80/443 liberadas para esse servidor. A hospedagem e o domínio são contratados separadamente. Não é necessário Apple Developer ou Google Play para instalar o PWA pela URL.

1. Envie o conteúdo do pacote Android/iOS ao servidor, preservando a estrutura das pastas.
2. Copie `deploy/.env.example` para `deploy/.env`.
3. Em `deploy/.env`, configure `DOCE_DOMAIN` com o domínio real, sem `https://` nem caminho. Defina `DOCE_MOBILE_PASSWORD` com uma senha exclusiva de pelo menos 12 caracteres. Nunca envie esse arquivo ao GitHub.
4. Na raiz do projeto, execute:

```bash
docker compose --env-file deploy/.env -f deploy/compose.yaml up -d --build
docker compose --env-file deploy/.env -f deploy/compose.yaml ps
```

O Caddy provisiona HTTPS automaticamente quando o DNS e as portas estão corretos. O Streamlit fica em uma porta privada, acessível apenas pelo gateway autenticado. O banco e as fotos ficam no volume persistente `confeitaria`. Verifique o acesso pela URL HTTPS antes de entregar ao cliente; o repositório não provisiona nem contrata um servidor.

Para atualizar, faça backup pelo sistema, envie os arquivos novos e execute novamente `up -d --build`. Preserve o volume: **não use `down -v`**. A migração do banco mantém cadastros e recebimentos, com cópia antes de alterações estruturais. As cópias internas do banco não substituem o backup completo com fotos.

## Trazer dados do computador

No Windows, prepare o backup em Configurações e encerre o aplicativo. O ZIP contém `dados/confeitaria.sqlite3` e `midia/`. Transfira para o servidor de forma privada, pare o serviço `sistema` e restaure essas duas pastas no volume `/data` do contêiner. Os arquivos precisam pertencer ao usuário de UID 10001. Inicie o serviço e confira clientes, fotos e saldos. Preserve uma cópia do backup original. A chave `.mobile-session-key` é criada no servidor, não deve ser colocada no ZIP distribuído nem substituída por uma chave pública.

Após a migração, use a URL hospedada no computador e nos celulares para manter um único cadastro. O aplicativo Windows local permanece independente e não deve ser usado para editar uma cópia paralela se a intenção for compartilhar os mesmos pedidos.

## Teste local para desenvolvedores

Na raiz, instale `requirements.txt`, defina `DOCE_MOBILE_PASSWORD` no ambiente e execute:

```bash
python mobile.py --porta 8080
```

Abra `http://localhost:8080` **no próprio computador**. HTTP local serve apenas para desenvolvimento. A instalação nos celulares exige uma URL HTTPS; usar o IP HTTP do computador não substitui a hospedagem segura.

Configurações opcionais: `DOCE_PUBLIC_URL` (origem HTTPS da loja), `CONFEITARIA_DATA_DIR` e `CONFEITARIA_MEDIA_DIR`. O comando `--endereco 0.0.0.0` destina-se ao contêiner ou a um servidor atrás de um proxy HTTPS. A porta privada do gateway não deve ser exposta diretamente à internet. O endpoint `/saude` informa a disponibilidade sem revelar dados de clientes.

## Validação

Os testes automatizados verificam login, senha incorreta, limite de tentativas, XSRF, bloqueio de acesso sem sessão, WebSocket com verificação de origem, uploads, downloads e manifesto de instalação. A interface também é conferida em navegador Chromium com largura de celular. A instalação real em aparelhos Android/iOS e o provisionamento de um domínio dependem do ambiente de hospedagem e dos aparelhos; não são simulados como já concluídos pelo pacote.
