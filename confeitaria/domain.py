"""Regras monetárias independentes da interface e do banco."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CATEGORIES = ["Bolos Simples", "Bolos Especiais", "Cento de Brigadeiros", "Kits Festa", "Cupcakes", "Mini Donuts", "Topos de Bolo"]
SIMPLE_FILLINGS = ["Chocolate", "Ninho", "Chocolate Branco", "Dois Amores"]
SPECIAL_FILLINGS = ["Ninho com Morango", "Nutella", "Ninho com Nutella", "Chocolate com Morango", "Doce de Leite com Ameixa"]
EXTRAS = ["Massa de Chocolate", "Brigadeiros no Topo", "Frutas Extras", "Recheios Extras", "Bolo de Andar", "Topo de Bolo Simples", "Topo de Bolo Especial"]
BRIGADEIRO_TYPES = ["Tradicional", "Especial", "Personalizado"]
UNITS = ["Cx", "Un", "Kg", "Grama", "Litro"]
PAYMENT_METHODS = ["PIX", "Dinheiro", "Cartão"]


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Informe um número válido.") from exc
    if not result.is_finite():
        raise ValueError("Informe um número finito.")
    return result


def cents(value):
    return int((decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def brl(value):
    return "R$ " + f"{int(value) / 100:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def quantity_text(value):
    return format(decimal(value).normalize(), "f").replace(".", ",")


def active_price(product, on_date=None):
    today = (on_date or date.today()).isoformat()
    promotional = bool(product.get("promo_enabled")) and bool(product.get("promo_start")) and bool(product.get("promo_end")) and product["promo_start"] <= today <= product["promo_end"]
    return (int(product["promo_cents"]) if promotional else int(product["price_cents"])), promotional


def make_line(product, quantity, fillings=None, extras=None, details="", gift=False, brigadeiro_type=None, split=False, flavors=None):
    qty = decimal(quantity)
    if qty <= 0 or qty > 100000:
        raise ValueError("A quantidade deve ser maior que zero e até 100.000.")
    if product["unit"] != "kg" and qty != qty.to_integral_value():
        raise ValueError("Itens por unidade ou cento exigem quantidade inteira.")
    if product["category"] == "Bolos Simples" and qty < 2:
        raise ValueError("O Bolo Simples exige no mínimo 2 kg.")
    fillings = fillings or []
    if product["category"] in ("Bolos Simples", "Bolos Especiais"):
        allowed = SIMPLE_FILLINGS if product["category"] == "Bolos Simples" else SPECIAL_FILLINGS
        if not fillings or any(f not in allowed for f in fillings):
            raise ValueError("Selecione recheios válidos para a categoria do bolo.")
    if product["category"] == "Cento de Brigadeiros":
        if brigadeiro_type not in BRIGADEIRO_TYPES:
            raise ValueError("Selecione a categoria dos brigadeiros.")
        flavors = [f.strip() for f in (flavors or []) if f.strip()]
        if len(flavors) != (2 if split else 1):
            raise ValueError("Informe os dois sabores para dividir 50/50, ou um sabor para o cento inteiro.")
    normalized_extras = []
    for extra in extras or []:
        amount = int(extra["amount_cents"])
        if amount < 0 or not extra["name"].strip():
            raise ValueError("Adicional inválido.")
        normalized_extras.append({"name": extra["name"].strip(), "amount_cents": amount, "gift": bool(extra.get("gift"))})
    price, promotional = active_price(product)
    if price <= 0 and not gift:
        raise ValueError("Defina um preço no catálogo ou marque o item como cortesia.")
    base = int((qty * price).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    extras_total = sum(e["amount_cents"] for e in normalized_extras if not e["gift"])
    return {
        "product_id": product["id"], "name": product["name"], "category": product["category"],
        "quantity": str(qty), "unit": product["unit"], "unit_cents": price,
        "regular_unit_cents": int(product["price_cents"]), "promotional": promotional,
        "fillings": fillings, "extras": normalized_extras, "details": details.strip(),
        "gift": bool(gift), "brigadeiro_type": brigadeiro_type,
        "split": bool(split), "flavors": flavors or [],
        "total_cents": 0 if gift else base + extras_total,
    }


def totals(lines, discount_cents=0, delivery_cents=0, pix_enabled=False, pix_percent=0, payment_method="PIX"):
    subtotal = sum(int(line["total_cents"]) for line in lines)
    discount_cents, delivery_cents = int(discount_cents), int(delivery_cents)
    percent = decimal(pix_percent)
    if discount_cents < 0 or discount_cents > subtotal:
        raise ValueError("O desconto geral deve ficar entre zero e o subtotal dos itens.")
    if delivery_cents < 0 or not 0 <= percent <= 100:
        raise ValueError("Frete ou percentual de desconto inválido.")
    if payment_method not in PAYMENT_METHODS:
        raise ValueError("Forma de pagamento inválida.")
    if pix_enabled and payment_method == "Cartão":
        raise ValueError("O desconto PIX/Dinheiro não se aplica ao cartão.")
    pix_discount = int((Decimal(subtotal - discount_cents) * percent / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if pix_enabled else 0
    card = subtotal - discount_cents + delivery_cents
    return {"subtotal_cents": subtotal, "discount_cents": discount_cents, "delivery_cents": delivery_cents,
            "card_cents": card, "pix_discount_cents": pix_discount, "total_cents": card - pix_discount,
            "deposit_cents": (card - pix_discount + 1) // 2}


def order_status(quote, paid_cents, today=None):
    if quote.get("delivered"):
        return "Entregue"
    total = quote["totals"]["total_cents"]
    if paid_cents >= total and total > 0:
        return "Quitado / Data Reservada"
    if paid_cents >= quote["totals"]["deposit_cents"] and total > 0:
        return "Aprovado / Data Reservada"
    if quote["valid_until"] < (today or date.today()).isoformat():
        return "Vencido"
    return "Em Aberto"


def validate_cpf(cpf):
    digits = "".join(c for c in cpf if c.isdigit())
    if not digits:
        return ""
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValueError("CPF inválido.")
    for n in (9, 10):
        check = (sum(int(digits[i]) * (n + 1 - i) for i in range(n)) * 10) % 11 % 10
        if int(digits[n]) != check:
            raise ValueError("CPF inválido.")
    return digits
