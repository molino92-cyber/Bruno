from contextlib import closing
from datetime import datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import URLError

from PIL import Image
from pypdf import PdfReader

from confeitaria.demo import demonstration_store
from confeitaria.domain import make_line
from confeitaria.pdf import generate_pdf
from confeitaria.postal import lookup_postal_code
from confeitaria.storage import Store


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root/"dados", self.root/"midia")
        self.products = self.store.list("products")

    def tearDown(self):
        self.temp.cleanup()

    def test_weight_fillings_and_negotiated_exceptions_on_both_cake_types(self):
        for name, fillings in [("Bolo Simples", ["Ninho","Chocolate","Dois Amores"]), ("Bolo Especial", ["Nutella","Ninho com Morango","Ninho com Nutella"])]:
            product = next(p for p in self.products if p["name"]==name)
            for weight in [1,1.5]:
                with self.assertRaisesRegex(ValueError,"mínimo 2 kg"):
                    make_line(product,weight,fillings[:1])
                with self.assertRaisesRegex(ValueError,"motivo"):
                    make_line(product,weight,fillings[:1],allow_under_minimum=True)
                approved = make_line(product,weight,fillings[:1],allow_under_minimum=True,negotiation_notes="Autorizado pela confeiteira.")
                self.assertTrue(approved["negotiation"]["under_minimum"])
                with self.assertRaisesRegex(ValueError,"padrão"):
                    make_line(product,weight,fillings[:2],allow_under_minimum=True,negotiation_notes="Teste")
            self.assertFalse(make_line(product,2,fillings[:2])["negotiation"]["extra_fillings"])
            with self.assertRaisesRegex(ValueError,"padrão"):
                make_line(product,2,fillings)
            approved=make_line(product,2,fillings,allow_extra_fillings=True,negotiation_notes="Terceiro recheio combinado.")
            self.assertTrue(approved["negotiation"]["extra_fillings"])

    def test_brigadeiro_flavors_and_additional_unit_calculation(self):
        cake=next(p for p in self.products if p["name"]=="Bolo Simples")
        extra={"name":"Brigadeiros no Topo","amount_cents":3000,"quantity":10,"unit_cents":300,"gift":False,"brigadeiro_type":"Especial","flavors":["Nutella"]}
        line=make_line(cake,2,["Ninho"],[extra])
        self.assertEqual(line["total_cents"],18000)
        self.assertEqual(line["extras"][0]["quantity"],10)
        with self.assertRaisesRegex(ValueError,"total do adicional"):
            make_line(cake,2,["Ninho"],[dict(extra,amount_cents=300)])
        product=next(p for p in self.products if p["category"]=="Cento de Brigadeiros")
        for kind,flavors,details in [("Tradicional",["Nutella"],""),("Personalizado",["Chocolate"],"")]:
            with self.assertRaises(ValueError):
                make_line(product,1,brigadeiro_type=kind,flavors=flavors,details=details,gift=True)
        self.assertEqual(make_line(product,1,brigadeiro_type="Tradicional",flavors=["Chocolate","Beijinho"],split=True,gift=True)["flavors"],["Chocolate","Beijinho"])

    def test_demo_isolated_idempotent_and_includes_illustrated_kits(self):
        demo=demonstration_store(self.store)
        self.assertEqual(len(self.store.list("customers")),0)
        self.assertEqual(len(demo.list("customers")),6)
        self.assertEqual(len(demo.quotes()),6)
        self.assertTrue(all(p["photos"] and demo.image_path(p["photos"][0]) for p in demo.list("products")))
        self.assertEqual(len([p for p in demo.list("products") if p["category"]=="Kits Festa"]),4)
        self.assertEqual(next(p for p in self.products if p["name"]=="Cupcake")["price_cents"],0)
        self.assertEqual(len(demonstration_store(self.store).quotes()),6)

    def test_catalog_upgrade_preserves_custom_prices_descriptions_and_old_quotes(self):
        with self.store.db() as db:
            db.execute("DELETE FROM settings WHERE key='catalog_v3'")
            db.execute("UPDATE products SET price_cents=12345,description='Receita da família' WHERE name='Bolo Simples'")
            db.execute("UPDATE products SET name='Kit Festa',description='Cadastre a descrição e o preço antes de vender.',price_cents=34567 WHERE name='Kit Festa 1'")
        reloaded=Store(self.root/"dados",self.root/"midia")
        simple=next(p for p in reloaded.list("products") if p["name"]=="Bolo Simples")
        kit=next(p for p in reloaded.list("products") if p["name"]=="Kit Festa 1")
        self.assertEqual((simple["description"],simple["price_cents"]),("Receita da família",12345))
        self.assertEqual(kit["price_cents"],34567)
        self.assertEqual(len(kit["composition"]),3)

    def test_logo_reference_and_negotiation_in_pdfs_preserve_payments(self):
        client=self.store.save_customer({"name":"Cliente PDF","phone":"92999998888"})
        def image(color,size):
            data=BytesIO();Image.new("RGB",size,color).save(data,"PNG");return self.store.save_image(data)
        reference=image("pink",(40,300))
        logo=image("navy",(400,80))
        cake=next(p for p in self.products if p["name"]=="Bolo Especial")
        line=make_line(cake,1.5,["Nutella"],allow_under_minimum=True,negotiation_notes="Exceção de peso aprovada.",reference_photo=reference)
        identifier=self.store.save_quote({"customer_id":client,"event_at":(datetime.now()+timedelta(days=10)).isoformat(timespec="minutes"),"fulfillment":"Retirada","delivery_address":"","lines":[line],"payment_method":"PIX","pix_enabled":False,"pix_percent":"0","discount_cents":0,"delivery_cents":0,"notes":"","production_notes":"Sem castanhas.","reference_photo":""})
        self.store.add_payment(identifier,6375,"PIX")
        before=self.store.quotes()[0]
        self.store.update_quote_logo(identifier,logo)
        quote=self.store.quotes()[0]
        self.assertEqual(before["totals"],quote["totals"])
        self.assertEqual(quote["paid_cents"],6375)
        kitchen=PdfReader(BytesIO(generate_pdf(quote,self.store,True)))
        self.assertGreaterEqual(sum(len(p.images) for p in kitchen.pages),2)
        text=" ".join(p.extract_text() for p in kitchen.pages)
        self.assertIn("Exceção de peso aprovada",text)
        self.assertNotIn("R$",text)
        commercial=PdfReader(BytesIO(generate_pdf(quote,self.store)))
        self.assertGreaterEqual(sum(len(p.images) for p in commercial.pages),1)


