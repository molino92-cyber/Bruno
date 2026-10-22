"""Aplicativo local: execute com `streamlit run app.py`."""
import calendar
from copy import deepcopy
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from html import escape

import streamlit as st

from confeitaria.domain import (BRIGADEIRO_TYPES, CATEGORIES, EXTRAS, PAYMENT_METHODS, SIMPLE_FILLINGS,
                                SPECIAL_FILLINGS, UNITS, active_price, brl, cents, make_line, quantity_text, totals)
from confeitaria.pdf import formatted_date, generate_pdf
from confeitaria.storage import Store, inventory_cost
from confeitaria.presentation import apply_theme, brand_html, date_field, heading, table, media_thumbnail
from confeitaria.ui_customers import change_customer_view, customers_page
from confeitaria.ui_quotes import quote_editor_page

@st.cache_resource
def get_store(demo=False):
    real = Store()
    if demo:
        from confeitaria.demo import demonstration_store
        return demonstration_store(real)
    return real


store = get_store(st.session_state.get("demo_mode", False))
shop = store.settings()
shop_logo = store.image_path(shop["logo"])
st.set_page_config(page_title=f'{shop["name"]} · Gestão', page_icon=str(shop_logo) if shop_logo else "🧁", layout="wide")
apply_theme()


def hero(label, title, subtitle):
    heading(label, title, subtitle)

def image(name, width=None):
    media_thumbnail(name, store, height=110 if width else 170)


def money(label, value=0, key=None, **kwargs):
    return cents(st.number_input(label, min_value=0.0, value=float(value) / 100, step=1.0, format="%.2f", key=key, **kwargs))


def flash(message):
    st.session_state["notice"] = message
    st.rerun()


def go(page):
    st.session_state["page"] = page


def fresh_draft(quote=None):
    st.session_state["draft"] = deepcopy(quote or {"lines": []})
    st.session_state["draft_version"] = st.session_state.get("draft_version", 0) + 1
    st.session_state["page"] = "Novo orçamento"


def quote_rows(quotes):
    return [{"Pedido": f"#{q['id']:04d}", "Cliente": q["customer"]["name"], "Saída": formatted_date(q["event_at"]),
             "Status": q["status"], "Total": brl(q["totals"]["total_cents"]), "Recebido": brl(q["paid_cents"]), "Saldo": brl(q["balance_cents"])} for q in quotes]


def dashboard():
    hero("PAINEL DA CONFEITARIA", "Sua confeitaria em dia", "Acompanhe as encomendas, a produção e os recebimentos de um só lugar.")
    quotes = store.quotes()
    approved = [q for q in quotes if "Data Reservada" in q["status"]]
    today = [q for q in approved if q["event_at"][:10] == date.today().isoformat()]
    with st.container(key="metrics_dashboard"):
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
            table(quote_rows(upcoming))
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
    hero("PRODUTOS", "Catálogo da confeitaria", "Seus sabores, suas criações e as ofertas da vez.")
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
            with columns[i % 3], st.container(border=True, key=f"card_catalog_{product['id']}"):
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
            composition = st.text_area("Composição do kit / itens inclusos · um por linha", "\n".join(p.get("composition", [])), help="Exemplo: 1 bolo simples de 2 kg, 10 brigadeiros e 5 cupcakes, cada item em uma linha.")
            a, b = st.columns(2)
            price = money("Preço normal (R$ por kg / cento / unidade)", p.get("price_cents", 0), key=f"price_{selected}")
            active = st.checkbox("Visível no catálogo", value=bool(p.get("active", 1)))
            st.caption("A unidade é definida pela categoria. Bolos em kg; brigadeiros em cento; demais em unidades.")
            st.markdown("**Promoção do dia / mês**")
            enabled = st.checkbox("Ativar promoção no intervalo abaixo", value=bool(p.get("promo_enabled", 0)))
            promo = money("Preço promocional (R$)", p.get("promo_cents", 0), key=f"promo_{selected}")
            a, b = st.columns(2)
            with a:
                start = date_field("Início da promoção", date.fromisoformat(p["promo_start"]) if p.get("promo_start") else date.today(), f"promo_start_{selected}", picker=False)
            with b:
                end = date_field("Fim da promoção", date.fromisoformat(p["promo_end"]) if p.get("promo_end") else date.today(), f"promo_end_{selected}", picker=False)
            old_photos = p.get("photos", [])
            kept = st.multiselect("Fotos atuais a manter", old_photos, default=old_photos, placeholder="Selecione as fotos", format_func=lambda x: f"Foto {old_photos.index(x) + 1}")
            uploads = st.file_uploader("Adicionar fotos · até 3 no total · 10 MB cada", ["jpg", "jpeg", "png", "webp"], accept_multiple_files=True)
            if st.form_submit_button("Salvar produto", type="primary"):
                try:
                    if start is None or end is None:
                        raise ValueError("Informe as datas no formato DD/MM/AAAA.")
                    if len(kept) + len(uploads) > 3:
                        raise ValueError("Mantenha no máximo três fotos no total.")
                    photos = kept + [store.save_image(upload) for upload in uploads]
                    store.save_product({"name": name.strip(), "category": category, "description": description.strip(), "unit": "un",
                                        "price_cents": price, "active": int(active), "promo_enabled": int(enabled), "promo_cents": promo,
                                        "promo_start": start.isoformat(), "promo_end": end.isoformat(), "photos": photos,
                                        "composition": [item.strip() for item in composition.splitlines() if item.strip()]}, selected)
                    flash("Produto salvo. Orçamentos anteriores mantêm os preços registrados.")
                except ValueError as exc:
                    st.error(str(exc))


