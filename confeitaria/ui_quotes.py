"""Orçamento guiado: cliente, produtos, pagamento e revisão."""
from copy import deepcopy
from datetime import date, datetime, time, timedelta
import hashlib

import streamlit as st

from .domain import (BRIGADEIRO_TYPES, BRIGADEIRO_FLAVORS, CATEGORIES, EXTRAS, PAYMENT_METHODS, SIMPLE_FILLINGS,
                     SPECIAL_FILLINGS, active_price, brl, cents, customer_address, filling_limit, make_line, quantity_text, totals)
from .presentation import date_field, detail, empty_state, heading, media_thumbnail, profile_heading, quote_summary, stepper
from .ui_customers import customer_form


def _money(label, amount, key):
    st.session_state.setdefault(key, amount / 100)
    return cents(st.number_input(label, min_value=0.0, step=1.0, format="%.2f", key=key))


def _seed(key, value):
    st.session_state.setdefault(key, value)
    return key


def _capture_step(draft, key):
    state = st.session_state
    step = draft.get("_step", 0)
    if step == 0:
        customer_id = state.get(key("client"))
        try:
            day = datetime.strptime(state.get(key("date") + "_text", ""), "%d/%m/%Y").date()
            event = datetime.combine(day, state.get(key("time"), time(14))).isoformat(timespec="minutes")
        except ValueError:
            event = ""
        draft.update({"customer_id": customer_id, "event_at": event,
                      "fulfillment": "Entrega" if state.get(key("fulfillment")) == "Entrega" else "Retirada"})
        if draft["fulfillment"] == "Entrega":
            draft["delivery_address"] = state.get(key(f"address_{customer_id}"), draft.get("delivery_address", ""))
    elif step == 2:
        method = state.get(key("method"), "PIX")
        pix = bool(state.get(key("pix"))) and method != "Cartão"
        draft.update({"payment_method": method, "pix_enabled": pix, "pix_percent": str(state.get(key("percent"), 0) if pix else 0),
                      "discount_cents": cents(state.get(key("discount"), 0)), "delivery_cents": cents(state.get(key("delivery"), 0)),
                      "notes": state.get(key("notes"), ""), "production_notes": state.get(key("production"), "")})


def _go_step(store, draft, target, key):
    _capture_step(draft, key)
    try:
        if target > draft.get("_step", 0):
            _validate_customer(draft, store)
            if target >= 2 and not draft["lines"]:
                raise ValueError("Adicione pelo menos um produto ao pedido.")
            if draft.get("_line_edit") is not None:
                raise ValueError("Salve ou cancele a edição do item antes de continuar.")
            if target == 3 and _totals(draft)["total_cents"] <= 0:
                raise ValueError("O orçamento precisa ter valor total maior que zero.")
        draft["_step"] = target
    except ValueError as exc:
        draft["_error"] = str(exc)


def _totals(draft):
    return totals(draft["lines"], draft.get("discount_cents", 0), draft.get("delivery_cents", 0),
                  draft.get("pix_enabled", False), draft.get("pix_percent", "0"), draft.get("payment_method", "PIX"))


def _move(draft, step):
    draft["_step"] = step
    st.rerun()


def _validate_customer(draft, store):
    client = store.get_customer(draft.get("customer_id"))
    if not client or not client["active"]:
        raise ValueError("Escolha um cliente ou cadastre um novo para continuar.")
    if not draft.get("event_at"):
        raise ValueError("Informe a data no formato DD/MM/AAAA.")
    if datetime.fromisoformat(draft["event_at"]).date() < date.today():
        raise ValueError("Escolha uma data de hoje em diante.")
    if draft.get("fulfillment") == "Entrega" and not draft.get("delivery_address", "").strip():
        raise ValueError("Preencha o endereço de entrega para continuar.")


