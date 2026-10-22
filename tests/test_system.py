from contextlib import closing
from datetime import date, datetime, timedelta
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile

from PIL import Image
from pypdf import PdfReader

from confeitaria.domain import active_price, make_line, totals, validate_cpf
from confeitaria.pdf import generate_pdf
from confeitaria.storage import Store, inventory_cost


class ConfeitariaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "dados", self.root / "midia")
        self.client_id = self.store.save_customer({"name": "Ana & João", "phone": "92999998888", "cpf": "", "address": "Rua das Flores, 10", "photo": ""})
        self.products = self.store.list("products")
        self.simple = next(p for p in self.products if p["name"] == "Bolo Simples")
        self.special = next(p for p in self.products if p["name"] == "Bolo Especial")

    def tearDown(self):
        self.temp.cleanup()

    def payload(self, **kwargs):
        result = {"customer_id": self.client_id, "event_at": (datetime.now() + timedelta(days=10)).isoformat(timespec="minutes"),
                  "fulfillment": "Entrega", "delivery_address": "Rua das Flores, 10", "lines": [make_line(self.simple, 2, ["Ninho"])],
                  "payment_method": "PIX", "pix_enabled": False, "pix_percent": "0", "discount_cents": 0, "delivery_cents": 0,
                  "notes": "Transportar com cuidado.", "production_notes": "Decoração rosa. Alergia a castanhas.", "reference_photo": ""}
        result.update(kwargs)
        return result

    def save_quote(self, **kwargs):
        self.store.save_quote(self.payload(**kwargs))
        return self.store.quotes()[-1]

    def test_minimum_and_dynamic_fillings(self):
        self.assertEqual(make_line(self.simple, 2, ["Ninho"])["total_cents"], 15000)
        self.assertEqual(make_line(self.special, "2.5", ["Nutella"])["total_cents"], 21250)
        for product, quantity, fillings in [(self.simple, 1.9, ["Ninho"]), (self.simple, 2, ["Nutella"]), (self.special, 2, ["Ninho"]), (self.simple, 2, [])]:
            with self.assertRaises(ValueError):
                make_line(product, quantity, fillings)

    def test_gifts_and_addons(self):
        extras = [{"name": "Frutas Extras", "amount_cents": 2000, "gift": False}, {"name": "Topo", "amount_cents": 3000, "gift": True}]
        self.assertEqual(make_line(self.simple, 2, ["Chocolate"], extras)["total_cents"], 17000)
        self.assertEqual(make_line(self.simple, 2, ["Chocolate"], extras, gift=True)["total_cents"], 0)

    def test_brigadeiro_split(self):
        product = next(p for p in self.products if p["category"] == "Cento de Brigadeiros")
        product["price_cents"] = 12000
        line = make_line(product, 2, brigadeiro_type="Tradicional", split=True, flavors=["Chocolate", "Beijinho"])
        self.assertTrue(line["split"])
        self.assertEqual(line["total_cents"], 24000)
        with self.assertRaises(ValueError):
            make_line(product, 1, brigadeiro_type="Tradicional", split=True, flavors=["Chocolate"])
        with self.assertRaises(ValueError):
            make_line(product, 1.5, brigadeiro_type="Tradicional", flavors=["Chocolate"])

    def test_promotions_do_not_automatically_enable_pix(self):
        product = dict(self.simple, promo_enabled=1, promo_cents=7000, promo_start=date.today().isoformat(), promo_end=date.today().isoformat())
        self.assertEqual(active_price(product), (7000, True))
        line = make_line(product, 2, ["Ninho"])
        self.assertTrue(line["promotional"])
        self.assertEqual(totals([line], pix_percent=10)["total_cents"], 14000)
        result = totals([line], 1000, 2000, True, 10)
        self.assertEqual(result["pix_discount_cents"], 1300)
        self.assertEqual(result["card_cents"], 15000)
        self.assertEqual(result["total_cents"], 13700)
        yesterday = date.today() - timedelta(days=1)
        self.assertEqual(active_price(product, yesterday), (7500, False))
        with self.assertRaises(ValueError):
            totals([line], pix_enabled=True, pix_percent=5, payment_method="Cartão")

    def test_invalid_discounts_and_rounding(self):
        line = make_line(self.simple, "2.01", ["Ninho"])
        self.assertEqual(line["total_cents"], 15075)
        result = totals([line], pix_enabled=True, pix_percent="3.5")
        self.assertEqual(result["pix_discount_cents"], 528)
        self.assertEqual(result["deposit_cents"], 7274)
        for args in [(16000, 0, False, 0), (0, -1, False, 0), (0, 0, True, 101)]:
            with self.assertRaises(ValueError):
                totals([line], *args)

    def test_unpriced_products_require_configuration(self):
        product = next(p for p in self.products if p["name"] == "Cupcake")
        with self.assertRaises(ValueError):
            make_line(product, 1)
        self.assertEqual(make_line(product, 1, gift=True)["total_cents"], 0)

    def test_quote_snapshot_persistence_and_editing(self):
        q = self.save_quote()
        self.assertEqual(q["status"], "Em Aberto")
        self.assertEqual(q["valid_until"], (date.today() + timedelta(days=7)).isoformat())
        modified = self.simple.copy()
        modified.pop("id")
        modified["price_cents"] = 99999
        self.store.save_product(modified, self.simple["id"])
        self.assertEqual(self.store.quotes()[0]["totals"]["total_cents"], 15000)
        self.assertEqual(Store(self.root / "dados", self.root / "midia").quotes()[0]["customer"]["name"], "Ana & João")
        self.store.save_quote(self.payload(delivery_cents=1000), q["id"])
        self.assertEqual(self.store.quotes()[0]["totals"]["total_cents"], 16000)

    def test_real_payments_approval_balance_and_delivery(self):
        q = self.save_quote()
        with self.assertRaises(ValueError):
            self.store.mark_delivered(q["id"])
        self.store.add_payment(q["id"], 5000, "PIX")
        self.assertEqual(self.store.quotes()[0]["status"], "Em Aberto")
        with self.assertRaises(ValueError):
            self.store.save_quote(self.payload(), q["id"])
        self.store.add_payment(q["id"], 2500, "PIX")
        current = self.store.quotes()[0]
        self.assertEqual(current["status"], "Aprovado / Data Reservada")
        self.assertEqual(current["balance_cents"], 7500)
        for amount in (0, -1, 7501):
            with self.assertRaises(ValueError):
                self.store.add_payment(q["id"], amount, "PIX")
        self.store.add_payment(q["id"], 7500, "Dinheiro", "Saldo na retirada")
        self.assertEqual(self.store.quotes()[0]["status"], "Quitado / Data Reservada")
        self.store.mark_delivered(q["id"])
        self.assertEqual(self.store.quotes()[0]["status"], "Entregue")
        self.assertEqual(len(self.store.payments(q["id"])), 3)

    def test_expired_quote_must_be_renewed(self):
        q = self.save_quote()
        with self.store.db() as db:
            db.execute("UPDATE quotes SET valid_until=?", ((date.today() - timedelta(days=1)).isoformat(),))
        self.assertEqual(self.store.quotes()[0]["status"], "Vencido")
        with self.assertRaises(ValueError):
            self.store.add_payment(q["id"], 7500, "PIX")
        self.store.renew_quote(q["id"])
        self.store.add_payment(q["id"], 7500, "PIX")
        self.assertEqual(self.store.quotes()[0]["status"], "Aprovado / Data Reservada")

    def test_inventory_and_cpf(self):
        item = {"name": "Leite", "brand": "Italac", "content": "1000", "content_unit": "ml", "stock": "3", "package_unit": "Cx", "paid_cents": 500, "photo": ""}
        self.store.save_inventory(item)
        self.assertEqual(str(inventory_cost(self.store.list("inventory")[0])), "0.005")
        with self.assertRaises(ValueError):
            self.store.save_inventory(dict(item, content="0"))
        self.assertEqual(validate_cpf("529.982.247-25"), "52998224725")
        with self.assertRaises(ValueError):
            validate_cpf("111.111.111-11")

    def test_images_and_consistent_backup(self):
        raw = BytesIO()
        Image.new("RGB", (100, 80), "pink").save(raw, format="JPEG")
        filename = self.store.save_image(raw)
        self.assertIsNotNone(self.store.image_path(filename))
        self.assertIsNone(self.store.image_path("../secret.png"))
        with self.assertRaises(ValueError):
            self.store.save_image(BytesIO(b"not an image"))
        self.save_quote(reference_photo=filename)
        archive = zipfile.ZipFile(BytesIO(self.store.backup()))
        self.assertIn("midia/" + filename, archive.namelist())
        dest = self.root / "restored.sqlite3"
        dest.write_bytes(archive.read("dados/confeitaria.sqlite3"))
        with closing(sqlite3.connect(dest)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT count(*) FROM quotes").fetchone()[0], 1)

    def test_pdf_client_and_kitchen_separation(self):
        extras = [{"name": "Topo de Bolo Simples", "amount_cents": 2500, "gift": True}]
        q = self.save_quote(lines=[make_line(self.simple, 2, ["Ninho"], extras)], pix_enabled=True, pix_percent="5", delivery_cents=2000)
        client = " ".join(" ".join(page.extract_text() for page in PdfReader(BytesIO(generate_pdf(q, self.store))).pages).split())
        kitchen = " ".join(" ".join(page.extract_text() for page in PdfReader(BytesIO(generate_pdf(q, self.store, True))).pages).split())
        for term in ("Preço Cartão", "PIX/Dinheiro", "Artigos 417 a 420", "[BRINDE]", "Saldo devedor", "Ana & João"):
            self.assertIn(term, client)
        for term in ("R$", "Saldo", "Preço", "PIX", "sinal", "417", "Válido até"):
            self.assertNotIn(term, kitchen)
        for term in ("Ninho", "Alergia a castanhas", "Ana & João", "[BRINDE]"):
            self.assertIn(term, kitchen)

    def test_large_pdf_paginates(self):
        lines = [make_line(self.simple, 2, ["Ninho"], details=f"Bolo {i}: decoração rosa.") for i in range(35)]
        q = self.save_quote(lines=lines)
        self.assertGreater(len(PdfReader(BytesIO(generate_pdf(q, self.store))).pages), 1)
        self.assertGreater(len(PdfReader(BytesIO(generate_pdf(q, self.store, True))).pages), 1)

    def test_single_long_item_can_span_pdf_pages(self):
        line = make_line(self.simple, 2, ["Ninho"], details="Detalhes da decoração e do transporte. " * 200)
        q = self.save_quote(lines=[line])
        self.assertGreater(len(PdfReader(BytesIO(generate_pdf(q, self.store))).pages), 1)


if __name__ == "__main__":
    unittest.main()