def inventory():
    hero("PRODUÇÃO", "Estoque e insumos", "Controle embalagens, ingredientes e custos com uma visão do que está disponível.")
    items = store.list("inventory")
    stock_tab, edit_tab = st.tabs(["Estoque visual", "Cadastrar / atualizar"])
    with stock_tab:
        search = st.text_input("Buscar insumo ou marca")
        filtered = [i for i in items if search.casefold() in (i["name"] + " " + i["brand"]).casefold()]
        st.metric("Valor estimado em estoque", brl(cents(sum(Decimal(i["stock"]) * i["paid_cents"] / 100 for i in items))))
        columns = st.columns(3)
        for n, item in enumerate(filtered):
            with columns[n % 3], st.container(border=True, key=f"card_inventory_{item['id']}"):
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
    customers_page(store)


def quote_editor():
    quote_editor_page(store)

def quotes_page():
    hero("ATENDIMENTO", "Pedidos e pagamentos", "Do orçamento aprovado à entrega, acompanhe cada encomenda.")
    quotes = store.quotes()
    selected = st.session_state.get("selected_quote")
    if not quotes:
        st.info("Nenhum orçamento salvo ainda.")
        st.button("Criar primeiro orçamento", on_click=fresh_draft)
        return
    if selected is None:
        st.button("Novo orçamento", type="primary", on_click=fresh_draft)
        group = st.radio("Situação dos pedidos", ["Todos", "Abertos", "Fechados"], horizontal=True)
        st.caption("Abertos: pedidos ainda não entregues, incluindo vencidos. Fechados: entrega / retirada concluída.")
        a, b = st.columns(2)
        search = a.text_input("Buscar cliente ou número do orçamento")
        status_filter = b.selectbox("Filtrar status", ["Todos", "Em Aberto", "Vencido", "Aprovado / Data Reservada", "Quitado / Data Reservada", "Entregue"])
        filtered = [q for q in quotes if (group == "Todos" or bool(q["delivered"]) == (group == "Fechados")) and (status_filter == "Todos" or q["status"] == status_filter) and (search.casefold() in q["customer"]["name"].casefold() or search.lstrip("#").isdigit() and int(search.lstrip("#")) == q["id"])]
        st.caption(f"{len(filtered)} pedido(s) encontrado(s) · Clique em Ver pedido para abrir os detalhes.")
        for q in filtered:
            with st.container(key=f"order_row_{q['id']}"):
                a, b, c, d = st.columns([2.4, 1.6, 1.8, 1], vertical_alignment="center")
                a.markdown(f"**#{q['id']:04d} · {q['customer']['name']}**")
                a.caption(formatted_date(q["event_at"]))
                b.write(q["status"])
                c.markdown(f"**{brl(q['totals']['total_cents'])}**")
                c.caption("Saldo: " + brl(q["balance_cents"]))
                def open_order(identifier=q["id"]):
                    st.session_state["selected_quote"] = identifier
                d.button("Ver pedido", key=f"open_order_{q['id']}", on_click=open_order, width="stretch")
        if not filtered:
            st.info("Nenhum orçamento com este filtro.")
        return
    q = next((q for q in quotes if q["id"] == selected), None)
    def close_order():
        st.session_state.pop("selected_quote", None)
    st.button("Voltar para pedidos", icon=":material/arrow_back:", on_click=close_order)
    if not q:
        st.info("Pedido não encontrado.")
        return
    st.subheader(f"#{q['id']:04d} · {q['customer']['name']}")
    st.info(q["status"] + f" · Validade: {date.fromisoformat(q['valid_until']):%d/%m/%Y}")
    with st.container(key="metrics_order"):
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
                    st.write(f"＋ {extra.get('quantity', 1)} × {extra['name']} · " + ("[BRINDE]" if extra["gift"] or line["gift"] else brl(extra["amount_cents"])))
                    if extra.get("flavors"):
                        st.caption(extra.get("brigadeiro_type", "") + " · " + " / ".join(extra["flavors"]) + " · " + extra.get("personalization", ""))
                    if extra.get("reference_photo"):
                        media_thumbnail(extra["reference_photo"], store, 120, "Inspiração do adicional")
                if line.get("composition"):
                    st.write("Inclui: " + "; ".join(line["composition"]))
                if line.get("negotiation", {}).get("notes"):
                    st.warning("Exceção autorizada: " + line["negotiation"]["notes"])
                if line.get("reference_photo"):
                    media_thumbnail(line["reference_photo"], store, 140, "Inspiração do item")
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
            table([{"Recebido em": formatted_date(p["received_at"]), "Valor": brl(p["amount_cents"]), "Forma": p["method"], "Descrição": p["note"]} for p in history])
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
        with st.expander("Logo da loja neste orçamento", expanded=not q["shop"].get("logo")):
            if q["shop"].get("logo"):
                media_thumbnail(q["shop"]["logo"], store, 100, "Logo da confeitaria")
            logo = st.file_uploader("Adicionar / trocar logo para gerar o PDF", ["jpg", "jpeg", "png", "webp"], key=f"order_logo_{q['id']}")
            if st.button("Aplicar logo ao orçamento", disabled=not logo, key=f"apply_logo_{q['id']}"):
                try:
                    store.update_quote_logo(q["id"], store.save_image(logo))
                    flash("Logo atualizada neste orçamento. Os valores e recebimentos foram preservados.")
                except ValueError as exc:
                    st.error(str(exc))
        a, b = st.columns(2)
        a.download_button("↓ Orçamento do cliente", generate_pdf(q, store), file_name=f"orcamento-{q['id']:04d}.pdf", mime="application/pdf", key=f"pdf_client_{q['id']}")
        b.download_button("↓ Ficha da cozinha · sem preços", generate_pdf(q, store, kitchen=True), file_name=f"producao-{q['id']:04d}.pdf", mime="application/pdf", key=f"pdf_kitchen_{q['id']}")


