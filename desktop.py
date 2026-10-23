"""Executável desktop: controlador nativo e servidor local isolado em subprocesso."""
import argparse
import asyncio
from datetime import datetime, timedelta
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener
import webbrowser


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def user_root():
    if os.environ.get("DOCE_ATELIE_HOME"):
        return Path(os.environ["DOCE_ATELIE_HOME"]).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DoceAtelie"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "doce-atelie"


def prepare_data():
    root = user_root()
    for folder in ("dados", "midia", "logs"):
        (root / folder).mkdir(parents=True, exist_ok=True)
    os.environ["CONFEITARIA_DATA_DIR"] = str(root / "dados")
    os.environ["CONFEITARIA_MEDIA_DIR"] = str(root / "midia")
    # Streamlit precisa de uma pasta gravável mesmo quando instalado em Program Files.
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    return root


def available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def local_url(port):
    return f"http://127.0.0.1:{int(port)}/doce-atelie/"


def is_ready(port):
    try:
        # Requisições ao próprio computador nunca passam por proxies configurados.
        with build_opener(ProxyHandler({})).open(local_url(port) + "_stcore/health", timeout=.4) as response:
            return response.status == 200 and response.read(16) == b"ok"
    except (OSError, URLError):
        return False


class InstanceLock:
    """O SO libera a trava automaticamente mesmo após uma falha do aplicativo."""
    def __init__(self, path):
        self.path = Path(path)
        self.file = None

    def acquire(self):
        self.file = self.path.open("a+b")
        self.file.seek(0, 2)
        if self.file.tell() == 0:
            self.file.write(b"0")
            self.file.flush()
        self.file.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            self.file = None
            return False
        return True

    def release(self):
        if self.file:
            if os.name == "nt":
                import msvcrt
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def worker_command(port, stop_file):
    command = [sys.executable]
    if not getattr(sys, "frozen", False):
        command.append(str(Path(__file__).resolve()))
    return command + ["--serve", "--porta", str(port), "--stop-file", str(stop_file)]


def serve(port, stop_file):
    root = prepare_data()
    log = (root / "logs" / "servidor.log").open("a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stderr = log
    app = resource_root() / "app.py"
    # Não alterar cwd para a pasta instalada: bibliotecas podem tentar gravar nela.
    os.chdir(root)
    sys.path.insert(0, str(resource_root()))
    sys.argv = [str(app)]
    from streamlit.web import bootstrap
    from streamlit.web.server import Server

    bootstrap.load_config_options({
        "server.address": "127.0.0.1", "server.port": port, "server.headless": True,
        "server.baseUrlPath": "doce-atelie", "server.fileWatcherType": "none", "server.runOnSave": False,
        "server.maxUploadSize": 10, "browser.gatherUsageStats": False, "global.developmentMode": False,
        "theme.primaryColor": "#d86b52", "theme.backgroundColor": "#f5f6f8",
        "theme.secondaryBackgroundColor": "#eef1f4", "theme.textColor": "#243346", "client.toolbarMode": "minimal",
    })
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    async def run():
        server = Server(str(app), is_hello=False)
        await server.start()
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGINT, signal.SIGTERM):
            signal.signal(signum, lambda *_: loop.call_soon_threadsafe(server.stop))

        async def watch_stop():
            while not stop_file.exists():
                await asyncio.sleep(.25)
            server.stop()

        watcher = asyncio.create_task(watch_stop())
        try:
            await server.stopped
        finally:
            watcher.cancel()

    try:
        asyncio.run(run())
    finally:
        log.flush()


def diagnostic(output):
    """Smoke test do binário em banco temporário, sem tocar nos dados do cliente."""
    from confeitaria.domain import make_line
    from confeitaria.pdf import generate_pdf
    from confeitaria.storage import Store
    from PIL import Image
    from io import BytesIO

    with tempfile.TemporaryDirectory() as temp:
        data = Store(Path(temp) / "dados", Path(temp) / "midia")
        customer = data.save_customer({"name": "Teste de empacotamento", "phone": "92999999999", "cpf": "", "address": "", "photo": ""})
        product = next(p for p in data.list("products") if p["name"] == "Bolo Simples")
        raw = BytesIO()
        Image.new("RGB", (80, 80), "pink").save(raw, "PNG")
        photo = data.save_image(raw)
        quote_id = data.save_quote({"customer_id": customer, "event_at": (datetime.now() + timedelta(days=10)).isoformat(),
                                   "fulfillment": "Retirada", "delivery_address": "", "lines": [make_line(product, 2, ["Ninho"])],
                                   "payment_method": "PIX", "pix_enabled": False, "pix_percent": "0", "discount_cents": 0,
                                   "delivery_cents": 0, "notes": "", "production_notes": "Teste", "reference_photo": photo})
        data.add_payment(quote_id, 7500, "PIX")
        quote = data.quotes()[0]
        assert quote["balance_cents"] == 7500 and quote["status"] == "Aprovado / Data Reservada"
        for kitchen in (False, True):
            pdf = generate_pdf(quote, data, kitchen)
            assert pdf.startswith(b"%PDF") and len(pdf) > 1000
        assert data.backup().startswith(b"PK")
    output.write_text(json.dumps({"status": "ok", "checks": ["sqlite", "imagens", "orcamento", "sinal", "pdf_cliente", "pdf_cozinha", "backup"], "app_exists": (resource_root() / "app.py").is_file()}), encoding="utf-8")


