"""Persistência SQLite, mídia normalizada e backup consistente."""
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import uuid
import warnings
import zipfile

from PIL import Image, ImageOps

from .domain import CATEGORIES, CUSTOMER_DEFAULTS, decimal, normalize_customer, order_status, totals

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS = {"name": "Minha Confeitaria", "phone": "", "address": "", "document": "",
                    "logo": "", "change_days": 3, "reminders_enabled": False,
                    "local_notifications": True, "alert_days": [3, 2], "alert_time": "09:00",
                    "notification_email": "", "email_enabled": False, "smtp_host": "smtp.gmail.com",
                    "smtp_port": 465, "smtp_security": "SSL/TLS", "smtp_username": "", "smtp_sender": ""}


class Store:
    def __init__(self, data_dir=None, media_dir=None):
        self.data_dir = Path(data_dir or os.environ.get("CONFEITARIA_DATA_DIR", ROOT / "dados"))
        self.media_dir = Path(media_dir or os.environ.get("CONFEITARIA_MEDIA_DIR", ROOT / "midia"))
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "confeitaria.sqlite3"
        self.initialize()

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self):
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '', unit TEXT NOT NULL,
                    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                    promo_enabled INTEGER NOT NULL DEFAULT 0, promo_cents INTEGER NOT NULL DEFAULT 0,
                    promo_start TEXT, promo_end TEXT, photos TEXT NOT NULL DEFAULT '[]',
                    active INTEGER NOT NULL DEFAULT 1, composition TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL,
                    cpf TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', photo TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '', phone_secondary TEXT NOT NULL DEFAULT '',
                    postal_code TEXT NOT NULL DEFAULT '', street TEXT NOT NULL DEFAULT '', number TEXT NOT NULL DEFAULT '',
                    complement TEXT NOT NULL DEFAULT '', neighborhood TEXT NOT NULL DEFAULT '', city TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT '', address_reference TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS inventory (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL, content_unit TEXT NOT NULL, stock TEXT NOT NULL,
                    package_unit TEXT NOT NULL, paid_cents INTEGER NOT NULL, photo TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
                    created_at TEXT NOT NULL, valid_until TEXT NOT NULL, event_at TEXT NOT NULL,
                    payload TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY, quote_id INTEGER NOT NULL REFERENCES quotes(id),
                    amount_cents INTEGER NOT NULL CHECK(amount_cents > 0), method TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '', received_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS quotes_event ON quotes(event_at);
                CREATE INDEX IF NOT EXISTS payments_quote ON payments(quote_id);
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(customers)")}
            missing = set(CUSTOMER_DEFAULTS) - columns
            product_columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
            if missing or "composition" not in product_columns:
                backup_dir = self.data_dir / "copias_antes_atualizacao"
                backup_dir.mkdir(exist_ok=True)
                target = backup_dir / f"antes-v3-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.sqlite3"
                with closing(sqlite3.connect(target)) as dest:
                    db.backup(dest)
                db.execute("BEGIN IMMEDIATE")
                columns = {row[1] for row in db.execute("PRAGMA table_info(customers)")}
                for field in sorted(set(CUSTOMER_DEFAULTS) - columns):
                    definition = "INTEGER NOT NULL DEFAULT 1" if field == "active" else "TEXT NOT NULL DEFAULT ''"
                    db.execute(f"ALTER TABLE customers ADD COLUMN {field} {definition}")
                if "composition" not in {row[1] for row in db.execute("PRAGMA table_info(products)")}:
                    db.execute("ALTER TABLE products ADD COLUMN composition TEXT NOT NULL DEFAULT '[]'")
            if not db.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone():
                from .catalog_data import product_templates
                for item in product_templates():
                    db.execute("INSERT INTO products(name,category,description,unit,price_cents,composition) VALUES(?,?,?,?,?,?)",
                               (item["name"], item["category"], item["description"], item["unit"], item.get("price_cents", 0), json.dumps(item.get("composition", []))))
                db.execute("INSERT INTO settings VALUES('initialized','true')")
            if not db.execute("SELECT 1 FROM settings WHERE key='catalog_v3'").fetchone():
                from .catalog_data import product_templates
                legacy = {"Cadastre a descrição e o preço antes de vender.", "Bolo por quilo com recheios simples. Mínimo de 2 kg.", "Bolo por quilo com recheios especiais."}
                old_kit = db.execute("SELECT * FROM products WHERE name='Kit Festa' AND category='Kits Festa'").fetchone()
                if old_kit and old_kit["description"] in legacy and not db.execute("SELECT 1 FROM products WHERE name='Kit Festa 1'").fetchone():
                    db.execute("UPDATE products SET name='Kit Festa 1' WHERE id=?", (old_kit["id"],))
                for item in product_templates():
                    found = db.execute("SELECT * FROM products WHERE name=? AND category=?", (item["name"], item["category"])).fetchone()
                    if not found:
                        db.execute("INSERT INTO products(name,category,description,unit,price_cents,composition) VALUES(?,?,?,?,?,?)",
                                   (item["name"], item["category"], item["description"], item["unit"], item.get("price_cents", 0), json.dumps(item.get("composition", []))))
                    elif found["description"] in legacy:
                        db.execute("UPDATE products SET description=?,composition=? WHERE id=?", (item["description"], json.dumps(item.get("composition", [])), found["id"]))
                db.execute("INSERT INTO settings VALUES('catalog_v3','true')")

    def list(self, table):
        if table not in {"products", "customers", "inventory"}:
            raise ValueError("Tabela inválida.")
        with self.db() as db:
            rows = [dict(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY name COLLATE NOCASE")]
        if table == "products":
            for row in rows:
                row["photos"] = json.loads(row["photos"])
                row["composition"] = json.loads(row["composition"])
        return rows

    def save_product(self, values, product_id=None):
        values = dict(values)
        previous = next((p for p in self.list("products") if p["id"] == product_id), {}) if product_id else {}
        values.setdefault("composition", previous.get("composition", []))
        if not values["name"].strip() or values["category"] not in CATEGORIES:
            raise ValueError("Informe nome e categoria válidos.")
        expected_unit = "kg" if values["category"] in CATEGORIES[:2] else "cento" if values["category"] == CATEGORIES[2] else "un"
        values["unit"] = expected_unit
        if values["price_cents"] < 0 or values["promo_cents"] < 0:
            raise ValueError("Os preços não podem ser negativos.")
        if values["promo_enabled"]:
            if not values["promo_start"] or not values["promo_end"] or values["promo_start"] > values["promo_end"]:
                raise ValueError("Defina um intervalo válido para a promoção.")
            if values["promo_cents"] <= 0 or values["promo_cents"] >= values["price_cents"]:
                raise ValueError("O preço promocional deve ser positivo e menor que o preço normal.")
        if len(values["photos"]) > 3:
            raise ValueError("Use até três fotos por produto.")
        values["photos"] = json.dumps(values["photos"])
        if not isinstance(values["composition"], list) or any(not isinstance(item, str) or not item.strip() for item in values["composition"]):
            raise ValueError("Informe a composição como uma lista de itens preenchidos.")
        values["composition"] = json.dumps(values["composition"])
        return self._save("products", values, product_id)

    def save_customer(self, values, customer_id=None):
        previous = self.get_customer(customer_id) if customer_id else {}
        if customer_id and not previous:
            raise ValueError("Cliente não encontrado.")
        return self._save("customers", normalize_customer({**(previous or {}), **values}), customer_id)

    def get_customer(self, customer_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM customers WHERE id=?", (customer_id,)).fetchone()
        return dict(row) if row else None

    def delete_customer(self, customer_id):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM customers WHERE id=?", (customer_id,)).fetchone():
                raise ValueError("Cliente não encontrado.")
            if db.execute("SELECT 1 FROM quotes WHERE customer_id=?", (customer_id,)).fetchone():
                db.execute("UPDATE customers SET active=0 WHERE id=?", (customer_id,))
                return "archived"
            db.execute("DELETE FROM customers WHERE id=?", (customer_id,))
            return "deleted"

    def restore_customer(self, customer_id):
        with self.db() as db:
            if db.execute("UPDATE customers SET active=1 WHERE id=?", (customer_id,)).rowcount != 1:
                raise ValueError("Cliente não encontrado.")

    def save_inventory(self, values, item_id=None):
        if not values["name"].strip() or decimal(values["content"]) <= 0 or decimal(values["stock"]) < 0 or values["paid_cents"] < 0:
            raise ValueError("Informe nome, conteúdo positivo e estoque/valor não negativos.")
        return self._save("inventory", values, item_id)

    def _save(self, table, values, item_id):
        fields = {
            "products": {"name", "category", "description", "unit", "price_cents", "promo_enabled", "promo_cents", "promo_start", "promo_end", "photos", "active", "composition"},
            "customers": set(CUSTOMER_DEFAULTS),
            "inventory": {"name", "brand", "content", "content_unit", "stock", "package_unit", "paid_cents", "photo"},
        }
        if table not in fields or set(values) != fields[table]:
            raise ValueError("Campos de cadastro inválidos.")
        with self.db() as db:
            if item_id:
                if db.execute(f"UPDATE {table} SET " + ",".join(f"{k}=?" for k in values) + " WHERE id=?", [*values.values(), item_id]).rowcount != 1:
                    raise ValueError("Cadastro não encontrado.")
                return item_id
            cursor = db.execute(f"INSERT INTO {table} (" + ",".join(values) + ") VALUES (" + ",".join("?" for _ in values) + ")", list(values.values()))
            return cursor.lastrowid

    def settings(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM settings WHERE key='shop'").fetchone()
        return {**DEFAULT_SETTINGS, **(json.loads(row[0]) if row else {})}

    def save_settings(self, values):
        values = {**self.settings(), **values}
        if not values["name"].strip() or not 0 <= int(values["change_days"]) <= 365:
            raise ValueError("Informe o nome da loja e um prazo entre 0 e 365 dias.")
        with self.db() as db:
            db.execute("INSERT INTO settings VALUES('shop',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (json.dumps(values),))

    def save_quote(self, payload, quote_id=None):
        payload = json.loads(json.dumps(payload))
        if not payload["lines"]:
            raise ValueError("Adicione pelo menos um item ao orçamento.")
        payload["totals"] = totals(payload["lines"], payload["discount_cents"], payload["delivery_cents"], payload["pix_enabled"], payload["pix_percent"], payload["payment_method"])
        if payload["totals"]["total_cents"] <= 0:
            raise ValueError("O orçamento precisa ter valor total maior que zero.")
        event = datetime.fromisoformat(payload["event_at"])
        if event.date() < date.today():
            raise ValueError("A saída/retirada deve ser hoje ou em uma data futura.")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            customer = db.execute("SELECT * FROM customers WHERE id=?", (payload["customer_id"],)).fetchone()
            if not customer or not customer["active"]:
                raise ValueError("Selecione um cliente cadastrado.")
            payload["customer"] = dict(customer)
            payload["shop"] = self.settings()
            override = payload.pop("logo_override", "")
            if override:
                if not self.image_path(override):
                    raise ValueError("A logo selecionada não foi encontrada.")
                payload["shop"]["logo"] = override
            if quote_id:
                previous = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
                if not previous or previous["delivered"] or db.execute("SELECT 1 FROM payments WHERE quote_id=?", (quote_id,)).fetchone():
                    raise ValueError("Somente orçamentos sem pagamentos podem ser editados.")
                db.execute("UPDATE quotes SET customer_id=?,event_at=?,payload=? WHERE id=?", (payload["customer_id"], payload["event_at"], json.dumps(payload), quote_id))
                return quote_id
            cursor = db.execute("INSERT INTO quotes(customer_id,created_at,valid_until,event_at,payload) VALUES(?,?,?,?,?)",
                                (payload["customer_id"], datetime.now().isoformat(timespec="seconds"), (date.today() + timedelta(days=7)).isoformat(), payload["event_at"], json.dumps(payload)))
            return cursor.lastrowid

    @staticmethod
    def _quote(row):
        if not row:
            return None
        result = json.loads(row["payload"])
        result.update({k: row[k] for k in ("id", "created_at", "valid_until", "event_at", "delivered")})
        return result

    def quotes(self, customer_id=None):
        with self.db() as db:
            rows = db.execute("SELECT * FROM quotes" + (" WHERE customer_id=?" if customer_id else "") + " ORDER BY event_at,id", (customer_id,) if customer_id else ()).fetchall()
            paid = {r[0]: r[1] for r in db.execute("SELECT quote_id,SUM(amount_cents) FROM payments GROUP BY quote_id")}
        result = []
        for row in rows:
            quote = self._quote(row)
            quote["paid_cents"] = paid.get(quote["id"], 0)
            quote["balance_cents"] = quote["totals"]["total_cents"] - quote["paid_cents"]
            quote["status"] = order_status(quote, quote["paid_cents"])
            result.append(quote)
        return result

    def payments(self, quote_id):
        with self.db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM payments WHERE quote_id=? ORDER BY id", (quote_id,))]

    def update_quote_logo(self, quote_id, logo):
        if not self.image_path(logo):
            raise ValueError("Envie uma logo válida antes de atualizar o orçamento.")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT payload FROM quotes WHERE id=?", (quote_id,)).fetchone()
            if not row:
                raise ValueError("Orçamento não encontrado.")
            payload = json.loads(row["payload"])
            payload["shop"]["logo"] = logo
            db.execute("UPDATE quotes SET payload=? WHERE id=?", (json.dumps(payload), quote_id))

    def add_payment(self, quote_id, amount_cents, method, note=""):
        if amount_cents <= 0 or method not in ("PIX", "Dinheiro", "Cartão"):
            raise ValueError("Informe um pagamento positivo e uma forma válida.")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            quote = self._quote(db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone())
            if not quote or quote["delivered"]:
                raise ValueError("Pedido não encontrado ou já entregue.")
            paid = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE quote_id=?", (quote_id,)).fetchone()[0]
            if order_status(quote, paid) == "Vencido":
                raise ValueError("Renove a validade do orçamento antes de receber o pagamento.")
            if amount_cents > quote["totals"]["total_cents"] - paid:
                raise ValueError("O recebimento não pode ultrapassar o saldo devedor.")
            db.execute("INSERT INTO payments(quote_id,amount_cents,method,note,received_at) VALUES(?,?,?,?,?)",
                       (quote_id, int(amount_cents), method, note.strip(), datetime.now().isoformat(timespec="seconds")))

    def mark_delivered(self, quote_id):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM quotes WHERE id=?", (quote_id,)).fetchone()
            quote = self._quote(row)
            paid = db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM payments WHERE quote_id=?", (quote_id,)).fetchone()[0]
            if not quote or paid < quote["totals"]["total_cents"]:
                raise ValueError("Quite o saldo antes de registrar a entrega.")
            db.execute("UPDATE quotes SET delivered=1 WHERE id=?", (quote_id,))

    def renew_quote(self, quote_id):
        with self.db() as db:
            if db.execute("UPDATE quotes SET valid_until=? WHERE id=? AND delivered=0", ((date.today() + timedelta(days=7)).isoformat(), quote_id)).rowcount != 1:
                raise ValueError("Orçamento não encontrado ou já entregue.")

    def save_image(self, upload):
        if upload is None:
            return ""
        raw = upload.getvalue() if hasattr(upload, "getvalue") else upload.read()
        if len(raw) > 10 * 1024 * 1024:
            raise ValueError("Cada foto deve ter no máximo 10 MB.")
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(raw)) as original:
                    if original.format not in ("JPEG", "PNG", "WEBP"):
                        raise ValueError("Use imagens JPG, PNG ou WEBP.")
                    image = ImageOps.exif_transpose(original)
                    image.thumbnail((1800, 1800))
                    image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    name = f"{uuid.uuid4().hex}.png"
                    image.save(self.media_dir / name, "PNG")
                    return name
        except (OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ValueError("Imagem inválida ou com resolução excessiva.") from exc

    def image_path(self, name):
        if not name or Path(name).name != name:
            return None
        target = (self.media_dir / name).resolve()
        if target.parent != self.media_dir.resolve() or not target.is_file():
            return None
        return target

    def backup(self):
        """Backup online do SQLite + todas as mídias; nenhuma credencial é incluída."""
        output = BytesIO()
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "confeitaria.sqlite3"
            with self.db() as source:
                with closing(sqlite3.connect(target)) as dest:
                    source.backup(dest)
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(target, "dados/confeitaria.sqlite3")
                for path in self.media_dir.iterdir():
                    if path.is_file() and not path.is_symlink():
                        archive.write(path, f"midia/{path.name}")
        return output.getvalue()


def inventory_cost(item):
    """Reais por g/ml/unidade. Valor pago refere-se a uma embalagem."""
    return Decimal(item["paid_cents"]) / 100 / decimal(item["content"])