def agenda():
    hero("PRODUÇÃO", "Agenda da cozinha", "Organize os pedidos confirmados por dia e horário de saída.")
    approved = [q for q in store.quotes() if "Data Reservada" in q["status"]]
    from confeitaria.presentation import MONTHS
    a, b = st.columns([2, 1])
    month_number = a.selectbox("Mês da agenda", list(range(1, 13)), index=date.today().month - 1, format_func=lambda n: MONTHS[n - 1], key="agenda_month")
    year = b.number_input("Ano da agenda", min_value=2020, max_value=2100, value=date.today().year, step=1, key="agenda_year")
    month = date(year, month_number, 1)
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
                    st.session_state["agenda_selected_date_text"] = day_date.strftime("%d/%m/%Y")
                    st.rerun()
    st.divider()
    selected = date_field("Encomendas do dia", selected, key="agenda_selected_date")
    if selected is None:
        return
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
    hero("SUA CONFEITARIA", "Configurações", "Identidade da loja, documentos e cópias de segurança.")
    settings = store.settings()
    with st.form("settings"):
        st.caption("Personalize o nome e a logo exibidos no sistema e nos próximos orçamentos. Você pode alterá-los quando precisar.")
        name = st.text_input("Nome da confeitaria *", settings["name"], max_chars=150)
        a, b = st.columns(2)
        phone = a.text_input("Telefone / WhatsApp da loja", settings["phone"])
        document = b.text_input("CNPJ / CPF da loja", settings["document"])
        address = st.text_area("Endereço da loja", settings["address"])
        days = st.number_input("Alterações aceitas até quantos dias antes do evento?", min_value=0, max_value=365, value=int(settings["change_days"]))
        logo = st.file_uploader("Logo da confeitaria · cabeçalho e PDFs", ["jpg", "jpeg", "png", "webp"])
        remove_logo = st.checkbox("Remover logo atual")
        if st.form_submit_button("Salvar configurações", type="primary"):
            try:
                logo_name = store.save_image(logo) if logo else "" if remove_logo else settings["logo"]
                store.save_settings({"name": name.strip(), "phone": phone.strip(), "document": document.strip(), "address": address.strip(), "change_days": int(days), "logo": logo_name})
                flash("Nome e logo atualizados no sistema. Serão usados também nos próximos orçamentos salvos.")
            except ValueError as exc:
                st.error(str(exc))
    st.caption("Identidade atual · a logo se ajusta ao quadro sem distorcer")
    with st.container(border=True):
        st.markdown(f'<div class="brand-preview">{brand_html(settings, store)}</div>', unsafe_allow_html=True)
    st.subheader("Cópia de segurança")
    st.write("O arquivo ZIP reúne uma cópia consistente do SQLite e todas as fotos. Faça backup regularmente e antes de atualizar o aplicativo.")
    if st.button("Preparar cópia de segurança"):
        st.download_button("Baixar cópia completa", store.backup(), f"confeitaria-backup-{date.today()}.zip", mime="application/zip")
    st.caption(f"Banco: {store.db_path} · Fotos: {store.media_dir}")
    st.caption("Para restaurar: feche o aplicativo, preserve a pasta atual e extraia dados/ e midia/ do backup na pasta do projeto. Instruções completas no README.")