def launch():
    import tkinter as tk
    from tkinter import messagebox, ttk

    root_path = prepare_data()
    logging.basicConfig(filename=root_path / "logs" / "aplicativo.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    window = tk.Tk()
    window.title("Doce Ateliê · Confeitaria")
    window.geometry("480x350")
    window.resizable(False, False)
    window.configure(bg="#fcfaf7")
    icon = resource_root() / "assets" / "doce-atelie.ico"
    if sys.platform == "win32" and icon.exists():
        window.iconbitmap(str(icon))
    lock = InstanceLock(root_path / "aplicativo.lock")
    if not lock.acquire():
        try:
            state = json.loads((root_path / "sessao.json").read_text(encoding="utf-8"))
            port = int(state["port"])
            if 1 <= port <= 65535 and is_ready(port):
                webbrowser.open(local_url(port))
            else:
                messagebox.showinfo("Doce Ateliê", "O sistema já está iniciando. Aguarde a janela existente.")
        except (OSError, ValueError, KeyError):
            messagebox.showinfo("Doce Ateliê", "O sistema já está aberto ou iniciando.")
        window.destroy()
        return
    port = available_port()
    stop_file = root_path / "encerrar-servidor"
    stop_file.unlink(missing_ok=True)
    process = None
    try:
        process = subprocess.Popen(worker_command(port, stop_file), cwd=root_path,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        (root_path / "sessao.json").write_text(json.dumps({"port": port}), encoding="utf-8")
        tk.Label(window, text="Doce Ateliê", bg="#fcfaf7", fg="#603c49", font=("Georgia", 28)).pack(pady=(30, 5))
        tk.Label(window, text="Gestão da sua confeitaria", bg="#fcfaf7", fg="#7d6e70", font=("Segoe UI", 12)).pack()
        status = tk.StringVar(value="Preparando o sistema…")
        tk.Label(window, textvariable=status, bg="#fcfaf7", fg="#603c49", wraplength=430).pack(pady=20)
        open_button = ttk.Button(window, text="Abrir sistema", state="disabled", command=lambda: webbrowser.open(local_url(port)))
        open_button.pack(ipadx=45, ipady=8)

        def open_folder():
            if os.name == "nt":
                os.startfile(root_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(root_path)])
            else:
                subprocess.Popen(["xdg-open", str(root_path)])

        ttk.Button(window, text="Abrir pasta de dados e backups", command=open_folder).pack(pady=12)
        tk.Label(window, text="Mantenha esta janela aberta enquanto utiliza o sistema.", bg="#fcfaf7", fg="#7d6e70", font=("Segoe UI", 9)).pack()
        started = time.monotonic()

        def poll():
            if process.poll() is not None:
                status.set("Não foi possível iniciar. Consulte a pasta logs.")
                messagebox.showerror("Falha na inicialização", f"Não foi possível iniciar o sistema.\nConsulte os arquivos em:\n{root_path / 'logs'}")
            elif is_ready(port):
                status.set("Pronto para usar. Seus dados são salvos neste computador.")
                open_button.config(state="normal")
                webbrowser.open(local_url(port))
            elif time.monotonic() - started > 120:
                status.set("A inicialização demorou mais que o esperado. Consulte os logs.")
            else:
                window.after(300, poll)

        def close():
            if messagebox.askyesno("Encerrar Doce Ateliê", "Encerrar o sistema? Salve o pedido em edição antes de continuar."):
                window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        window.after(300, poll)
        window.mainloop()
    except Exception:
        logging.exception("Falha no inicializador")
        messagebox.showerror("Doce Ateliê", f"Ocorreu uma falha. Consulte os logs em {root_path / 'logs'}.")
    finally:
        if process and process.poll() is None:
            stop_file.touch()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=5)
        (root_path / "sessao.json").unlink(missing_ok=True)
        lock.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--porta", type=int)
    parser.add_argument("--stop-file", type=Path)
    parser.add_argument("--diagnostico", type=Path)
    parser.add_argument("--notificar", action="store_true")
    parser.add_argument("--dados", type=Path)
    parser.add_argument("--midia", type=Path)
    args = parser.parse_args()
    if args.notificar:
        if not args.dados and not os.environ.get("CONFEITARIA_DATA_DIR"):
            prepare_data()
        from confeitaria.storage import Store
        from confeitaria.notifications import check_reminders
        check_reminders(Store(args.dados, args.midia))
    elif args.diagnostico:
        diagnostic(args.diagnostico)
    elif args.serve:
        if args.porta is None or not 1 <= args.porta <= 65535 or args.stop_file is None:
            parser.error("Informe uma porta válida e --stop-file para o servidor.")
        serve(args.porta, args.stop_file)
    else:
        launch()


if __name__ == "__main__":
    main()
