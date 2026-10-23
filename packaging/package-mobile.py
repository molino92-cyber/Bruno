"""Gera o pacote de hospedagem Android/iOS; não inclui dados, senhas ou ambientes locais."""
from pathlib import Path
import zipfile

root=Path(__file__).resolve().parent.parent
output=root/"dist"/"DoceAtelie-Android-iOS-1.3.0.zip"
output.parent.mkdir(exist_ok=True)
files=[root/name for name in ["app.py","mobile.py","requirements.txt","README.md"]]
for folder in ["confeitaria","assets","web/mobile","deploy",".streamlit"]:
    files += [path for path in (root/folder).rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc",".pyo"} and path.name not in {".env","secrets.toml"}]
files.append(root/".dockerignore")
with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path,path.relative_to(root))
print(output.name)