def _new_client_dialog(store, draft):
    def dismissed():
        draft.pop("_new_client_open", None)
    @st.dialog("Novo cliente", width="large", on_dismiss=dismissed)
    def dialog():
        if not draft.get("_new_client_open"):
            st.rerun(scope="app")
        st.caption("Cadastre o cliente sem sair do orçamento.")
        def saved(customer_id):
            draft["customer_id"] = customer_id
            draft.pop("_new_client_open", None)
            st.session_state["draft_version"] = st.session_state.get("draft_version", 0) + 1
            st.session_state["notice"] = "Cliente cadastrado e selecionado no orçamento."
        customer_form(store, prefix="quote_new_customer_", on_saved=saved)
        if st.button("Cancelar cadastro", key="quote_cancel_customer"):
            draft.pop("_new_client_open", None)
            st.rerun(scope="app")
    dialog()


def _client_step(store, draft, key):
    with st.container(border=True, key="card_quote_0"):
        st.subheader("Para quem é esta encomenda?")
        clients = [c for c in store.list("customers") if c["active"]]
        ids = [c["id"] for c in clients]
        selected = draft.get("customer_id")
        a, b = st.columns([3, 1], vertical_alignment="bottom")
        customer_id = a.selectbox("Cliente", ids, index=None,
                                  format_func=lambda cid: next(f"{c['name']} · {c['phone']}" for c in clients if c["id"] == cid),
                                  placeholder="Busque pelo nome ou telefone", key=_seed(key("client"), selected if selected in ids else None))
        add_client = b.button("Novo cliente", icon=":material/person_add:", key=key("new_client"), width="stretch")
        customer = next((c for c in clients if c["id"] == customer_id), None)
        draft["customer_id"] = customer_id
        if customer:
            profile_heading(customer, store, customer_address(customer) or "Endereço ainda não informado")
        elif not clients:
            st.info("Cadastre o primeiro cliente pelo botão Novo cliente, acima.")
        st.divider()
        st.subheader("Quando e como será a entrega?")
        initial = datetime.fromisoformat(draft["event_at"]) if draft.get("event_at") else datetime.combine(date.today() + timedelta(days=7), time(14))
        a, b = st.columns([2, 1])
        with a:
            day = date_field("Data da encomenda", initial.date(), key("date"))
        hour = b.time_input("Horário de saída", time(14), key=_seed(key("time"), initial.time()))
        fulfillment = st.radio("Como o cliente vai receber?", ["Retirada na loja", "Entrega"], horizontal=True, key=_seed(key("fulfillment"), "Entrega" if draft.get("fulfillment") == "Entrega" else "Retirada na loja"))
        draft["event_at"] = datetime.combine(day, hour).isoformat(timespec="minutes") if day else ""
        draft["fulfillment"] = "Entrega" if fulfillment == "Entrega" else "Retirada"
        if draft.get("_address_customer") != customer_id:
            draft["delivery_address"] = customer_address(customer) if customer else ""
            draft["_address_customer"] = customer_id
        if fulfillment == "Entrega":
            address = st.text_area("Endereço de entrega", placeholder="Rua, número, bairro, cidade e CEP", key=_seed(key(f"address_{customer_id}"), draft.get("delivery_address", "")), height=90)
            draft["delivery_address"] = address
            if customer and customer.get("address_reference"):
                st.caption("Referência: " + customer["address_reference"])
        else:
            st.caption("O cliente retira a encomenda na confeitaria.")
        if add_client:
            draft["_new_client_open"] = True
        if draft.get("_new_client_open"):
            _new_client_dialog(store, draft)
    st.button("Continuar para produtos", type="primary", icon=":material/arrow_forward:", key=key("next_1"), width="stretch", on_click=_go_step, args=(store, draft, 1, key))


def _edit_line(draft, index):
    line = deepcopy(draft["lines"][index])
    line["category"] = line.get("category", CATEGORIES[0])
    draft["_builder"] = line
    draft["_line_edit"] = index
    draft["_builder_version"] = draft.get("_builder_version", 0) + 1


def _remove_line(draft, index):
    draft["lines"].pop(index)
    if draft.get("_line_edit") is not None:
        draft.pop("_line_edit", None)
        draft.pop("_builder", None)
        draft["_builder_version"] = draft.get("_builder_version", 0) + 1


