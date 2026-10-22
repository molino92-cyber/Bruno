import json
from io import BytesIO
import os
import re
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import tornado.httpclient
import tornado.httpserver
import tornado.netutil
from tornado.testing import AsyncHTTPTestCase, gen_test
import tornado.web
import tornado.websocket

from mobile import make_application


class Echo(tornado.web.RequestHandler):
    def get(self,path):
        self.set_header("Content-Type","text/plain")
        self.write("backend:"+path)
    def post(self,path):
        self.write(self.request.body)
    def put(self,path):
        self.set_header("X-Uploaded-Length",str(len(self.request.body)))
        self.set_status(204)


class EchoStream(tornado.websocket.WebSocketHandler):
    def check_origin(self,origin):
        return True
    def select_subprotocol(self,subprotocols):
        return "streamlit"
    def on_message(self,message):
        self.write_message(message,binary=isinstance(message,bytes))


class MobileTests(AsyncHTTPTestCase):
    def setUp(self):
        self.brand_data = tempfile.TemporaryDirectory()
        self.brand_env = patch.dict(os.environ, {"CONFEITARIA_DATA_DIR": self.brand_data.name + "/dados", "CONFEITARIA_MEDIA_DIR": self.brand_data.name + "/midia"})
        self.brand_env.start()
        super().setUp()

    def get_app(self):
        self.password="senha-de-teste-segura"
        self.secret="chave-de-teste-"*5
        sockets=tornado.netutil.bind_sockets(0,"127.0.0.1")
        port=sockets[0].getsockname()[1]
        backend=tornado.web.Application([(r"/sistema/_stcore/stream",EchoStream),(r"/sistema/(.*)",Echo)])
        self.backend_server=tornado.httpserver.HTTPServer(backend)
        self.backend_server.add_sockets(sockets)
        return make_application(f"http://127.0.0.1:{port}",self.password,self.secret,"http://localhost")

    def tearDown(self):
        self.backend_server.stop()
        self.io_loop.run_sync(self.backend_server.close_all_connections)
        super().tearDown()
        self.brand_env.stop()
        self.brand_data.cleanup()

    def test_identity_follows_saved_shop_and_requires_login(self):
        from PIL import Image
        from confeitaria.storage import Store
        store = Store()
        image = BytesIO()
        Image.new("RGB", (1000, 100), "#d86b52").save(image, "PNG")
        settings = store.settings()
        settings.update(name='Doces & Afeto <Loja>', logo=store.save_image(image))
        store.save_settings(settings)
        self.assertEqual(self.fetch("/identidade", follow_redirects=False).code, 302)
        response = self.fetch("/identidade", headers={"Cookie": self.cookie()})
        brand = json.loads(response.body)
        self.assertEqual(brand["name"], settings["name"])
        self.assertTrue(brand["logo"].startswith("data:image/png;base64,"))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        settings["logo"] = ""
        store.save_settings(settings)
        self.assertEqual(json.loads(self.fetch("/identidade", headers={"Cookie": self.cookie()}).body)["logo"], "")

    def cookie(self):
        signed=tornado.web.create_signed_value(self.secret,"doce_session","owner").decode()
        return "doce_session="+signed

    def test_requires_authentication_for_application_and_documents(self):
        home=self.fetch("/",follow_redirects=False)
        self.assertEqual(home.code,302)
        self.assertIn("/entrar",home.headers["Location"])
        for path in ["/sistema/","/sistema/media/document.pdf","/sistema/_stcore/upload_file/test"]:
            self.assertEqual(self.fetch(path).code,401)
        response=self.fetch("/",headers={"Cookie":self.cookie()})
        self.assertEqual(response.code,200)
        self.assertIn(b'iframe',response.body)
        self.assertEqual(response.headers["Cache-Control"],"no-store")

    def test_login_csrf_correct_password_wrong_password_and_logout(self):
        page=self.fetch("/entrar")
        token=re.search(rb'name="_xsrf" value="([^"]+)"',page.body).group(1).decode()
        cookie=next(v.split(";",1)[0] for v in page.headers.get_list("Set-Cookie") if v.startswith("_xsrf="))
        self.assertEqual(self.fetch("/entrar",method="POST",body=urlencode({"password":self.password})).code,403)
        for password,expected in [("senha-errada",401),(self.password,302)]:
            response=self.fetch("/entrar",method="POST",body=urlencode({"password":password,"_xsrf":token}),headers={"Cookie":cookie},follow_redirects=False)
            self.assertEqual(response.code,expected)
        session=next(value.split(";",1)[0] for value in response.headers.get_list("Set-Cookie") if value.startswith("doce_session="))
        self.assertIn("HttpOnly",response.headers.get("Set-Cookie"))
        self.assertEqual(self.fetch("/",headers={"Cookie":session}).code,200)
        logout=self.fetch("/sair",method="POST",body=urlencode({"_xsrf":token}),headers={"Cookie":cookie+"; "+session},follow_redirects=False)
        self.assertEqual(logout.code,302)

    def test_login_throttles_repeated_failures(self):
        page=self.fetch("/entrar")
        token=re.search(rb'name="_xsrf" value="([^"]+)"',page.body).group(1).decode()
        cookie=next(v.split(";",1)[0] for v in page.headers.get_list("Set-Cookie") if v.startswith("_xsrf="))
        for _ in range(8):
            self.assertEqual(self.fetch("/entrar",method="POST",body=urlencode({"password":"errada","_xsrf":token}),headers={"Cookie":cookie}).code,401)
        self.assertEqual(self.fetch("/entrar",method="POST",body=urlencode({"password":self.password,"_xsrf":token}),headers={"Cookie":cookie}).code,429)

    def test_proxy_supports_downloads_and_uploads_without_caching(self):
        response=self.fetch("/sistema/media/document.pdf",headers={"Cookie":self.cookie()})
        self.assertEqual(response.body,b"backend:media/document.pdf")
        self.assertEqual(response.headers["Cache-Control"],"no-store")
        response=self.fetch("/sistema/_stcore/upload_file/file",method="POST",body=b"imagem-de-teste",headers={"Cookie":self.cookie(),"Content-Type":"application/octet-stream"})
        self.assertEqual(response.body,b"imagem-de-teste")
        response=self.fetch("/sistema/_stcore/upload_file/file",method="PUT",body=b"imagem-de-teste",headers={"Cookie":self.cookie(),"Content-Type":"application/octet-stream"})
        self.assertEqual(response.code,204)
        self.assertEqual(response.body,b"")
        self.assertEqual(response.headers["X-Uploaded-Length"],str(len(b"imagem-de-teste")))

    def test_install_manifest_icons_and_private_cache_exclusion(self):
        manifest=json.loads(self.fetch("/manifest.webmanifest").body)
        self.assertEqual(manifest["display"],"standalone")
        for icon in manifest["icons"]:
            response=self.fetch(icon["src"])
            self.assertEqual(response.code,200)
            self.assertEqual(response.headers["Content-Type"],"image/png")
        worker=self.fetch("/sw.js")
        self.assertIn(b"url.pathname.startsWith('/sistema/')",worker.body)
        self.assertEqual(worker.headers["Service-Worker-Allowed"],"/")
        self.assertEqual(self.fetch("/../mobile.py").code,404)

    @gen_test
    async def test_websocket_authentication_origin_and_bidirectional_binary_messages(self):
        url=self.get_url("/sistema/_stcore/stream").replace("http://","ws://")
        for headers in [{"Origin":"http://localhost"},{"Origin":"https://outra-loja.example","Cookie":self.cookie()}]:
            with self.assertRaises(tornado.httpclient.HTTPClientError):
                await tornado.websocket.websocket_connect(tornado.httpclient.HTTPRequest(url,headers=headers),subprotocols=["streamlit"])
        socket=await tornado.websocket.websocket_connect(tornado.httpclient.HTTPRequest(url,headers={"Origin":"http://localhost","Cookie":self.cookie()}),subprotocols=["streamlit"])
        try:
            await socket.write_message(b"mensagem-streamlit",binary=True)
            self.assertEqual(await socket.read_message(),b"mensagem-streamlit")
            await socket.write_message("texto")
            self.assertEqual(await socket.read_message(),"texto")
        finally:
            socket.close()

    def test_rejects_short_password_and_non_https_remote_site(self):
        with self.assertRaises(ValueError):
            make_application("http://localhost:8501","123",self.secret,"https://doces.example")
        with self.assertRaises(ValueError):
            make_application("http://localhost:8501",self.password,self.secret,"http://doces.example")


if __name__=="__main__":
    unittest.main()
