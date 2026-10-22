"""Valida o servidor móvel real sem gravar clientes ou dados de produção."""
import argparse
from http.cookiejar import CookieJar
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, Request, build_opener


def check_server(url):
    base=url.rstrip("/")
    client=build_opener(ProxyHandler({}),HTTPCookieProcessor(CookieJar()))
    ready=False
    for _ in range(30):
        try:
            with client.open(base+"/saude",timeout=2) as response:
                ready=response.read()==b"ok"
            if ready:
                break
        except (URLError,OSError):
            pass
        time.sleep(1)
    if not ready:
        raise RuntimeError("O servidor móvel não ficou pronto.")
    for path in ["/sistema/","/sistema/media/exemplo.pdf"]:
        try:
            client.open(base+path,timeout=5)
            raise AssertionError("O sistema precisa exigir autenticação.")
        except HTTPError as exc:
            assert exc.code==401
    with client.open(base+"/manifest.webmanifest",timeout=5) as response:
        assert json.load(response)["display"]=="standalone"
    with client.open(base+"/entrar",timeout=5) as response:
        token=re.search(rb'name="_xsrf" value="([^"]+)"',response.read()).group(1).decode()
    password=os.environ["DOCE_MOBILE_PASSWORD"]
    data=urlencode({"_xsrf":token,"password":password}).encode()
    with client.open(Request(base+"/entrar",data=data),timeout=5) as response:
        assert b'<iframe' in response.read()
    with client.open(base+"/sistema/",timeout=5) as response:
        assert response.status==200 and b"<html" in response.read().lower()
    with client.open(base+"/sistema/_stcore/health",timeout=5) as response:
        assert response.read()==b"ok"
    print("OK: servidor móvel real, autenticação, manifesto, proxy e Streamlit privado.")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("url",nargs="?",default="http://localhost:8080")
    check_server(parser.parse_args().url)