def _reference_upload(store, target, key, label="Imagem de inspiração deste item"):
    upload = st.file_uploader(label, ["jpg", "jpeg", "png", "webp"], key=key)
    if upload:
        signature = hashlib.sha256(upload.getvalue()).hexdigest()
        if signature != target.get("_reference_hash"):
            try:
                target["reference_photo"] = store.save_image(upload)
                target["_reference_hash"] = signature
            except ValueError as exc:
                st.error(str(exc))
    if target.get("reference_photo"):
        media_thumbnail(target["reference_photo"], store, 130, "Modelo de inspiração")
        if st.checkbox("Desconsiderar esta imagem", key=key + "_remove"):
            target["reference_photo"] = ""
    return target.get("reference_photo", "")


def _cart(draft, key, editable=False, store=None):
    if not draft["lines"]:
        empty_state("Seu orçamento está começando", "Escolha um produto, personalize e adicione ao pedido.", "▤")
        return
    st.subheader(f"Itens do pedido · {len(draft['lines'])}")
    for i, line in enumerate(draft["lines"]):
        with st.container(border=True, key=f"card_quote_line_{i}"):
            a, b = st.columns([3, 1])
            a.markdown(f"**{line['name']}**" + (" · [BRINDE]" if line["gift"] else ""))
            a.caption(f"{quantity_text(line['quantity'])} {line['unit']} · " + " / ".join(line.get("fillings", []) + line.get("flavors", [])))
            b.markdown(f"**{brl(line['total_cents'])}**")
            for extra in line["extras"]:
                st.caption(f"＋ {extra.get('quantity', 1)} × {extra['name']} · " + ("[BRINDE]" if extra["gift"] or line["gift"] else brl(extra["amount_cents"])))
                if extra.get("flavors"):
                    st.caption(extra.get("brigadeiro_type", "") + " · " + " / ".join(extra["flavors"]) + " · " + extra.get("personalization", ""))
            if line.get("composition"):
                st.caption("Inclui: " + "; ".join(line["composition"]))
            if line.get("negotiation", {}).get("notes"):
                st.caption("Exceção autorizada: " + line["negotiation"]["notes"])
            if store and line.get("reference_photo"):
                media_thumbnail(line["reference_photo"], store, 120, "Referência do item")
            if line["details"]:
                st.caption(line["details"])
            if editable:
                a, b = st.columns(2)
                a.button("Editar item", icon=":material/edit:", key=key(f"edit_{i}"), on_click=_edit_line, args=(draft, i), width="stretch")
                b.button("Remover item", icon=":material/delete:", key=key(f"remove_{i}"), on_click=_remove_line, args=(draft, i), width="stretch")


