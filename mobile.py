"""Entrada web instalável no Android/iOS, com autenticação e proxy privado do Streamlit."""
import argparse
import asyncio
import base64
from collections import defaultdict, deque
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit

import tornado.httpclient
import tornado.httputil
import tornado.web
import tornado.websocket

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web" / "mobile"
HOP_HEADERS = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade", "content-length", "host"}


class Base(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header("Cache-Control", "no-store")
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Referrer-Policy", "same-origin")
        self.set_header("X-Frame-Options", "SAMEORIGIN")

    def get_current_user(self):
        return self.get_secure_cookie("doce_session", max_age_days=8/24) == b"owner"


class Home(Base):
    @tornado.web.authenticated
    def get(self):
        self.render(str(WEB / "index.html"))


class Identity(Base):
    @tornado.web.authenticated
    def get(self):
        from io import BytesIO
        from PIL import Image, ImageOps
        from confeitaria.storage import Store
        store = Store()
        settings = store.settings()
        logo = ""
        path = store.image_path(settings["logo"])
        if path:
            with Image.open(path) as image:
                thumb = ImageOps.exif_transpose(image).convert("RGBA")
                thumb.thumbnail((192, 192))
                output = BytesIO()
                thumb.save(output, "PNG")
            logo = "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
        self.write({"name": settings["name"], "logo": logo})


class Login(Base):
    def get(self):
        if self.current_user:
            self.redirect("/")
            return
        self.render(str(WEB / "login.html"), error="")

    def post(self):
        attempts = self.settings["attempts"][self.request.remote_ip]
        now = time.monotonic()
        while attempts and attempts[0] < now - 300:
            attempts.popleft()
        if len(attempts) >= 8:
            self.set_status(429)
            self.render(str(WEB / "login.html"), error="Muitas tentativas. Aguarde cinco minutos antes de tentar novamente.")
            return
        password = self.get_body_argument("password", "")
        candidate = hashlib.sha256(password.encode()).digest()
        if not hmac.compare_digest(candidate, self.settings["password_digest"]):
            attempts.append(now)
            self.set_status(401)
            self.render(str(WEB / "login.html"), error="Senha incorreta. Confira e tente novamente.")
            return
        attempts.clear()
        self.set_secure_cookie("doce_session", "owner", expires_days=None, httponly=True,
                               secure=self.settings["secure_cookies"], samesite="Strict")
        self.redirect("/")


class Logout(Base):
    def post(self):
        self.clear_cookie("doce_session")
        self.redirect("/entrar")


class Health(Base):
    async def get(self):
        try:
            response = await tornado.httpclient.AsyncHTTPClient().fetch(self.settings["backend"] + "/sistema/_stcore/health", request_timeout=2)
            self.write("ok" if response.code == 200 else "iniciando")
        except tornado.httpclient.HTTPClientError:
            self.set_status(503)
            self.write("iniciando")


class PublicFile(tornado.web.StaticFileHandler):
    def set_extra_headers(self, path):
        self.set_header("X-Content-Type-Options", "nosniff")
        if path.endswith("sw.js"):
            self.set_header("Cache-Control", "no-cache")
            self.set_header("Service-Worker-Allowed", "/")


class Proxy(Base):
    def check_xsrf_cookie(self):
        # O Streamlit valida seu próprio token XSRF nos uploads e chamadas internas.
        pass

    async def prepare(self):
        if not self.current_user:
            self.set_status(401)
            self.finish("Sessão encerrada. Entre novamente pela tela inicial.")

    async def forward(self, path=""):
        headers = tornado.httputil.HTTPHeaders()
        for name, value in self.request.headers.get_all():
            if name.lower() not in HOP_HEADERS and name.lower() not in {"accept-encoding", "origin", "x-forwarded-for", "x-forwarded-proto", "x-forwarded-host"}:
                headers.add(name, value)
        headers["Origin"] = self.settings["backend"]
        request = tornado.httpclient.HTTPRequest(self.settings["backend"] + self.request.uri,
                    method=self.request.method, headers=headers, body=self.request.body if self.request.method in {"POST", "PUT", "PATCH"} else None,
                    follow_redirects=False, request_timeout=90, decompress_response=True)
        try:
            response = await tornado.httpclient.AsyncHTTPClient().fetch(request, raise_error=False)
        except tornado.httpclient.HTTPClientError:
            self.set_status(503)
            self.finish("O sistema está iniciando. Aguarde alguns segundos e recarregue a página.")
            return
        self.set_status(response.code)
        for name, value in response.headers.get_all():
            if name.lower() not in HOP_HEADERS | {"content-encoding", "cache-control", "expires"}:
                self.add_header(name, value) if name.lower() == "set-cookie" else self.set_header(name, value)
        if response.code in {204, 304} or self.request.method == "HEAD":
            self.finish()
        else:
            self.finish(response.body)

    get = post = put = patch = delete = head = options = forward


class Stream(tornado.websocket.WebSocketHandler):
    def prepare(self):
        if self.get_secure_cookie("doce_session", max_age_days=8/24) != b"owner":
            raise tornado.web.HTTPError(401)

    def check_origin(self, origin):
        return origin == self.settings["public_origin"]

    def select_subprotocol(self, subprotocols):
        return "streamlit" if "streamlit" in subprotocols else None

    async def open(self):
        self.backend_connection = None
        self.pending = []
        origin = self.settings["backend"]
        protocols = [part.strip() for part in self.request.headers.get("Sec-WebSocket-Protocol", "").split(",") if part.strip()]
        headers = {"Origin": origin, "Cookie": self.request.headers.get("Cookie", "")}
        request = tornado.httpclient.HTTPRequest(origin.replace("http://", "ws://", 1) + self.request.uri, headers=headers)
        try:
            connection = await tornado.websocket.websocket_connect(request, subprotocols=protocols, max_message_size=50*1024*1024)
        except (OSError, tornado.httpclient.HTTPClientError):
            self.close(1013, "Servidor iniciando. Tente novamente.")
            return
        self.backend_connection = connection
        if self.ws_connection is None:
            connection.close()
            return
        for message in self.pending:
            await connection.write_message(message, binary=isinstance(message, bytes))
        self.pending.clear()
        self.relay_task = asyncio.create_task(self.relay(connection))

    async def relay(self, connection):
        try:
            while True:
                message = await connection.read_message()
                if message is None:
                    break
                await self.write_message(message, binary=isinstance(message, bytes))
        except tornado.websocket.WebSocketClosedError:
            pass
        finally:
            connection.close()
            self.close()

    async def on_message(self, message):
        connection = getattr(self, "backend_connection", None)
        if connection:
            try:
                await connection.write_message(message, binary=isinstance(message, bytes))
            except tornado.websocket.WebSocketClosedError:
                self.close()
        elif len(getattr(self, "pending", [])) < 20:
            self.pending.append(message)
        else:
            self.close(1009, "Servidor ocupado. Reabra o sistema.")

    def on_close(self):
        if getattr(self, "backend_connection", None):
            self.backend_connection.close()


def make_application(backend, password, cookie_secret, public_url):
    public = urlsplit(public_url)
    if len(password) < 12:
        raise ValueError("Defina DOCE_MOBILE_PASSWORD com pelo menos 12 caracteres.")
    if len(cookie_secret) < 32:
        raise ValueError("A chave de sessão deve ter pelo menos 32 caracteres.")
    if public.scheme not in {"http", "https"} or not public.netloc or public.username or public.password or public.path not in {"", "/"} or public.query or public.fragment:
        raise ValueError("DOCE_PUBLIC_URL precisa ser a URL da loja, sem caminho, como https://doces.exemplo.com.")
    if public.scheme != "https" and public.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Use HTTPS para instalar e proteger o acesso no celular.")
    origin = f"{public.scheme}://{public.netloc}"
    return tornado.web.Application([
        (r"/", Home), (r"/identidade", Identity), (r"/entrar", Login), (r"/sair", Logout), (r"/saude", Health),
        (r"/(manifest.webmanifest|sw.js|mobile.js|mobile.css|offline.html|icone-192.png|icone-512.png|apple-touch-icon.png)", PublicFile, {"path":str(WEB)}),
        (r"/sistema/_stcore/stream", Stream), (r"/sistema(?:/(.*))?", Proxy),
    ], backend=backend.rstrip("/"), password_digest=hashlib.sha256(password.encode()).digest(),
       cookie_secret=cookie_secret, public_origin=origin, secure_cookies=public.scheme=="https",
       attempts=defaultdict(deque), login_url="/entrar", xsrf_cookies=True, websocket_max_message_size=50*1024*1024)


async def serve(args):
    password = os.environ.get("DOCE_MOBILE_PASSWORD", "")
    if len(password) < 12:
        raise ValueError("Defina DOCE_MOBILE_PASSWORD com pelo menos 12 caracteres antes de iniciar.")
    data = Path(os.environ.get("CONFEITARIA_DATA_DIR", ROOT / "dados"))
    data.mkdir(parents=True, exist_ok=True)
    secret_path = data / ".mobile-session-key"
    if not secret_path.exists():
        with secret_path.open("x") as destination:
            destination.write(secrets.token_urlsafe(48))
        try:
            secret_path.chmod(0o600)
        except OSError:
            pass
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    backend = f"http://127.0.0.1:{port}"
    public_url = os.environ.get("DOCE_PUBLIC_URL", f"http://localhost:{args.porta}")
    app = make_application(backend, password, secret_path.read_text().strip(), public_url)
    command = [sys.executable, "-m", "streamlit", "run", str(ROOT/"app.py"), "--server.address=127.0.0.1", f"--server.port={port}",
               "--server.baseUrlPath=sistema", "--server.headless=true", "--browser.gatherUsageStats=false"]
    child = subprocess.Popen(command, cwd=ROOT)
    server = None
    stopped = asyncio.Event()
    def stop(*_):
        stopped.set()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, stop)
    try:
        server = app.listen(args.porta, address=args.endereco, max_buffer_size=50*1024*1024,
                            xheaders=True, trusted_downstream=["127.0.0.1", "::1"])
        print(f"Doce Ateliê para celular: {public_url} · aguardando conexões", flush=True)
        while not stopped.is_set():
            if child.poll() is not None:
                raise RuntimeError("O servidor do sistema foi encerrado.")
            try:
                await asyncio.wait_for(stopped.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass
    finally:
        if server:
            server.stop()
            await server.close_all_connections()
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Doce Ateliê · versão web instalável para Android e iOS")
    parser.add_argument("--porta", type=int, default=8080)
    parser.add_argument("--endereco", default="127.0.0.1")
    try:
        asyncio.run(serve(parser.parse_args()))
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
