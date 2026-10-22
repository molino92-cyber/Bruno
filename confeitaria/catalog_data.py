"""Produtos-base e exemplos editáveis; preços ilustrativos só na demonstração."""
from .domain import CATEGORIES, SIMPLE_FILLINGS, SPECIAL_FILLINGS

SIMPLE_DESCRIPTION = "Bolo por quilo com massa branca e recheios simples: " + ", ".join(SIMPLE_FILLINGS) + ". Padrão: mínimo de 2 kg, com até dois recheios. Abaixo de 2 kg, um recheio e autorização da confeiteira. Decoração e adicionais à parte."
SPECIAL_DESCRIPTION = "Bolo por quilo com recheios especiais: " + ", ".join(SPECIAL_FILLINGS) + ". Padrão: mínimo de 2 kg, com até dois recheios. Abaixo de 2 kg, um recheio e autorização da confeiteira. Decoração e adicionais à parte."
KITS = [
    {"name": "Kit Festa 1", "composition": ["1 bolo simples de 2 kg", "10 brigadeiros tradicionais", "5 cupcakes"], "demo_cents": 21000, "asset": "kit1"},
    {"name": "Kit Festa 2", "composition": ["1 bolo simples de 2 kg", "20 brigadeiros tradicionais", "10 cupcakes"], "demo_cents": 28000, "asset": "kit2"},
    {"name": "Kit Festa 3", "composition": ["1 bolo especial de 3 kg", "40 brigadeiros tradicionais", "15 cupcakes", "10 mini donuts"], "demo_cents": 46000, "asset": "kit3"},
    {"name": "Kit Festa 4", "composition": ["1 bolo especial de 4 kg", "60 brigadeiros especiais", "20 cupcakes", "20 mini donuts"], "demo_cents": 68000, "asset": "kit4"},
]


def product_templates():
    rows = [
        {"name": "Bolo Simples", "category": CATEGORIES[0], "description": SIMPLE_DESCRIPTION, "unit": "kg", "price_cents": 7500, "demo_cents": 7500, "asset": "bolo-simples"},
        {"name": "Bolo Especial", "category": CATEGORIES[1], "description": SPECIAL_DESCRIPTION, "unit": "kg", "price_cents": 8500, "demo_cents": 8500, "asset": "bolo-especial"},
        {"name": "Cento de Brigadeiros", "category": CATEGORIES[2], "description": "100 brigadeiros tradicionais. Sabores: Chocolate e Beijinho. Escolha um sabor ou divida em 50 unidades de cada. Forminhas inclusas.", "unit": "cento", "demo_cents": 12000, "asset": "brigadeiros"},
        {"name": "Brigadeiros Especiais", "category": CATEGORIES[2], "description": "100 brigadeiros especiais. Sabores: Nutella, Brigadeiro Rocher, Ninho e Ninho com Nutella. Permite divisão 50/50.", "unit": "cento", "demo_cents": 18000, "asset": "brigadeiros-especiais"},
        {"name": "Brigadeiros Personalizados", "category": CATEGORIES[2], "description": "100 brigadeiros com decoração temática. Escolha o sabor base e descreva as cores, o tema e os detalhes da personalização. Foto de referência opcional.", "unit": "cento", "demo_cents": 22000, "asset": "brigadeiros-personalizados"},
        {"name": "Cupcake", "category": CATEGORIES[4], "description": "Cupcake individual com massa de baunilha, recheio de chocolate ou ninho e cobertura de chantininho. Informe as cores e o tema no orçamento.", "unit": "un", "demo_cents": 800, "asset": "cupcake"},
        {"name": "Mini Donut", "category": CATEGORIES[5], "description": "Mini donut com cobertura de chocolate ou glacê e confeitos. Ideal para mesas de festa e lembrancinhas. Cores podem ser personalizadas.", "unit": "un", "demo_cents": 400, "asset": "donut"},
        {"name": "Topo de Bolo", "category": CATEGORIES[6], "description": "Topo em papel personalizado com nome, idade e tema. Anexe a referência do modelo e informe os detalhes. Pode ser marcado como cortesia.", "unit": "un", "demo_cents": 2500, "asset": "topo"},
    ]
    rows += [{**kit, "category": CATEGORIES[3], "unit": "un", "description": "Kit para comemorar em casa. Inclui: " + "; ".join(kit["composition"]) + ". Composição ilustrativa, editável pela confeiteira."} for kit in KITS]
    return rows
