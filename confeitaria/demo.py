"""Dados fictícios em banco separado; nunca altera os cadastros reais."""
from datetime import date, datetime, time, timedelta
from pathlib import Path

from .catalog_data import product_templates
from .domain import make_line
from .storage import Store


def demonstration_store(real_store):
    root = real_store.data_dir / "demonstracao"
    store = Store(root / "dados", root / "midia")
    with store.db() as db:
        if db.execute("SELECT 1 FROM settings WHERE key='demo_initialized'").fetchone():
            return store
    assets = Path(__file__).resolve().parent.parent / "assets" / "demo"
    templates = {p["name"]: p for p in product_templates()}
    for product in store.list("products"):
        item = templates[product["name"]]
        with (assets / (item["asset"] + ".png")).open("rb") as photo:
            product["photos"] = [store.save_image(photo)]
        product["price_cents"] = item["demo_cents"]
        if product["name"] == "Cupcake":
            product.update(promo_enabled=1, promo_cents=650, promo_start=date.today().isoformat(), promo_end=(date.today()+timedelta(days=30)).isoformat())
        identifier = product.pop("id")
        store.save_product(product, identifier)
    store.save_settings({**store.settings(), "name":"Doce Ateliê · Demonstração", "phone":"(92) 99999-0000", "address":"Rua das Flores, 120 · Manaus / AM"})
    for index, name in enumerate(["Ana Beatriz", "Beatriz Almeida", "Camila Santos", "Daniela Oliveira", "Elisa Martins", "Fernanda Costa"]):
        with (assets / f"cliente-{index}.png").open("rb") as photo:
            image = store.save_image(photo)
        client = store.save_customer({"name":name, "phone":f"9299999000{index}", "email":name.split()[0].lower()+"@example.com", "postal_code":"69005040", "street":"Rua das Flores", "number":str(120+index), "neighborhood":"Centro", "city":"Manaus", "state":"AM", "photo":image, "notes":"Cadastro fictício para conhecer o sistema."})
        product = next(p for p in store.list("products") if p["name"] == ("Bolo Especial" if index%2 else "Bolo Simples"))
        line = make_line(product, 2+index*.5, ["Nutella" if index%2 else "Ninho"], details="Decoração em tons suaves. Modelo ilustrativo.", reference_photo=product["photos"][0])
        quote = store.save_quote({"customer_id":client, "event_at":datetime.combine(date.today()+timedelta(days=index+1),time(10+index)).isoformat(timespec="minutes"), "fulfillment":"Retirada", "delivery_address":"", "lines":[line], "payment_method":"PIX", "pix_enabled":False, "pix_percent":"0", "discount_cents":0, "delivery_cents":0, "notes":"Pedido fictício.", "production_notes":"Conferir nome e cores antes da produção.", "reference_photo":""})
        if index in [1,2,3]:
            store.add_payment(quote, (line["total_cents"]+1)//2, "PIX", "Sinal de exemplo")
        if index == 4:
            store.add_payment(quote, line["total_cents"], "PIX", "Pagamento fictício")
            store.mark_delivered(quote)
    with store.db() as db:
        db.execute("INSERT INTO settings VALUES('demo_initialized','true')")
    return store