if "_navigate" in st.session_state:
    st.session_state["page"] = st.session_state.pop("_navigate")


def navigation_changed():
    if st.session_state.get("page") == "Clientes":
        change_customer_view()
    if st.session_state.get("page") == "Orçamentos e pagamentos":
        st.session_state.pop("selected_quote", None)


def mobile_navigation_changed():
    st.session_state["page"] = st.session_state["mobile_page"]
    navigation_changed()


def switch_demo():
    for key in list(st.session_state):
        if key != "demo_mode":
            del st.session_state[key]


with st.sidebar:
    st.markdown(brand_html(shop, store), unsafe_allow_html=True)
    st.toggle("Ver demonstração", key="demo_mode", on_change=switch_demo, help="Exemplos com imagens em um banco separado dos seus dados.")
    st.markdown('<div class="nav-caption">SEU ESPAÇO DE TRABALHO</div>', unsafe_allow_html=True)
    page_labels = {"Visão geral": "◫  Visão geral", "Catálogo": "▦  Produtos", "Insumos e estoque": "▣  Estoque e insumos", "Clientes": "♧  Clientes", "Novo orçamento": "＋  Novo orçamento", "Orçamentos e pagamentos": "▤  Pedidos e pagamentos", "Agenda de produção": "▦  Agenda da cozinha", "Configurações": "⚙  Configurações"}
    page = st.radio("Navegação", list(page_labels), format_func=page_labels.get, key="page", label_visibility="collapsed", on_change=navigation_changed)
    st.markdown('<div class="sidebar-footer"><strong>Feito para o seu dia a dia</strong><span>Seus pedidos organizados.<br>Seus dados sempre com você.</span></div>', unsafe_allow_html=True)

with st.container(key="mobile_navigation"):
    st.session_state["mobile_page"] = page
    st.selectbox("Ir para", list(page_labels), format_func=page_labels.get, key="mobile_page", on_change=mobile_navigation_changed)

if "notice" in st.session_state:
    st.success(st.session_state.pop("notice"))

if st.session_state.get("demo_mode"):
    st.info("Modo demonstração · Clientes, imagens, pedidos e preços fictícios. Desative Ver demonstração para voltar aos seus dados.")

# Sincronizar o calendário antes de instanciar o seletor de dia.
if page == "Agenda de produção" and st.session_state.get("agenda_day") != st.session_state.get("agenda_last_day"):
    if "agenda_day" in st.session_state:
        st.session_state["agenda_selected_date"] = st.session_state["agenda_day"]
        st.session_state["agenda_last_day"] = st.session_state["agenda_day"]

{"Visão geral": dashboard, "Catálogo": catalog, "Insumos e estoque": inventory, "Clientes": customers,
 "Novo orçamento": quote_editor, "Orçamentos e pagamentos": quotes_page, "Agenda de produção": agenda, "Configurações": settings_page}[page]()