class PostalTests(unittest.TestCase):
    def response(self,payload):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(payload).encode()
        return response

    def test_validated_address_and_timeout(self):
        with patch("confeitaria.postal.urlopen",return_value=self.response({"logradouro":"Praça da Sé","bairro":"Sé","localidade":"São Paulo","uf":"SP"})) as fetch:
            result=lookup_postal_code("01001-000")
            self.assertEqual(result["street"],"Praça da Sé")
            self.assertEqual(result["state"],"SP")
            self.assertEqual(result["postal_code"],"01001000")
            self.assertEqual(fetch.call_args.kwargs["timeout"],6)
            self.assertEqual(fetch.call_args.args[0].full_url,"https://viacep.com.br/ws/01001000/json/")

    def test_invalid_missing_and_unavailable_addresses(self):
        for code in ["123","0000A000","https://example.com"]:
            with self.assertRaisesRegex(ValueError,"CEP válido"):
                lookup_postal_code(code)
        with patch("confeitaria.postal.urlopen",return_value=self.response({"erro":True})):
            with self.assertRaisesRegex(ValueError,"não encontrado"):
                lookup_postal_code("99999999")
        with patch("confeitaria.postal.urlopen",side_effect=URLError("offline")):
            with self.assertRaisesRegex(ValueError,"manualmente"):
                lookup_postal_code("01001000")


if __name__=="__main__":
    unittest.main()