def _products_step(store, draft, key):
    products = [p for p in store.list("products") if p["active"]]
    builder = draft.setdefault("_builder", {})
    version = draft.get("_builder_version", 0)
    bkey = lambda name: key(f"builder_{version}_{name}")
    with st.container(border=True, key="card_quote_1"):
        st.subheader("O que vamos preparar?")
        categories = [category for category in CATEGORIES if any(p["category"] == category for p in products)]
        if not categories:
            st.info("Cadastre ou ative um produto no catálogo para continuar.")
            return
        category_key = bkey("category")
        if category_key not in st.session_state:
            st.session_state[category_key] = builder.get("category") if builder.get("category") in categories else categories[0]
        category = st.radio("Categoria", categories, horizontal=True, key=category_key)
        filtered = [p for p in products if p["category"] == category]
        ids = [p["id"] for p in filtered]
        product_id = st.selectbox("Produto", ids, format_func=lambda pid: next(p["name"] for p in filtered if p["id"] == pid),
                                  key=_seed(bkey("product_" + category), builder.get("product_id") if builder.get("product_id") in ids else ids[0]))
        product = next(p for p in filtered if p["id"] == product_id)
        if builder.get("product_id") != product_id:
            builder = {"product_id": product_id, "category": category}
            draft["_builder"] = builder
        pkey = lambda name: bkey(f"{product_id}_{name}")
        price, promotional = active_price(product)
        st.markdown(f"**{brl(price)} / {product['unit']}**" + (" · Promoção vigente" if promotional else ""))
        if product.get("photos"):
            photo, description = st.columns([1, 3])
            with photo:
                media_thumbnail(product["photos"][0], store, 120)
            description.write(product["description"])
        else:
            st.write(product["description"])
        if product.get("composition"):
            st.markdown("**Este kit inclui**")
            for component in product["composition"]:
                st.write("• " + component)
        is_cake = category in CATEGORIES[:2]
        minimum = 1.0
        initial_quantity = 2.0 if is_cake else 1.0
        label = "Peso do bolo (kg)" if is_cake else "Quantidade de centos" if product["unit"] == "cento" else "Quantidade de unidades"
        quantity = st.number_input(label, min_value=minimum, max_value=100000.0, step=.5 if is_cake else 1.0, format="%.2f" if is_cake else "%.0f", key=_seed(pkey("qty"), max(minimum, float(builder.get("quantity", initial_quantity)))))
        fillings, extras, flavors = [], [], []
        brigadeiro_type, split = None, False
        allow_exception, negotiation_notes = False, ""
        if is_cake:
            st.markdown(f"**Escolha até {filling_limit(quantity)} recheio(s)**")
            st.caption("Mínimo padrão de 2 kg. Abaixo de 2 kg: um recheio. A partir de 2 kg: até dois recheios.")
            choices = SIMPLE_FILLINGS if category == CATEGORIES[0] else SPECIAL_FILLINGS
            columns = st.columns(2)
            for i, filling in enumerate(choices):
                if columns[i % 2].checkbox(filling, key=_seed(pkey(filling), filling in builder.get("fillings", []))):
                    fillings.append(filling)
            if quantity < 2 or len(fillings) > filling_limit(quantity):
                st.warning("Este bolo foge do padrão de peso ou quantidade de recheios. Só continue se a confeiteira tiver combinado a exceção com o cliente.")
                allow_exception = st.checkbox("Confirmar exceção combinada com a confeiteira", key=_seed(pkey("exception"), bool(builder.get("negotiation", {}).get("notes"))))
                negotiation_notes = st.text_input("Motivo / condição da exceção", key=_seed(pkey("negotiation"), builder.get("negotiation", {}).get("notes", "")), placeholder="Registre o que foi combinado com o cliente")
            with st.expander("Decoração e adicionais", expanded=bool(builder.get("extras"))):
                old = {e["name"]: e for e in builder.get("extras", [])}
                selected_extras = st.multiselect("Adicionar ao bolo", EXTRAS, placeholder="Escolha os adicionais", key=_seed(pkey("extras"), list(old)))
                for name in selected_extras:
                    st.markdown(f"**{name}**")
                    previous = old.get(name, {})
                    a, b, c = st.columns([1, 1.5, 1], vertical_alignment="bottom")
                    units = a.number_input("Quantidade do adicional", min_value=1, max_value=100000, step=1, key=_seed(pkey(name + "units"), int(previous.get("quantity", 1))))
                    with b:
                        amount = _money("Valor unitário (R$)", previous.get("unit_cents", previous.get("amount_cents", 0)), pkey(name + "amount"))
                    free = c.checkbox("É cortesia", key=_seed(pkey(name + "gift"), previous.get("gift", False)))
                    extra = {"name": name, "quantity": units, "unit_cents": amount, "amount_cents": units * amount, "gift": free}
                    st.caption("[BRINDE]" if free else f"{units} unidade(s) × {brl(amount)} = {brl(units * amount)}")
                    if name == "Brigadeiros no Topo":
                        kind = st.selectbox("Tipo dos brigadeiros adicionais", BRIGADEIRO_TYPES, key=_seed(pkey(name+"type"), previous.get("brigadeiro_type", "Tradicional")))
                        chosen = st.multiselect("Sabores dos brigadeiros adicionais", BRIGADEIRO_FLAVORS[kind], key=_seed(pkey(name+kind+"flavors"), [f for f in previous.get("flavors", []) if f in BRIGADEIRO_FLAVORS[kind]]), placeholder="Escolha os sabores")
                        extra.update(brigadeiro_type=kind, flavors=chosen)
                        if kind == "Personalizado":
                            extra["personalization"] = st.text_input("Personalização dos brigadeiros adicionais", key=_seed(pkey(name+"personalization"), previous.get("personalization", "")))
                    if "Topo de Bolo" in name:
                        extra["reference_photo"] = _reference_upload(store, previous, pkey(name+"reference"), "Imagem de inspiração do topo")
                        extra["_reference_hash"] = previous.get("_reference_hash", "")
                    extras.append(extra)
                if selected_extras:
                    st.caption("Cada adicional usa quantidade × valor unitário, independentemente do peso do bolo.")
        if category == CATEGORIES[2]:
            default_type = "Personalizado" if "Personalizados" in product["name"] else "Especial" if "Especiais" in product["name"] else "Tradicional"
            brigadeiro_type = st.selectbox("Tipo de brigadeiro", BRIGADEIRO_TYPES, key=_seed(pkey("type"), builder.get("brigadeiro_type") or default_type))
            split = st.checkbox("Dividir cento em 50/50", key=_seed(pkey("split"), builder.get("split", False)))
            options = BRIGADEIRO_FLAVORS[brigadeiro_type]
            old_flavors = builder.get("flavors", [])
            initial = old_flavors[0] if old_flavors and old_flavors[0] in options else options[0]
            flavors = [st.selectbox("Sabor 1", options, key=_seed(pkey(brigadeiro_type+"flavor_1"), initial))]
            if split:
                initial = old_flavors[1] if len(old_flavors)>1 and old_flavors[1] in options else options[1]
                flavors.append(st.selectbox("Sabor 2", options, key=_seed(pkey(brigadeiro_type+"flavor_2"), initial)))
                st.caption("50 unidades de cada sabor por cento.")
            if brigadeiro_type == "Personalizado":
                st.info("Preencha o tema, as cores e a decoração em Detalhes deste item. Você também pode anexar uma inspiração.")
        with st.expander("Personalização e cortesia", expanded=bool(builder.get("details") or builder.get("gift"))):
            details = st.text_area("Detalhes deste item", placeholder="Tema, tamanho, cores e personalização…", key=_seed(pkey("details"), builder.get("details", "")))
            gift = st.checkbox("Este item é um brinde / cortesia", key=_seed(pkey("gift"), builder.get("gift", False)))
        reference = _reference_upload(store, builder, pkey("reference"))
        builder.update({"product_id": product_id, "category": category, "quantity": str(quantity), "fillings": fillings, "extras": extras,
                        "details": details, "gift": gift, "brigadeiro_type": brigadeiro_type, "split": split, "flavors": flavors})
        editing = draft.get("_line_edit")
        if st.button("Salvar alterações do item" if editing is not None else "Adicionar ao pedido", type="primary", icon=":material/add:", width="stretch", key=key("add")):
            try:
                line = make_line(product, quantity, fillings, extras, details, gift, brigadeiro_type, split, flavors,
                                 allow_extra_fillings=allow_exception, allow_under_minimum=allow_exception, negotiation_notes=negotiation_notes, reference_photo=reference)
                if editing is None:
                    draft["lines"].append(line)
                else:
                    draft["lines"][editing] = line
                    draft.pop("_line_edit", None)
                st.toast("Item atualizado." if editing is not None else "Produto adicionado ao pedido.")
            except ValueError as exc:
                st.error(str(exc))
        if editing is not None and st.button("Cancelar edição do item", key=key("cancel_edit")):
            draft.pop("_line_edit", None)
            draft.pop("_builder", None)
            draft["_builder_version"] = version + 1
            st.rerun()
    _cart(draft, key, editable=True, store=store)
    a, b = st.columns(2)
    a.button("Voltar", icon=":material/arrow_back:", key=key("back_2"), width="stretch", on_click=_go_step, args=(store, draft, 0, key))
    b.button("Continuar para pagamento", type="primary", key=key("next_2"), disabled=not draft["lines"], width="stretch", on_click=_go_step, args=(store, draft, 2, key))


