"""Inicializador portátil. Uso: python iniciar.py [--sem-navegador] [--porta 8501]."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description="Inicia o sistema local da confeitaria.")
    parser.add_argument("--sem-navegador", action="store_true", help="Não abrir o navegador automaticamente.")
    parser.add_argument("--porta", type=int, default=8501)
    args = parser.parse_args()
    if not 1 <= args.porta <= 65535:
        parser.error("A porta deve estar entre 1 e 65535.")
    if sys.version_info < (3, 10):
        raise SystemExit("Instale Python 3.10 ou superior (recomendado: 3.12).")
    root = Path(__file__).resolve().parent
    env_path = root / ".venv"
    python = env_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Preparando o ambiente Python local…", flush=True)
        venv.EnvBuilder(with_pip=True).create(env_path)
    try:
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(root / "requirements.txt")], cwd=root, check=True)
        subprocess.run([str(python), "-m", "streamlit", "run", "app.py", "--server.address", "127.0.0.1", "--server.port", str(args.porta),
                        "--server.headless", str(args.sem_navegador).lower(), "--browser.gatherUsageStats", "false"], cwd=root, check=True)
    except KeyboardInterrupt:
        print("\nAplicativo encerrado. Os dados continuam salvos localmente.")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc


if __name__ == "__main__":
    main()
