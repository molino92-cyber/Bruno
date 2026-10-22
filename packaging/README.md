# Versão Windows para o cliente

O empacotamento produz um **instalador Windows x64** e uma versão portátil. Python, Streamlit e todas as dependências acompanham o aplicativo. **O cliente não precisa instalar Python nem executar comandos.** A interface continua abrindo no navegador local; uma pequena janela controla Abrir / Encerrar.

## Experiência do cliente

1. Executar `DoceAtelie-Instalador-1.2.0-Windows-x64.exe`.
2. Seguir o instalador em português. A instalação é por usuário, sem exigir administrador.
3. Abrir **Doce Ateliê** pelo menu Iniciar ou pelo atalho da área de trabalho.
4. O navegador abre automaticamente quando o sistema está pronto. Manter a pequena janela Doce Ateliê aberta durante o uso.
5. Para encerrar, fechar a janela Doce Ateliê e confirmar. Fechar apenas a aba do navegador mantém o sistema em execução, podendo reabri-lo pelo botão **Abrir sistema**.

Duplo clique repetido reabre o sistema existente. O servidor atende apenas em `127.0.0.1`, usa uma porta local disponível e não exige internet para funcionar. O instalador não apaga os dados na atualização ou desinstalação.

## Onde ficam os dados

No executável, banco e fotos ficam separados da instalação:

```text
%LOCALAPPDATA%\DoceAtelie\dados\confeitaria.sqlite3
%LOCALAPPDATA%\DoceAtelie\midia\
%LOCALAPPDATA%\DoceAtelie\logs\
```

O botão **Abrir pasta de dados e backups** abre essa localização; backups são baixados pelo navegador em Configurações. Não há pasta de backup automática. Para migrar da versão de código-fonte, feche ambas as versões, preserve um backup e copie suas pastas `dados` e `midia` para essa localização. Não copie `.venv` nem arquivos do programa. Para restaurar um ZIP, use as mesmas pastas acima com o aplicativo fechado.

Na versão portátil, **copie a pasta inteira** `DoceAtelie`, incluindo `_internal`, e abra `DoceAtelie.exe`. Apenas copiar o `.exe` dessa pasta não basta. Para distribuir somente um arquivo, envie o **instalador**.

## Gerar no Windows (desenvolvedor)

O PyInstaller não compila para outro sistema operacional. Gere o `.exe` no **Windows 10/11 x64**, com Python 3.12 x64 e [Inno Setup 6](https://jrsoftware.org/isdl.php) instalados. Essas ferramentas são necessárias apenas no computador de compilação.

Abra PowerShell na raiz do projeto:

```powershell
.\packaging\build-windows.ps1
# Outra versão de atualização, se necessário:
.\packaging\build-windows.ps1 -Version 1.2.1
```

Se a política local bloquear scripts, ela precisa permitir esse script revisado conforme as regras do computador. Não é necessário mudar a política global.

O script cria `.venv-build`, instala dependências, executa os testes, empacota o programa, valida **o binário real** e gera o instalador. Falhas interrompem o processo. Resultado:

```text
dist\DoceAtelie\DoceAtelie.exe
dist\instalador\DoceAtelie-Instalador-1.2.0-Windows-x64.exe
```

O teste do binário verifica SQLite, mídia, orçamento/sinal, os dois PDFs, backup, resposta HTTP, renderização da interface por WebSocket e encerramento do servidor. Todo teste usa perfil temporário e não altera dados reais.

## Gerar pelo GitHub, sem preparar um computador

O arquivo `.github/workflows/windows-installer.yml` inclui um fluxo manual de compilação em Windows:

1. Envie os arquivos deste projeto, incluindo `.github`, para o repositório no GitHub. O ambiente local não envia alterações automaticamente.
2. No GitHub, abra **Actions → Gerar instalador Windows → Run workflow**.
3. Aguarde todos os passos concluírem.
4. Baixe **DoceAtelie-Instalador-Windows-x64** em Artifacts. Extraia o ZIP recebido e envie o instalador `.exe` ao cliente.

O workflow não publica releases nem distribui o programa automaticamente. Consome a disponibilidade/cota de GitHub Actions do repositório. Preserve o mesmo AppId do instalador nas atualizações para manter a identidade do aplicativo.

Na branch `codex/doce-atelie`, o envio de alterações também inicia a geração automaticamente. Execuções anteriores dessa branch são canceladas quando uma nova compilação começa. A versão 1.2 mantém o AppId da versão 1.0 e migra os cadastros existentes automaticamente, com cópia do banco antes da migração. Feche o aplicativo antes de instalar a atualização.

## Validação antes de distribuir

A compilação e os testes de pacote em Linux não validam o `.exe` do Windows. Antes da entrega, execute o workflow Windows e teste a instalação em um computador/VM Windows limpo, sem Python: abrir pelo atalho, cadastrar cliente, salvar orçamento, baixar PDFs, encerrar/reabrir e atualizar preservando dados. O desinstalador preserva intencionalmente os dados pessoais; a remoção deles é manual.

O projeto não inclui certificado de assinatura de código. O Windows pode identificar o instalador como de editor desconhecido. Para distribuição comercial, use o certificado de assinatura da empresa no `.exe` e no instalador. Não é necessário nem recomendado desativar o antivírus.

## Android e iOS

O mesmo workflow gera **DoceAtelie-Android-iOS-PWA**, com código, imagens e configuração de hospedagem HTTPS. É um pacote para o servidor, não um instalador APK/IPA. Depois da hospedagem, o cliente instala pela URL no Chrome (Android) ou Safari (iPhone). Veja [as instruções completas](../deploy/README.md).
