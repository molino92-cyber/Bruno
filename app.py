"""Aplicativo local: execute com `streamlit run app.py`."""
import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from html import escape

import streamlit as st

from confeitaria.domain import (BRIGADEIRO_TYPES, CATEGORIES, EXTRAS, PAYMENT_METHODS, SIMPLE_FILLINGS,
                                SPECIAL_FILLINGS, UNITS, active_price, brl, cents, make_line, quantity_text, totals)
from confeitaria.pdf import formatted_date, generate_pdf
from confeitaria.storage import Store, inventory_cost

st.set_page_config(page_title="Doce Ateliê · Gestão", page_icon="🧁", layout="wide")
st.markdown("""<style>
:root {--primary-color:#974e65;}
.stApp {background:#fcfaf7;}
[data-testid="stSidebar"] {background:#f4ece8;}
[data-testid="stMetric"] {background:white;border:1px solid #eadfd9;border-radius:14px;padding:18px;}
h1,h2,h3 {color:#603c49;}
.eyebrow {font-size:.78rem;letter-spacing:.2em;color:#976778;font-weight:600;margin-bottom:8px;}
.hero {padding:8px 0 18px;border-bottom:1px solid #e7dbd5;margin-bottom:24px;}
.hero h1 {font-family:Georgia,serif;font-size:2.7rem;margin:0;}
.hero p {color:#7d6e70;margin:8px 0;}
.tag {display:inline-block;background:#f8e5eb;color:#87445b;padding:3px 10px;border-radius:20px;font-size:.8rem;}
.placeholder {height:145px;background:linear-gradient(135deg,#f3e4df,#f9f1e7);border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:3rem;margin-bottom:12px;}
.stButton>button {border-radius:9px;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:14px;}
@media print {[data-testid="stSidebar"] {display:none;}}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def get_store():
    return Store()


store = get_store()


def hero(label, title, subtitle):
    st.markdown(f'<div class="hero"><div class="eyebrow">{escape(label)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>', unsafe_allow_html=True)


def image(name, width=None):
    path = store.image_path(name)
    if path:
        st.image(str(path), width=width or "stretch")
    else:
        st.markdown('<div class="placeholder">🧁</div>', unsafe_allow_html=True)


def money(label, value=0, key=None, **kwargs):
    return cents(st.number_input(label, min_value=0.0, value=float(value) / 100, step=1.0, format="%.2f", key=key, **kwargs))


def flash(message):
    st.session_state["notice"] = message
    st.rerun()


def go(page):
    st.session_state["page"] = page


def fresh_draft(quote=None):
    st.session_state["draft"] = dict(quote or {"lines": []})
    st.session_state["draft_version"] = st.session_state.get("draft_version", 0) + 1
    st.session_state["page"] = "Novo orçamento"


def quote_rows(quotes):
    return [{"Pedido": f"#{q['id']:04d}", "Cliente": q["customer"]["name"], "Saída": formatted_date(q["event_at"]),
             "Status": q["status"], "Total": brl(q["totals"]["total_cents"]), "Recebido": brl(q["paid_cents"]), "Saldo": brl(q["balance_cents"])} for q in quotes]


def dashboard():
    hero("SEU NEGÓCIO, COM CARINHO", "Uma cozinha organizada.", "Pedidos, produção e números para cuidar de cada detalhe.")
    quotes = store.quotes()
    approved = [q for q in quotes if "Data Reservada" in q["status"]]
    today = [q for q in approved if q["event_at"][:10] == date.today().isoformat()]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Saídas de hoje", len(today))
    c2.metric("Datas reservadas", len(approved))
    c3.metric("A receber · reservados", brl(sum(q["balance_cents"] for q in approved)))
    c4.metric("Recebido · acumulado", brl(sum(q["paid_cents"] for q in quotes)))
    st.write("")
    left, right = st.columns([2, 1])
    with left:
        st.subheader("Próximas encomendas")
        upcoming = [q for q in approved if q["event_at"][:10] >= date.today().isoformat()][:8]
        if upcoming:
            st.dataframe(quote_rows(upcoming), hide_index=True, width="stretch")
        else:
            st.info("As encomendas aparecem aqui quando o sinal de pelo menos 50% é recebido.")
        st.button("Criar orçamento", type="primary", on_click=fresh_draft)
    with right:
        with st.container(border=True):
            st.subheader("Vitrine do dia")
            promoted = [p for p in store.list("products") if p["active"] and active_price(p)[1]]
            if promoted:
                for product in promoted:
                    st.write(f"**{product['name']}** · {brl(active_price(product)[0])}/{product['unit']}")
            else:
                st.write("Nenhuma promoção vigente. Prepare ofertas na aba Catálogo.")
            unpriced = sum(1 for p in store.list("products") if p["active"] and p["price_cents"] == 0)
            if unpriced:
                st.caption(f"{unpriced} produtos aguardam definição de preço.")


def catalog():
    hero("CATÁLOGO & VITRINE", "Feitos para encantar.", "Fotos locais, descrições e promoções com início e fim definidos.")
    products = store.list("products")
    showcase, editor = st.tabs(["Vitrine visual", "Cadastrar / editar"])
    with showcase:
        col1, col2 = st.columns([2, 1])
        search = col1.text_input("Buscar produto", placeholder="Nome ou descrição…")
        category = col2.selectbox("Categoria", ["Todas"] + CATEGORIES)
        visible = [p for p in products if p["active"] and (category == "Todas" or p["category"] == category) and search.casefold() in (p["name"] + " " + p["description"]).casefold()]
        if not visible:
            st.info("Nenhum produto encontrado.")
        columns = st.columns(3)
        for i, product in enumerate(visible):
            with columns[i % 3], st.container(border=True):
                image(product["photos"][0] if product["photos"] else "")
                st.caption(product["category"])
                st.subheader(product["name"])
                price, promotional = active_price(product)
                if promotional:
                    st.markdown('<span class="tag">PROMOÇÃO</span>', unsafe_allow_html=True)
                    st.markdown(f"~~{brl(product['price_cents'])}~~ → **{brl(price)} / {product['unit']}**")
                    st.caption(f"Até {date.fromisoformat(product['promo_end']):%d/%m/%Y}")
                elif price:
                    st.markdown(f"**{brl(price)} / {product['unit']}**")
                else:
                    st.caption("Preço a cadastrar")
                st.write(product["description"])
                if len(product["photos"]) > 1:
                    with st.expander("Ver galeria completa"):
                        for photo in product["photos"]:
                            image(photo)
    with editor:
        selected = st.selectbox("Produto para editar", [None] + [p["id"] for p in products], format_func=lambda x: "＋ Novo produto" if x is None else next(p["name"] for p in products if p["id"] == x))
        p = next((p for p in products if p["id"] == selected), {})
        with st.form(f"product_{selected}"):
            a, b = st.columns(2)
            name = a.text_input("Nome do produto *", p.get("name", ""))
            category = b.selectbox("Categoria *", CATEGORIES, index=CATEGORIES.index(p.get("category", CATEGORIES[0])))
            description = st.text_area("Descrição completa", p.get("description", ""))
            a, b = st.columns(2)
            price = money("Preço normal (R$ por kg / cento / unidade)", p.get("price_cents", 0), key=f"price_{selected}")
            active = st.checkbox("Visível no catálogo", value=bool(p.get("active", 1)))
            st.caption("A unidade é definida pela categoria. Bolos em kg; brigadeiros em cento; demais em unidades.")
            st.markdown("**Promoção do dia / mês**")
            enabled = st.checkbox("Ativar promoção no intervalo abaixo", value=bool(p.get("promo_enabled", 0)))
            promo = money("Preço promocional (R$)", p.get("promo_cents", 0), key=f"promo_{selected}")
            a, b = st.columns(2)
            start = a.date_input("Início da promoção", date.fromisoformat(p["promo_start"]) if p.get("promo_start") else date.today())
            end = b.date_input("Fim da promoção", date.fromisoformat(p["promo_end"]) if p.get("promo_end") else date.today())
            old_photos = p.get("photos", [])
            kept = st.multiselect("Fotos atuais a manter", old_photos, default=old_photos, format_func=lambda x: f"Foto {old_photos.index(x) + 1}")
            uploads = st.file_uploader("Adicionar fotos · até 3 no total · 10 MB cada", ["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
            if st.form_submit_button("Salvar produto", type="primary"):
                try:
                    if len(kept) + len(uploads) > 3:
                        raise ValueError("Mantenha no máximo três fotos no total.")
                    photos = kept + [store.save_image(upload) for upload in uploads]
                    store.save_product({"name": name.strip(), "category": category, "description": description.strip(), "unit": "un",
                                        "price_cents": price, "active": int(active), "promo_enabled": int(enabled), "promo_cents": promo,
                                        "promo_start": start.isoformat(), "promo_end": end.isoformat(), "photos": photos}, selected)
                    flash("Produto salvo. Orçamentos anteriores mantêm os preços registrados.")
                except ValueError as exc:
                    st.error(str(exc))


def inventory():
    hero("INSUMOS & MATERIAIS", "Tudo no seu lugar.", "Estoque visual e custo por conteúdo. As movimentações são manuais; não há baixa automática por receita.")
    items = store.list("inventory")
    stock_tab, edit_tab = st.tabs(["Estoque visual", "Cadastrar / atualizar"])
    with stock_tab:
        search = st.text_input("Buscar insumo ou marca")
        filtered = [i for i in items if search.casefold() in (i["name"] + " " + i["brand"]).casefold()]
        st.metric("Valor estimado em estoque", brl(cents(sum(Decimal(i["stock"]) * i["paid_cents"] / 100 for i in items))))
        columns = st.columns(3)
        for n, item in enumerate(filtered):
            with columns[n % 3], st.container(border=True):
                image(item["photo"])
                st.subheader(item["name"])
                st.caption(item["brand"] or "Marca não informada")
                st.write(f"Conteúdo: {quantity_text(item['content'])} {item['content_unit']}")
                st.write(f"Estoque: {quantity_text(item['stock'])} {item['package_unit']}")
                st.write(f"Valor por embalagem: {brl(item['paid_cents'])}")
                unit_cost = f"{inventory_cost(item):.4f}".replace(".", ",")
                st.markdown(f"**Custo unitário: R$ {unit_cost} / {item['content_unit']}**")
        if not filtered:
            st.info("Cadastre seus insumos e materiais, com a foto da marca ou embalagem.")
    with edit_tab:
        selected = st.selectbox("Insumo", [None] + [i["id"] for i in items], format_func=lambda x: "＋ Novo insumo" if x is None else next(i["name"] for i in items if i["id"] == x))
        item = next((i for i in items if i["id"] == selected), {})
        with st.form(f"inventory_{selected}"):
            a, b = st.columns(2)
            name = a.text_input("Nome *", item.get("name", ""))
            brand = b.text_input("Marca", item.get("brand", ""))
            a, b = st.columns(2)
            content = a.number_input("Conteúdo por embalagem *", min_value=0.001, value=float(item.get("content", 1000)), format="%.3f")
            content_unit = b.selectbox("Unidade do conteúdo", ["g", "ml", "unidade"], index=["g", "ml", "unidade"].index(item.get("content_unit", "g")))
            a, b = st.columns(2)
            stock = a.number_input("Quantidade em estoque (embalagens)", min_value=0.0, value=float(item.get("stock", 0)), format="%.3f")
            package_unit = b.selectbox("Unidade de estoque", UNITS, index=UNITS.index(item.get("package_unit", "Un")))
            paid = money("Valor pago por embalagem (R$)", item.get("paid_cents", 0), key=f"paid_stock_{selected}")
            st.caption("Exemplo: caixa de leite de 1.000 ml a R$ 5,00 → custo de R$ 0,0050/ml. Estoque de 3 Cx = 3.000 ml.")
            upload = st.file_uploader("Foto do insumo / embalagem", ["jpg", "jpeg", "png", "webp"])
            remove = st.checkbox("Remover foto atual", key=f"remove_inventory_{selected}")
            if st.form_submit_button("Salvar insumo", type="primary"):
                try:
                    photo = store.save_image(upload) if upload else "" if remove else item.get("photo", "")
                    store.save_inventory({"name": name.strip(), "brand": brand.strip(), "content": str(content), "content_unit": content_unit,
                                          "stock": str(stock), "package_unit": package_unit, "paid_cents": paid, "photo": photo}, selected)
                    flash("Insumo e custo unitário atualizados.")
                except ValueError as exc:
                    st.error(str(exc))


def customers():
    hero("CLIENTES", "Cada pedido tem uma história.", "Contatos, endereços e histórico de encomendas em um só lugar.")
    clients = store.list("customers")
    selected = st.selectbox("Cliente", [None] + [c["id"] for c in clients], format_func=lambda x: "＋ Novo cliente" if x is None else next(f"{c['name']} · {c['phone']}" for c in clients if c["id"] == x))
    client = next((c for c in clients if c["id"] == selected), {})
    left, right = st.columns([2, 1])
    with left:
        with st.form(f"customer_{selected}"):
            name = st.text_input("Nome completo *", client.get("name", ""))
            a, b = st.columns(2)
            phone = a.text_input("Telefone / WhatsApp com DDD *", client.get("phone", ""))
            cpf = b.text_input("CPF (opcional)", client.get("cpf", ""))
            address = st.text_area("Endereço de entrega", client.get("address", ""))
            upload = st.file_uploader("Foto do cliente", ["jpg", "jpeg", "png", "webp"])
            remove = st.checkbox("Remover foto atual", key=f"remove_customer_{selected}")
            if st.form_submit_button("Salvar cliente", type="primary"):
                try:
                    photo = store.save_image(upload) if upload else "" if remove else client.get("photo", "")
                    store.save_customer({"name": name.strip(), "phone": phone.strip(), "cpf": cpf, "address": address.strip(), "photo": photo}, selected)
                    flash("Cliente salvo.")
                except ValueError as exc:
                    st.error(str(exc))
    with right:
        if client.get("photo"):
            image(client["photo"])
        st.caption("Os dados são armazenados apenas no banco local. O backup contém dados pessoais e deve ser guardado com cuidado.")
    if selected:
        st.subheader("Histórico de pedidos")
        history = store.quotes(selected)
        if history:
            st.dataframe(quote_rows(history), hide_index=True, width="stretch")
        else:
            st.info("Este cliente ainda não tem orçamentos.")


def quote_editor():
    draft = st.session_state.setdefault("draft", {"lines": []})
    prefix = f"draft_{st.session_state.get('draft_version', 0)}_"
    key = lambda name: prefix + name
    editing = draft.get("id") or draft.get("quote_id")
    hero("ORÇAMENTO PERSONALIZADO", f"{'Editar #' + str(editing).zfill(4) if editing else 'Do desejo à encomenda.'}", "Monte os sabores, confira as condições e salve o pedido com validade de 7 dias.")
    st.button("Limpar e iniciar outro orçamento", on_click=fresh_draft)
    clients = store.list("customers")
    if not clients:
        st.info("Cadastre o primeiro cliente antes de montar um orçamento.")
        st.button("Cadastrar cliente", on_click=go, args=("Clientes",))
        return
    ids = [c["id"] for c in clients]
    selected_id = draft.get("customer_id", ids[0])
    customer_id = st.selectbox("Cliente *", ids, index=ids.index(selected_id) if selected_id in ids else 0,
                               format_func=lambda x: next(f"{c['name']} · {c['phone']}" for c in clients if c["id"] == x), key=key("client"))
    client = next(c for c in clients if c["id"] == customer_id)
    a, b, c = st.columns(3)
    initial_event = datetime.fromisoformat(draft["event_at"]) if draft.get("event_at") else datetime.combine(date.today() + timedelta(days=7), time(14))
    event_date = a.date_input("Data de saída / retirada *", initial_event.date(), key=key("event_date"))
    event_time = b.time_input("Horário de saída *", initial_event.time(), key=key("event_time"))
    fulfillment = c.selectbox("Modalidade", ["Retirada", "Entrega"], index=1 if draft.get("fulfillment") == "Entrega" else 0, key=key("fulfillment"))
    address = st.text_input("Endereço para este pedido (se entrega)", draft.get("delivery_address", client["address"]), key=key("address") + str(customer_id))

    st.subheader("1 · Monte os itens")
    products = [p for p in store.list("products") if p["active"]]
    if not products:
        st.warning("Ative ou cadastre produtos no catálogo para adicionar itens.")
    else:
        with st.container(border=True):
            product_id = st.selectbox("Produto", [p["id"] for p in products], format_func=lambda x: next(p["name"] for p in products if p["id"] == x), key=key("product"))
            product = next(p for p in products if p["id"] == product_id)
            product_key = key(f"product_{product_id}_")
            price, promo = active_price(product)
            st.caption(f"Preço vigente: {brl(price)}/{product['unit']}" + (" · PROMOÇÃO" if promo else ""))
            is_cake = product["category"] in CATEGORIES[:2]
            min_qty = 2.0 if product["category"] == CATEGORIES[0] else 0.1 if is_cake else 1.0
            quantity = st.number_input(f"Quantidade ({product['unit']})", min_value=min_qty, max_value=100000.0, value=max(min_qty, 1.0), step=0.1 if is_cake else 1.0, format="%.2f" if is_cake else "%.0f", key=product_key + "qty")
            fillings, extras, flavors = [], [], []
            brigadeiro_type, split = None, False
            if is_cake:
                st.markdown("**Recheios simples**" if product["category"] == CATEGORIES[0] else "**Recheios especiais**")
                options = SIMPLE_FILLINGS if product["category"] == CATEGORIES[0] else SPECIAL_FILLINGS
                cols = st.columns(2)
                for i, filling in enumerate(options):
                    if cols[i % 2].checkbox(filling, key=product_key + filling):
                        fillings.append(filling)
                st.caption("Os adicionais abaixo têm preço pelo item inteiro, não por kg. Preencha manualmente ou marque cortesia.")
                for extra in EXTRAS:
                    if st.checkbox(extra, key=product_key + extra):
                        a, b = st.columns(2)
                        amount = money(f"{extra} · valor total (R$)", key=product_key + extra + "amount")
                        free = b.checkbox("Brinde / Cortesia", key=product_key + extra + "gift")
                        extras.append({"name": extra, "amount_cents": amount, "gift": free})
            if product["category"] == CATEGORIES[2]:
                brigadeiro_type = st.selectbox("Categoria dos brigadeiros", BRIGADEIRO_TYPES, key=product_key + "type")
                st.caption("O preço é o deste produto no catálogo. Cadastre produtos separados para categorias com preços diferentes.")
                split = st.checkbox("Dividir cento em 50/50", key=product_key + "split")
                flavors = [st.text_input("Sabor 1", key=product_key + "flavor1")]
                if split:
                    flavors.append(st.text_input("Sabor 2", key=product_key + "flavor2"))
                    st.caption("Cada cento contém 50 unidades do sabor 1 e 50 do sabor 2.")
            details = st.text_area("Detalhes deste item (tamanho, decoração, personalização)", key=product_key + "details")
            gift = st.checkbox("Este item inteiro é Brinde / Cortesia", key=product_key + "gift")
            if st.button("＋ Adicionar ao orçamento", type="primary", key=key("add")):
                try:
                    draft["lines"].append(make_line(product, quantity, fillings, extras, details, gift, brigadeiro_type, split, flavors))
                    st.toast("Item adicionado ao orçamento.")
                except ValueError as exc:
                    st.error(str(exc))

    st.subheader("2 · Confira sua composição")
    if not draft["lines"]:
        st.info("Seu orçamento ainda está vazio.")
    for i, line in enumerate(draft["lines"]):
        with st.container(border=True):
            left, right = st.columns([5, 1])
            left.markdown(f"**{quantity_text(line['quantity'])} {line['unit']} · {line['name']}**" + (" · [BRINDE]" if line["gift"] else ""))
            left.write(" · ".join(line["fillings"] + line["flavors"]))
            for extra in line["extras"]:
                left.write(f"＋ {extra['name']} · " + ("[BRINDE]" if extra["gift"] or line["gift"] else brl(extra["amount_cents"])))
            if line["details"]:
                left.caption(line["details"])
            right.markdown(f"**{brl(line['total_cents'])}**")
            if right.button("Remover", key=key(f"remove_{i}")):
                draft["lines"].pop(i)
                st.rerun()

    st.subheader("3 · Condições e cuidados")
    a, b = st.columns(2)
    payment_method = a.selectbox("Forma de pagamento acordada", PAYMENT_METHODS, index=PAYMENT_METHODS.index(draft.get("payment_method", "PIX")), key=key("method"))
    pix_enabled = b.checkbox("Aplicar desconto PIX / Dinheiro manualmente", value=bool(draft.get("pix_enabled", False)), disabled=payment_method == "Cartão", key=key("pix"))
    if payment_method == "Cartão":
        pix_enabled = False
    pix_percent = st.number_input("Percentual PIX / Dinheiro (%)", min_value=0.0, max_value=100.0, value=float(draft.get("pix_percent", 0)), step=0.5, disabled=not pix_enabled, key=key("percent"))
    if any(line["promotional"] for line in draft["lines"]):
        st.warning("Há itens em promoção. Confira antes de ativar o desconto PIX: ele será acumulado somente se você marcar a opção.")
    a, b = st.columns(2)
    with a:
        discount = money("Desconto manual geral (R$)", draft.get("discount_cents", 0), key=key("discount"))
    with b:
        delivery = money("Taxa de entrega / frete (R$)", draft.get("delivery_cents", 0), key=key("delivery"))
    st.caption("O percentual PIX é aplicado sobre os itens após o desconto geral. O frete não recebe desconto percentual.")
    notes = st.text_area("Observações gerais · avisos e condições para o cliente", draft.get("notes", ""), key=key("notes"))
    production_notes = st.text_area("Decoração, alergias, restrições e transporte · também aparecem na ficha da cozinha", draft.get("production_notes", ""), key=key("production"))
    draft.update({"customer_id": customer_id, "event_at": datetime.combine(event_date, event_time).isoformat(timespec="minutes"),
                  "fulfillment": fulfillment, "delivery_address": address, "payment_method": payment_method,
                  "pix_enabled": pix_enabled, "pix_percent": str(pix_percent), "discount_cents": discount,
                  "delivery_cents": delivery, "notes": notes, "production_notes": production_notes})
    reference = st.file_uploader("Foto de referência do bolo / pedido", ["jpg", "jpeg", "png", "webp"], key=key("reference"))
    remove_ref = st.checkbox("Remover referência anterior", key=key("remove_ref"))
    if draft.get("reference_photo") and not remove_ref:
        image(draft["reference_photo"], width=220)
    try:
        summary = totals(draft["lines"], discount, delivery, pix_enabled, pix_percent, payment_method)
    except ValueError as exc:
        st.error(str(exc))
        return
    a, b, c, d = st.columns(4)
    a.metric("Preço Cartão", brl(summary["card_cents"]))
    b.metric("PIX / Dinheiro" if pix_enabled else "Total acordado", brl(summary["total_cents"]))
    c.metric("Entrada mínima · 50%", brl(summary["deposit_cents"]))
    d.metric("Descontos", brl(discount + summary["pix_discount_cents"]))
    if st.button("Salvar orçamento", type="primary", disabled=not draft["lines"], key=key("save")):
        try:
            if fulfillment == "Entrega" and not address.strip():
                raise ValueError("Informe o endereço de entrega.")
            ref = store.save_image(reference) if reference else "" if remove_ref else draft.get("reference_photo", "")
            payload = {"customer_id": customer_id, "event_at": datetime.combine(event_date, event_time).isoformat(timespec="minutes"),
                       "fulfillment": fulfillment, "delivery_address": address.strip(), "lines": draft["lines"],
                       "payment_method": payment_method, "pix_enabled": pix_enabled, "pix_percent": str(pix_percent),
                       "discount_cents": discount, "delivery_cents": delivery, "notes": notes.strip(),
                       "production_notes": production_notes.strip(), "reference_photo": ref}
            quote_id = store.save_quote(payload, editing)
            draft["quote_id"] = quote_id
            draft["reference_photo"] = ref
            st.success(f"Orçamento #{quote_id:04d} salvo. Acesse Orçamentos e pagamentos para gerar PDFs e registrar recebimentos.")
        except ValueError as exc:
            st.error(str(exc))


def quotes_page():
    hero("PEDIDOS & RECEBIMENTOS", "Combinado, registrado.", "Receba o sinal, reserve a data e acompanhe o saldo até a entrega.")
    quotes = store.quotes()
    if not quotes:
        st.info("Nenhum orçamento salvo ainda.")
        st.button("Criar primeiro orçamento", on_click=fresh_draft)
        return
    a, b = st.columns(2)
    search = a.text_input("Buscar cliente ou número do orçamento")
    status_filter = b.selectbox("Filtrar status", ["Todos", "Em Aberto", "Vencido", "Aprovado / Data Reservada", "Quitado / Data Reservada", "Entregue"])
    filtered = [q for q in quotes if (status_filter == "Todos" or q["status"] == status_filter) and (search.casefold() in q["customer"]["name"].casefold() or search.lstrip("#").isdigit() and int(search.lstrip("#")) == q["id"])]
    if not filtered:
        st.info("Nenhum orçamento com este filtro.")
        return
    st.dataframe(quote_rows(filtered), hide_index=True, width="stretch")
    quote_id = st.selectbox("Abrir pedido", [q["id"] for q in filtered], format_func=lambda x: next(f"#{q['id']:04d} · {q['customer']['name']} · {formatted_date(q['event_at'])}" for q in filtered if q["id"] == x))
    q = next(q for q in filtered if q["id"] == quote_id)
    st.subheader(f"#{q['id']:04d} · {q['customer']['name']}")
    st.info(q["status"] + f" · Validade: {date.fromisoformat(q['valid_until']):%d/%m/%Y}")
    a, b, c, d = st.columns(4)
    a.metric("Total acordado", brl(q["totals"]["total_cents"]))
    b.metric("Entrada mínima · 50%", brl(q["totals"]["deposit_cents"]))
    c.metric("Recebido", brl(q["paid_cents"]))
    d.metric("Saldo devedor", brl(q["balance_cents"]))
    st.caption("O saldo é calculado pelos recebimentos reais. Após um sinal exato de 50%, restam 50% a pagar.")
    detail, payments_tab, docs = st.tabs(["Detalhes", "Recebimentos", "PDFs e impressão"])
    with detail:
        st.write(f"**Saída:** {formatted_date(q['event_at'])} · {q['fulfillment']}")
        st.write(f"**Endereço:** {q['delivery_address'] or 'Retirada na loja'}")
        for line in q["lines"]:
            with st.container(border=True):
                st.write(f"**{quantity_text(line['quantity'])} {line['unit']} · {line['name']}**" + (" [BRINDE]" if line["gift"] else "") + f" · {brl(line['total_cents'])}")
                if line["fillings"]:
                    st.write("Recheios: " + ", ".join(line["fillings"]))
                if line["flavors"]:
                    st.write(("Divisão 50/50: " if line["split"] else "Sabor: ") + " / ".join(line["flavors"]) + f" · {line['brigadeiro_type']}")
                for extra in line["extras"]:
                    st.write(f"＋ {extra['name']} · " + ("[BRINDE]" if extra["gift"] or line["gift"] else brl(extra["amount_cents"])))
                st.write(line["details"])
        st.write("**Observações gerais:**", q["notes"] or "—")
        st.write("**Produção / alergias / transporte:**", q["production_notes"] or "—")
        if q.get("reference_photo"):
            image(q["reference_photo"], width=280)
        if q["paid_cents"] == 0 and not q["delivered"]:
            st.button("Editar este orçamento", on_click=fresh_draft, args=(q,))
        else:
            st.caption("Pedidos com recebimentos têm composição e valores preservados.")
        if q["status"] == "Vencido" and st.button("Renovar validade por 7 dias"):
            store.renew_quote(q["id"])
            flash("Validade renovada; confira se a data de produção ainda está disponível.")
    with payments_tab:
        history = store.payments(q["id"])
        if history:
            st.dataframe([{"Recebido em": formatted_date(p["received_at"]), "Valor": brl(p["amount_cents"]), "Forma": p["method"], "Descrição": p["note"]} for p in history], hide_index=True, width="stretch")
        if q["balance_cents"] > 0 and q["status"] != "Vencido":
            remaining_deposit = max(0, q["totals"]["deposit_cents"] - q["paid_cents"])
            with st.form(f"receive_{q['id']}_{q['paid_cents']}"):
                is_deposit = st.checkbox("Entrada de 50% recebida (sinal)", value=remaining_deposit > 0)
                amount = money("Valor recebido agora (R$)", remaining_deposit or q["balance_cents"], key=f"receive_amount_{q['id']}_{q['paid_cents']}")
                method = st.selectbox("Forma deste recebimento", PAYMENT_METHODS, index=PAYMENT_METHODS.index(q["payment_method"]))
                note = st.text_input("Descrição / comprovante (opcional)")
                confirmed = st.checkbox("Confirmo que este valor já foi recebido")
                if st.form_submit_button("Registrar recebimento", type="primary"):
                    try:
                        if not confirmed:
                            raise ValueError("Confirme o recebimento antes de registrá-lo.")
                        store.add_payment(q["id"], amount, method, ("Sinal · " if is_deposit else "Pagamento · ") + note)
                        flash("Recebimento registrado. Status e saldo atualizados.")
                    except ValueError as exc:
                        st.error(str(exc))
        elif q["status"] == "Vencido":
            st.warning("Renove o orçamento na aba Detalhes antes de receber.")
        else:
            st.success("Pagamento integral recebido.")
        if q["balance_cents"] == 0 and not q["delivered"]:
            if st.button("Registrar entrega / retirada concluída", key=f"delivered_{q['id']}"):
                store.mark_delivered(q["id"])
                flash("Entrega registrada.")
    with docs:
        st.write("Baixe o PDF e use o comando Imprimir do seu leitor de PDFs.")
        st.caption("O orçamento usa os dados e as condições da loja registrados quando foi salvo.")
        a, b = st.columns(2)
        a.download_button("↓ Orçamento do cliente", generate_pdf(q, store), file_name=f"orcamento-{q['id']:04d}.pdf", mime="application/pdf", key=f"pdf_client_{q['id']}")
        b.download_button("↓ Ficha da cozinha · sem preços", generate_pdf(q, store, kitchen=True), file_name=f"producao-{q['id']:04d}.pdf", mime="application/pdf", key=f"pdf_kitchen_{q['id']}")


def agenda():
    hero("AGENDA DE PRODUÇÃO", "Tempo para cada detalhe.", "Apenas encomendas com entrada mínima de 50% e ainda não entregues aparecem na produção.")
    approved = [q for q in store.quotes() if "Data Reservada" in q["status"]]
    month = st.date_input("Mês da agenda", value=date.today(), key="agenda_month")
    selected = st.session_state.get("agenda_day", date.today())
    st.subheader(f"{['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro'][month.month - 1]} {month.year}")
    columns = st.columns(7)
    for col, day in zip(columns, ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]):
        col.markdown(f"**{day}**")
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(month.year, month.month):
        for col, day in zip(st.columns(7), week):
            if day:
                day_date = date(month.year, month.month, day)
                count = sum(1 for q in approved if q["event_at"][:10] == day_date.isoformat())
                if col.button(f"{day}" + (f" · {count} pedido(s)" if count else ""), key=f"day_{day_date}", type="primary" if day_date == selected else "secondary", width="stretch"):
                    st.session_state["agenda_day"] = day_date
                    st.rerun()
    st.divider()
    selected = st.date_input("Encomendas do dia", value=selected, key="agenda_selected_date")
    # O date_input mantém seu estado; o clique no calendário atualiza este widget no próximo ciclo.
    daily = [q for q in approved if q["event_at"][:10] == selected.isoformat()]
    if not daily:
        st.info("Nenhuma encomenda aprovada para esta data.")
    for q in daily:
        with st.container(border=True):
            st.subheader(f"{datetime.fromisoformat(q['event_at']):%H:%M} · {q['customer']['name']}")
            st.caption(f"Pedido #{q['id']:04d} · {q['fulfillment']}")
            for line in q["lines"]:
                st.write(f"{quantity_text(line['quantity'])} {line['unit']} · {line['name']} · " + ", ".join(line["fillings"] + line["flavors"]))
            st.write(q["production_notes"] or "Sem observações de produção.")
            st.download_button("Ficha de produção", generate_pdf(q, store, True), f"producao-{q['id']:04d}.pdf", mime="application/pdf", key=f"agenda_pdf_{q['id']}")


def settings_page():
    hero("CONFIGURAÇÕES", "A identidade da sua confeitaria.", "Personalize os documentos e mantenha uma cópia segura dos dados locais.")
    settings = store.settings()
    with st.form("settings"):
        name = st.text_input("Nome da confeitaria *", settings["name"])
        a, b = st.columns(2)
        phone = a.text_input("Telefone / WhatsApp da loja", settings["phone"])
        document = b.text_input("CNPJ / CPF da loja", settings["document"])
        address = st.text_area("Endereço da loja", settings["address"])
        days = st.number_input("Alterações aceitas até quantos dias antes do evento?", min_value=0, max_value=365, value=int(settings["change_days"]))
        logo = st.file_uploader("Logo para os PDFs", ["jpg", "jpeg", "png", "webp"])
        remove_logo = st.checkbox("Remover logo atual")
        if st.form_submit_button("Salvar configurações", type="primary"):
            try:
                logo_name = store.save_image(logo) if logo else "" if remove_logo else settings["logo"]
                store.save_settings({"name": name.strip(), "phone": phone.strip(), "document": document.strip(), "address": address.strip(), "change_days": int(days), "logo": logo_name})
                flash("Configurações salvas. Serão usadas nos próximos orçamentos salvos.")
            except ValueError as exc:
                st.error(str(exc))
    if settings["logo"]:
        image(settings["logo"], width=180)
    st.subheader("Backup local")
    st.write("O arquivo ZIP reúne uma cópia consistente do SQLite e todas as fotos. Faça backup regularmente e antes de atualizar o aplicativo.")
    if st.button("Preparar backup"):
        st.download_button("↓ Baixar backup completo", store.backup(), f"confeitaria-backup-{date.today()}.zip", mime="application/zip")
    st.caption(f"Banco: {store.db_path} · Fotos: {store.media_dir}")
    st.caption("Para restaurar: feche o aplicativo, preserve a pasta atual e extraia dados/ e midia/ do backup na pasta do projeto. Instruções completas no README.")


with st.sidebar:
    st.markdown("## 🧁 Doce Ateliê")
    st.caption(store.settings()["name"])
    page = st.radio("Navegação", ["Visão geral", "Catálogo", "Insumos e estoque", "Clientes", "Novo orçamento", "Orçamentos e pagamentos", "Agenda de produção", "Configurações"], key="page")
    st.divider()
    st.caption("LOCAL POR NATUREZA\n\nSQLite + fotos no seu computador. Sem serviços externos obrigatórios.")
if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))

# Sincronizar o calendário antes de instanciar o seletor de dia.
if page == "Agenda de produção" and st.session_state.get("agenda_day") != st.session_state.get("agenda_last_day"):
    if "agenda_day" in st.session_state:
        st.session_state["agenda_selected_date"] = st.session_state["agenda_day"]
        st.session_state["agenda_last_day"] = st.session_state["agenda_day"]

{"Visão geral": dashboard, "Catálogo": catalog, "Insumos e estoque": inventory, "Clientes": customers,
 "Novo orçamento": quote_editor, "Orçamentos e pagamentos": quotes_page, "Agenda de produção": agenda, "Configurações": settings_page}[page]()
