"""Valida o binário real: SQLite, PDFs e execução da interface via WebSocket."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import ProxyHandler, build_opener

from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg
from tornado.httpclient import HTTPRequest
from tornado.websocket import websocket_connect


async def check_interface(port):
    url = f"ws://127.0.0.1:{port}/doce-atelie/_stcore/stream"
    request = HTTPRequest(url, headers={"Origin": f"http://127.0.0.1:{port}"}, connect_timeout=10)
    ws = await websocket_connect(request, subprotocols=["streamlit"])
    request_msg = BackMsg()
    request_msg.rerun_script.query_string = ""
    await ws.write_message(request_msg.SerializeToString(), binary=True)
    deltas = 0
    try:
        while True:
            raw = await asyncio.wait_for(ws.read_message(), timeout=30)
            if raw is None:
                raise RuntimeError("A conexão fechou antes de concluir a execução da interface.")
            message = ForwardMsg()
            message.ParseFromString(raw)
            kind = message.WhichOneof("type")
            if kind == "delta":
                deltas += 1
                if message.delta.HasField("new_element") and message.delta.new_element.HasField("exception"):
                    raise RuntimeError(f"Falha na interface empacotada: {message.delta.new_element.exception.message}")
            if kind == "script_finished":
                if deltas == 0:
                    raise RuntimeError("O aplicativo não renderizou elementos.")
                return deltas
    finally:
        ws.close()


def check_bundle(executable):
    executable = Path(executable).resolve()
    command = ([sys.executable, str(executable)] if executable.suffix == ".py" else [str(executable)])
    with tempfile.TemporaryDirectory() as folder:
        temp = Path(folder)
        output = temp / "diagnostico.json"
        env = dict(os.environ, DOCE_ATELIE_HOME=str(temp / "perfil"))
        result = subprocess.run(command + ["--diagnostico", str(output)], env=env, timeout=90)
        if result.returncode or not output.exists():
            raise RuntimeError("O diagnóstico interno do executável falhou.")
        checks = json.loads(output.read_text(encoding="utf-8"))
        if checks["status"] != "ok" or not checks["app_exists"]:
            raise RuntimeError(f"Diagnóstico incompleto: {checks}")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        stop_file = temp / "parar"
        process = subprocess.Popen(command + ["--serve", "--porta", str(port), "--stop-file", str(stop_file)], env=env)
        try:
            deadline = time.monotonic() + 90
            opener = build_opener(ProxyHandler({}))
            while True:
                try:
                    with opener.open(f"http://127.0.0.1:{port}/doce-atelie/_stcore/health", timeout=1) as response:
                        if response.read() == b"ok":
                            break
                except OSError:
                    pass
                if process.poll() is not None or time.monotonic() > deadline:
                    log = temp / "perfil" / "logs" / "servidor.log"
                    raise RuntimeError("Servidor não iniciou.\n" + (log.read_text(encoding="utf-8")[-6000:] if log.exists() else "Sem log."))
                time.sleep(.2)
            deltas = asyncio.run(check_interface(port))
            stop_file.touch()
            process.wait(timeout=15)
            if process.returncode:
                raise RuntimeError(f"Encerramento retornou {process.returncode}.")
            print(f"OK: diagnóstico, PDFs, SQLite, interface ({deltas} elementos) e encerramento limpo.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    check_bundle(sys.argv[1])
