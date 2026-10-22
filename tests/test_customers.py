from contextlib import closing
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from confeitaria.domain import CUSTOMER_DEFAULTS, customer_address, make_line, normalize_customer
from confeitaria.storage import Store


class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "dados", self.root / "midia")

    def tearDown(self):
        self.temp.cleanup()

    def customer(self):
        return {"name": "Mariana Oliveira", "phone": "(92) 99999-8888", "phone_secondary": "(92) 3333-4444", "email": "Mariana@Exemplo.com",
                "cpf": "529.982.247-25", "postal_code": "69000-000", "street": "Rua das Acácias", "number": "120", "complement": "Casa 2",
                "neighborhood": "Centro", "city": "Manaus", "state": "AM", "address_reference": "Próximo à praça", "notes": "Prefere contato por WhatsApp", "photo": "", "address": ""}

    def test_complete_customer_and_normalized_address(self):
        customer_id = self.store.save_customer(self.customer())
        saved = self.store.get_customer(customer_id)
        self.assertEqual(saved["phone"], "92999998888")
        self.assertEqual(saved["phone_secondary"], "9233334444")
        self.assertEqual(saved["email"], "mariana@exemplo.com")
        self.assertEqual(saved["postal_code"], "69000000")
        self.assertEqual(saved["cpf"], "52998224725")
        for term in ("Rua das Acácias, 120", "Casa 2", "Centro", "Manaus / AM", "CEP 69000-000"):
            self.assertIn(term, saved["address"])

    def test_update_preserves_other_fields(self):
        customer_id = self.store.save_customer(self.customer())
        self.store.save_customer({"name": "Mariana Oliveira Silva"}, customer_id)
        saved = self.store.get_customer(customer_id)
        self.assertEqual(saved["name"], "Mariana Oliveira Silva")
        self.assertEqual(saved["email"], "mariana@exemplo.com")
        self.assertEqual(saved["street"], "Rua das Acácias")
        self.store.save_customer({"street": "Avenida Brasil", "number": "80"}, customer_id)
        self.assertIn("Avenida Brasil, 80", self.store.get_customer(customer_id)["address"])

    def test_invalid_contact_or_cep_is_not_saved(self):
        for field, value in [("email", "sem-arroba"), ("postal_code", "6900-000"), ("postal_code", "abc69000000"), ("state", "ZZ"), ("phone", "abc92999998888"), ("phone_secondary", "123"), ("name", " ")]:
            with self.subTest(field=field, value=value):
                values = {**self.customer(), field: value}
                with self.assertRaises(ValueError):
                    self.store.save_customer(values)
        self.assertEqual(len(self.store.list("customers")), 0)

    def test_delete_without_orders_and_reject_missing_customer(self):
        customer_id = self.store.save_customer(self.customer())
        self.assertEqual(self.store.delete_customer(customer_id), "deleted")
        self.assertIsNone(self.store.get_customer(customer_id))
        with self.assertRaises(ValueError):
            self.store.delete_customer(customer_id)

    def test_archive_preserves_quote_payments_and_snapshot(self):
        customer_id = self.store.save_customer(self.customer())
        product = next(p for p in self.store.list("products") if p["name"] == "Bolo Simples")
        payload = {"customer_id": customer_id, "event_at": (datetime.now() + timedelta(days=10)).isoformat(), "fulfillment": "Entrega", "delivery_address": customer_address(self.customer()),
                   "lines": [make_line(product, 2, ["Ninho"])], "payment_method": "PIX", "pix_enabled": False, "pix_percent": "0", "discount_cents": 0, "delivery_cents": 0,
                   "notes": "", "production_notes": "", "reference_photo": ""}
        quote_id = self.store.save_quote(payload)
        self.store.add_payment(quote_id, 7500, "PIX")
        snapshot = self.store.quotes()[0]["customer"]
        self.assertEqual(self.store.delete_customer(customer_id), "archived")
        self.assertFalse(self.store.get_customer(customer_id)["active"])
        self.assertEqual(self.store.quotes()[0]["customer"], snapshot)
        self.assertEqual(self.store.quotes()[0]["paid_cents"], 7500)
        with self.assertRaises(ValueError):
            self.store.save_quote(payload)
        self.store.restore_customer(customer_id)
        self.assertTrue(self.store.get_customer(customer_id)["active"])
        self.assertIsInstance(self.store.save_quote(payload), int)

    def test_old_database_migrates_once_without_losing_legacy_address(self):
        data = self.root / "legacy"
        data.mkdir()
        database = data / "confeitaria.sqlite3"
        old = {"id": 12, "name": "Cliente anterior", "phone": "92999998888", "cpf": "", "address": "Rua antiga, 20, Manaus", "photo": "foto-antiga.png"}
        with closing(sqlite3.connect(database)) as db:
            db.execute("CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL,phone TEXT NOT NULL,cpf TEXT NOT NULL DEFAULT '',address TEXT NOT NULL DEFAULT '',photo TEXT NOT NULL DEFAULT '')")
            db.execute("INSERT INTO customers VALUES(?,?,?,?,?,?)", tuple(old.values()))
            db.commit()
        migrated = Store(data, self.root / "legacy_media")
        saved = migrated.get_customer(12)
        self.assertEqual({k: saved[k] for k in old}, old)
        self.assertEqual(saved["email"], "")
        self.assertTrue(saved["active"])
        backups = list((data / "copias_antes_atualizacao").glob("*.sqlite3"))
        self.assertEqual(len(backups), 1)
        with closing(sqlite3.connect(backups[0])) as db:
            self.assertEqual(db.execute("SELECT address FROM customers WHERE id=12").fetchone()[0], old["address"])
            self.assertNotIn("email", {r[1] for r in db.execute("PRAGMA table_info(customers)")})
        Store(data, self.root / "legacy_media")
        self.assertEqual(len(list((data / "copias_antes_atualizacao").glob("*.sqlite3"))), 1)
        migrated.save_customer({"email": "cliente@exemplo.com"}, 12)
        self.assertEqual(migrated.get_customer(12)["address"], old["address"])


if __name__ == "__main__":
    unittest.main()