def _payment_step(store, draft, key):
    with st.container(border=True, key="card_quote_2"):
        st.subheader("Como será o pagamento?")
        method = st.radio("Forma de pagamento", PAYMENT_METHODS, horizontal=True, key=_seed(key("method"), draft.get("payment_method", "PIX")))
        pix = st.checkbox("Conceder desconto PIX / Dinheiro", disabled=method == "Cartão", key=_seed(key("pix"), draft.get("pix_enabled", False)))
        pix = pix and method != "Cartão"
        percent = st.number_input("Desconto PIX / Dinheiro (%)", min_value=0.0, max_value=100.0, step=.5, key=_seed(key("percent"), float(draft.get("pix_percent", 0)))) if pix else 0.0
        if any(line["promotional"] for line in draft["lines"]) and pix:
            st.warning("Há produtos em promoção. Este desconto será acumulado porque você o ativou.")
        a, b = st.columns(2)
        with a: discount = _money("Desconto geral (R$)", draft.get("discount_cents", 0), key("discount"))
        with b: delivery = _money("Entrega / frete (R$)", draft.get("delivery_cents", 0), key("delivery"))
        st.caption("Desconto percentual aplicado aos produtos, após o desconto geral. O frete mantém o valor informado.")
        draft.update({"payment_method": method, "pix_enabled": pix, "pix_percent": str(percent), "discount_cents": discount, "delivery_cents": delivery})
    with st.container(border=True, key="card_quote_3"):
        st.subheader("Os detalhes fazem a diferença")
        draft["notes"] = st.text_area("Observações para o cliente", placeholder="Condições combinadas e orientações para o cliente.", key=_seed(key("notes"), draft.get("notes", "")))
        draft["production_notes"] = st.text_area("Orientações para a cozinha", placeholder="Decoração, alergias, restrições e cuidados de transporte.", key=_seed(key("production"), draft.get("production_notes", "")))
        reference = st.file_uploader("Foto de referência do pedido", ["jpg", "jpeg", "png", "webp"], key=key("reference"))
        if reference:
            signature = hashlib.sha256(reference.getvalue()).hexdigest()
            if signature != draft.get("_reference_hash"):
                try:
                    draft["reference_photo"] = store.save_image(reference)
                    draft["_reference_hash"] = signature
                except ValueError as exc:
                    st.error(str(exc))
        if draft.get("reference_photo") and store.image_path(draft["reference_photo"]):
            st.image(str(store.image_path(draft["reference_photo"])), width=140)
            if st.button("Remover foto de referência", key=key("remove_reference")):
                draft["reference_photo"] = ""
                st.rerun()
    a, b = st.columns(2)
    a.button("Voltar", icon=":material/arrow_back:", key=key("back_3"), width="stretch", on_click=_go_step, args=(store, draft, 1, key))
    b.button("Revisar orçamento", type="primary", key=key("next_3"), width="stretch", on_click=_go_step, args=(store, draft, 3, key))


