"""Regras monetárias independentes da interface e do banco."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re

CATEGORIES = ["Bolos Simples", "Bolos Especiais", "Cento de Brigadeiros", "Kits Festa", "Cupcakes", "Mini Donuts", "Topos de Bolo"]
SIMPLE_FILLINGS = ["Chocolate", "Ninho", "Chocolate Branco", "Dois Amores"]
SPECIAL_FILLINGS = ["Ninho com Morango", "Nutella", "Ninho com Nutella", "Chocolate com Morango", "Doce de Leite com Ameixa"]
EXTRAS = ["Massa de Chocolate", "Brigadeiros no Topo", "Frutas Extras", "Recheios Extras", "Bolo de Andar", "Topo de Bolo Simples", "Topo de Bolo Especial"]
BRIGADEIRO_TYPES = ["Tradicional", "Especial", "Personalizado"]
BRIGADEIRO_FLAVORS = {"Tradicional": ["Chocolate", "Beijinho"], "Especial": ["Nutella", "Brigadeiro Rocher", "Ninho", "Ninho com Nutella"], "Personalizado": ["Chocolate", "Beijinho", "Nutella", "Brigadeiro Rocher", "Ninho"]}
UNITS = ["Cx", "Un", "Kg", "Grama", "Litro"]
PAYMENT_METHODS = ["PIX", "Dinheiro", "Cartão"]
STATES = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
CUSTOMER_DEFAULTS = {"name": "", "phone": "", "phone_secondary": "", "email": "", "cpf": "", "address": "", "photo": "",
                     "postal_code": "", "street": "", "number": "", "complement": "", "neighborhood": "", "city": "", "state": "", "address_reference": "", "notes": "", "active": 1}


def customer_address(customer):
    if not customer.get("street"):
        return customer.get("address", "")
    street = customer["street"] + (f", {customer['number']}" if customer.get("number") else "")
    city = " / ".join(filter(None, [customer.get("city"), customer.get("state")]))
    cep = customer.get("postal_code", "")
    if len(cep) == 8:
        cep = cep[:5] + "-" + cep[5:]
    return " · ".join(filter(None, [street, customer.get("complement"), customer.get("neighborhood"), city, f"CEP {cep}" if cep else ""]))


def normalize_customer(values):
    result = {**CUSTOMER_DEFAULTS, **values}
    result = {k: str(result[k]).strip() if k != "active" else int(bool(result[k])) for k in CUSTOMER_DEFAULTS}
    if len(result["name"]) < 2:
        raise ValueError("Informe o nome do cliente com pelo menos dois caracteres.")
    for field in ("phone", "phone_secondary"):
        raw = result[field]
        digits = re.sub(r"\D", "", raw)
        if field == "phone" or raw:
            if not 10 <= len(digits) <= 13 or re.search(r"[^\d\s()+.\-]", raw):
                raise ValueError("Informe um telefone válido com DDD (10 a 13 dígitos).")
        result[field] = digits
    if result["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result["email"]):
        raise ValueError("Informe um e-mail válido, como nome@exemplo.com.")
    result["email"] = result["email"].lower()
    if result["postal_code"]:
        if not re.fullmatch(r"\d{5}-?\d{3}", result["postal_code"]):
            raise ValueError("Informe o CEP com 8 dígitos, por exemplo 69000-000.")
        result["postal_code"] = result["postal_code"].replace("-", "")
    result["state"] = result["state"].upper()
    if result["state"] and result["state"] not in STATES:
        raise ValueError("Selecione um estado válido.")
    result["cpf"] = validate_cpf(result["cpf"])
    result["address"] = customer_address(result)
    return result


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


def filling_limit(quantity):
    return 1 if decimal(quantity) < 2 else 2


def make_line(product, quantity, fillings=None, extras=None, details="", gift=False, brigadeiro_type=None, split=False, flavors=None,
              *, allow_extra_fillings=False, allow_under_minimum=False, negotiation_notes="", reference_photo=""):
    qty = decimal(quantity)
    if qty <= 0 or qty > 100000:
        raise ValueError("A quantidade deve ser maior que zero e até 100.000.")
    if product["unit"] != "kg" and qty != qty.to_integral_value():
        raise ValueError("Itens por unidade ou cento exigem quantidade inteira.")
    under_minimum = product["category"] in ("Bolos Simples", "Bolos Especiais") and qty < 2
    if under_minimum and not allow_under_minimum:
        raise ValueError("Bolos Simples e Especiais exigem no mínimo 2 kg. Confirme a exceção negociada para aceitar um peso menor.")
    fillings = fillings or []
    excess = False
    if product["category"] in ("Bolos Simples", "Bolos Especiais"):
        allowed = SIMPLE_FILLINGS if product["category"] == "Bolos Simples" else SPECIAL_FILLINGS
        if not fillings or len(set(fillings)) != len(fillings) or any(f not in allowed for f in fillings):
            raise ValueError("Selecione recheios válidos para a categoria do bolo.")
        excess = len(fillings) > filling_limit(qty)
        if excess and not allow_extra_fillings:
            raise ValueError(f"Para {quantity_text(qty)} kg, o padrão é até {filling_limit(qty)} recheio(s). Confirme a exceção negociada antes de continuar.")
        if (under_minimum or excess) and not negotiation_notes.strip():
            raise ValueError("Registre o motivo ou a condição combinada para autorizar a exceção.")
    if product["category"] == "Cento de Brigadeiros":
        if brigadeiro_type not in BRIGADEIRO_TYPES:
            raise ValueError("Selecione a categoria dos brigadeiros.")
        flavors = [f.strip() for f in (flavors or []) if f.strip()]
        if len(flavors) != (2 if split else 1):
            raise ValueError("Informe os dois sabores para dividir 50/50, ou um sabor para o cento inteiro.")
        if any(flavor not in BRIGADEIRO_FLAVORS[brigadeiro_type] for flavor in flavors):
            raise ValueError("Selecione sabores válidos para o tipo de brigadeiro.")
        if split and flavors[0] == flavors[1]:
            raise ValueError("Escolha dois sabores diferentes para dividir 50/50.")
        if brigadeiro_type == "Personalizado" and not details.strip():
            raise ValueError("Descreva o tema e a personalização dos brigadeiros.")
    normalized_extras = []
    for extra in extras or []:
        amount = int(extra["amount_cents"])
        if amount < 0 or not extra["name"].strip():
            raise ValueError("Adicional inválido.")
        normalized = {"name": extra["name"].strip(), "amount_cents": amount, "gift": bool(extra.get("gift"))}
        if "quantity" in extra:
            units = decimal(extra["quantity"])
            unit_cents = int(extra.get("unit_cents", 0))
            if units <= 0 or units != units.to_integral_value() or unit_cents < 0:
                raise ValueError("Informe quantidade inteira positiva e preço válido para o adicional.")
            expected = int(units) * unit_cents
            if amount != expected:
                raise ValueError("O total do adicional não corresponde à quantidade e ao valor unitário.")
            normalized.update({"quantity": int(units), "unit_cents": unit_cents})
        for field in ("brigadeiro_type", "flavors", "personalization", "reference_photo"):
            if field in extra:
                normalized[field] = extra[field]
        if extra.get("brigadeiro_type"):
            kind = extra["brigadeiro_type"]
            if kind not in BRIGADEIRO_TYPES or not extra.get("flavors"):
                raise ValueError("Selecione o tipo e os sabores dos brigadeiros adicionais.")
            if any(flavor not in BRIGADEIRO_FLAVORS[kind] for flavor in extra["flavors"]):
                raise ValueError("Selecione sabores válidos para os brigadeiros adicionais.")
            if kind == "Personalizado" and not extra.get("personalization", "").strip():
                raise ValueError("Descreva a personalização dos brigadeiros adicionais.")
        normalized_extras.append(normalized)
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
        "description": product.get("description", ""), "composition": list(product.get("composition", [])),
        "reference_photo": reference_photo,
        "negotiation": {"extra_fillings": excess, "under_minimum": under_minimum, "notes": negotiation_notes.strip() if (excess or under_minimum) else ""},
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
