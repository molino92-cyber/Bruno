param([string]$Version = "1.3.1")
$ErrorActionPreference = "Stop"
if ($Version -notmatch '^\d+\.\d+\.\d+$') { throw "Use uma versão no formato 1.0.0." }
if ($env:OS -ne "Windows_NT") { throw "O executável Windows precisa ser gerado no Windows." }
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv-build\Scripts\python.exe")) {
    python -m venv .venv-build
    if ($LASTEXITCODE -ne 0) { throw "Instale Python 3.12 x64 no computador de compilação." }
}
$Python = Join-Path (Get-Location) ".venv-build\Scripts\python.exe"
& $Python -m pip install --disable-pip-version-check -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Falha na instalação das dependências." }
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Os testes do sistema falharam." }
& $Python -m PyInstaller --noconfirm --clean packaging\DoceAtelie.spec
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o executável." }
& $Python packaging\smoke_bundle.py dist\DoceAtelie\DoceAtelie.exe
if ($LASTEXITCODE -ne 0) { throw "A validação do executável falhou." }

$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($Iscc) { $Compiler = $Iscc.Source }
else { $Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $Compiler)) { throw "Instale Inno Setup 6 para gerar o instalador. O aplicativo portátil está em dist\DoceAtelie." }
& $Compiler "/DAppVersion=$Version" packaging\installer.iss
if ($LASTEXITCODE -ne 0) { throw "Falha ao gerar o instalador." }
Write-Host "Instalador gerado em dist\instalador. Envie o instalador .exe ao cliente."