def _review_step(store, draft, key):
    customer = store.get_customer(draft.get("customer_id"))
    with st.container(border=True, key="card_quote_4"):
        st.subheader("Confira antes de salvar")
        if customer:
            profile_heading(customer, store)
        a, b = st.columns(2)
        with a:
            detail("Data e horário", datetime.fromisoformat(draft["event_at"]).strftime("%d/%m/%Y · %H:%M") if draft.get("event_at") else "Data inválida")
            detail("Recebimento", draft.get("fulfillment"))
        with b:
            detail("Pagamento", draft.get("payment_method", "PIX"))
            detail("Endereço", draft.get("delivery_address") if draft.get("fulfillment") == "Entrega" else "Retirada na loja")
        st.button("Alterar cliente ou entrega", key=key("edit_client"), on_click=_go_step, args=(store, draft, 0, key))
    _cart(draft, key, store=store)
    with st.container(border=True, key="card_quote_5"):
        detail("Observações para o cliente", draft.get("notes"))
        detail("Orientações para a cozinha", draft.get("production_notes"))
        if draft.get("reference_photo") and store.image_path(draft["reference_photo"]):
            st.image(str(store.image_path(draft["reference_photo"])), width=160)
        st.caption("Validade de 7 dias. A data só é reservada após o recebimento do sinal mínimo de 50%.")
    with st.expander("Logo da loja no orçamento", expanded=not store.settings().get("logo")):
        logo_target = {"reference_photo": draft.get("logo_override") or draft.get("shop", {}).get("logo") or store.settings().get("logo", ""), "_reference_hash": draft.get("_logo_hash", "")}
        draft["logo_override"] = _reference_upload(store, logo_target, key("logo"), "Adicionar / trocar logo deste orçamento")
        draft["_logo_hash"] = logo_target.get("_reference_hash", "")
        st.caption("A identidade padrão da loja pode ser cadastrada em Configurações.")
    a, b = st.columns([1, 2])
    a.button("Voltar", icon=":material/arrow_back:", key=key("back_4"), width="stretch", on_click=_go_step, args=(store, draft, 2, key))
    if b.button("Salvar orçamento", type="primary", icon=":material/check:", key=key("save"), width="stretch"):
        try:
            _validate_customer(draft, store)
            payload = {field: draft.get(field, "") for field in ("customer_id", "event_at", "fulfillment", "delivery_address", "payment_method", "pix_enabled", "pix_percent", "discount_cents", "delivery_cents", "notes", "production_notes", "reference_photo")}
            if payload["fulfillment"] == "Retirada":
                payload["delivery_address"] = ""
            payload["lines"] = deepcopy(draft["lines"])
            payload["logo_override"] = draft.get("logo_override", "")
            quote_id = store.save_quote(payload, draft.get("id") or draft.get("quote_id"))
            st.session_state["draft"] = {"lines": []}
            st.session_state["draft_version"] = st.session_state.get("draft_version", 0) + 1
            st.session_state.pop("selected_quote", None)
            st.session_state["notice"] = f"Orçamento #{quote_id:04d} salvo. Agora você pode enviar o PDF ou registrar o sinal."
            st.session_state["_navigate"] = "Orçamentos e pagamentos"
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def quote_editor_page(store):
    draft = st.session_state.setdefault("draft", {"lines": []})
    draft.setdefault("payment_method", "PIX")
    draft.setdefault("pix_enabled", False)
    draft.setdefault("pix_percent", "0")
    draft.setdefault("discount_cents", 0)
    draft.setdefault("delivery_cents", 0)
    step = draft.setdefault("_step", 0)
    version = st.session_state.get("draft_version", 0)
    key = lambda name: f"draft_{version}_{name}"
    editing = draft.get("id") or draft.get("quote_id")
    heading("ATENDIMENTO / ORÇAMENTOS", f"Editar orçamento #{editing:04d}" if editing else "Novo orçamento", "Uma encomenda bem feita começa com um pedido bem organizado.")
    stepper(step)
    if draft.get("_error"):
        st.error(draft.pop("_error"))
    left, right = st.columns([2.3, 1], gap="large")
    with left:
        slot = st.empty()
        with slot.container():
            [_client_step, _products_step, _payment_step, _review_step][step](store, draft, key)
    with right:
        try:
            quote_summary(draft, _totals(draft))
        except ValueError as exc:
            st.error(str(exc))
        if draft.get("event_at"):
            with st.container(border=True, key="card_quote_6"):
                detail("Data da encomenda", datetime.fromisoformat(draft["event_at"]).strftime("%d/%m/%Y · %H:%M"))
                detail("Recebimento", draft.get("fulfillment"))
