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
                    "logo": "", "change_days": 3}


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
                    active INTEGER NOT NULL DEFAULT 1);
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
            if missing:
                backup_dir = self.data_dir / "copias_antes_atualizacao"
                backup_dir.mkdir(exist_ok=True)
                target = backup_dir / f"antes-v2-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}.sqlite3"
                with closing(sqlite3.connect(target)) as dest:
                    db.backup(dest)
                db.execute("BEGIN IMMEDIATE")
                columns = {row[1] for row in db.execute("PRAGMA table_info(customers)")}
                for field in sorted(set(CUSTOMER_DEFAULTS) - columns):
                    definition = "INTEGER NOT NULL DEFAULT 1" if field == "active" else "TEXT NOT NULL DEFAULT ''"
                    db.execute(f"ALTER TABLE customers ADD COLUMN {field} {definition}")
            if not db.execute("SELECT 1 FROM settings WHERE key='initialized'").fetchone():
                seeds = [("Bolo Simples", CATEGORIES[0], "Bolo por quilo com recheios simples. Mínimo de 2 kg.", "kg", 7500),
                         ("Bolo Especial", CATEGORIES[1], "Bolo por quilo com recheios especiais.", "kg", 8500)]
                seeds.extend((name, category, "Cadastre a descrição e o preço antes de vender.", unit, 0)
                             for name, category, unit in [("Cento de Brigadeiros", CATEGORIES[2], "cento"),
                             ("Kit Festa", CATEGORIES[3], "un"), ("Cupcake", CATEGORIES[4], "un"),
                             ("Mini Donut", CATEGORIES[5], "un"), ("Topo de Bolo", CATEGORIES[6], "un")])
                db.executemany("INSERT INTO products(name,category,description,unit,price_cents) VALUES(?,?,?,?,?)", seeds)
                db.execute("INSERT INTO settings VALUES('initialized','true')")

    def list(self, table):
        if table not in {"products", "customers", "inventory"}:
            raise ValueError("Tabela inválida.")
        with self.db() as db:
            rows = [dict(r) for r in db.execute(f"SELECT * FROM {table} ORDER BY name COLLATE NOCASE")]
        if table == "products":
            for row in rows:
                row["photos"] = json.loads(row["photos"])
        return rows

    def save_product(self, values, product_id=None):
        values = dict(values)
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
            "products": {"name", "category", "description", "unit", "price_cents", "promo_enabled", "promo_cents", "promo_start", "promo_end", "photos", "active"},
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
