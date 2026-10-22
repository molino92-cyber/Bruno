"""Cadastro de clientes com ações explícitas, endereço estruturado e histórico."""
from datetime import datetime
from html import escape

import streamlit as st

from .domain import STATES, brl, customer_address
from .presentation import contact_line, detail, empty_state, heading, phone_text, profile_heading, table


def change_customer_view(mode="list", customer_id=None):
    st.session_state["customer_view"] = mode
    st.session_state["customer_id"] = customer_id
    st.session_state["customer_form_version"] = st.session_state.get("customer_form_version", 0) + 1
    st.session_state.pop("customer_delete_id", None)


def start_customer_quote(customer_id):
    st.session_state["draft"] = {"lines": [], "customer_id": customer_id, "_step": 0}
    st.session_state["draft_version"] = st.session_state.get("draft_version", 0) + 1
    st.session_state["page"] = "Novo orçamento"


def customer_form(store, customer=None, prefix="customer", on_saved=None):
    customer = customer or {}
    with st.form(prefix + "_form", border=False):
        st.markdown('<div class="section-title">Dados pessoais</div>', unsafe_allow_html=True)
        a, b = st.columns([2, 1])
        name = a.text_input("Nome completo *", customer.get("name", ""), max_chars=150, placeholder="Nome e sobrenome", key=prefix + "name")
        cpf = b.text_input("CPF", customer.get("cpf", ""), max_chars=14, placeholder="000.000.000-00", key=prefix + "cpf")
        st.markdown('<div class="section-title">Contato</div>', unsafe_allow_html=True)
        a, b = st.columns(2)
        phone = a.text_input("Telefone / WhatsApp *", customer.get("phone", ""), max_chars=22, placeholder="(92) 99999-9999", key=prefix + "phone")
        secondary = b.text_input("Telefone adicional", customer.get("phone_secondary", ""), max_chars=22, placeholder="Opcional", key=prefix + "secondary")
        email = st.text_input("E-mail", customer.get("email", ""), max_chars=254, placeholder="cliente@exemplo.com", key=prefix + "email")
        st.markdown('<div class="section-title">Endereço de entrega</div>', unsafe_allow_html=True)
        a, b, c = st.columns([1, 2, 1])
        cep = customer.get("postal_code", "")
        postal_code = a.text_input("CEP", cep[:5] + "-" + cep[5:] if len(cep) == 8 else cep, max_chars=9, placeholder="69000-000", key=prefix + "cep")
        city = b.text_input("Cidade", customer.get("city", ""), max_chars=100, placeholder="Manaus", key=prefix + "city")
        state_options = [""] + STATES
        state = c.selectbox("Estado (UF)", state_options, index=state_options.index(customer.get("state", "")), format_func=lambda value: value or "UF", key=prefix + "state")
        a, b = st.columns([3, 1])
        street = a.text_input("Rua / avenida", customer.get("street", ""), max_chars=180, placeholder="Nome do logradouro", key=prefix + "street")
        number = b.text_input("Número", customer.get("number", ""), max_chars=20, placeholder="Ex.: 125 ou S/N", key=prefix + "number")
        a, b = st.columns(2)
        neighborhood = a.text_input("Bairro", customer.get("neighborhood", ""), max_chars=100, key=prefix + "neighborhood")
        complement = b.text_input("Complemento", customer.get("complement", ""), max_chars=150, placeholder="Apartamento, bloco, casa…", key=prefix + "complement")
        reference = st.text_input("Ponto de referência", customer.get("address_reference", ""), max_chars=200, key=prefix + "reference")
        legacy = customer.get("address", "")
        if legacy and not customer.get("street"):
            with st.expander("Endereço do cadastro anterior", expanded=False):
                legacy = st.text_area("Endereço anterior", legacy, key=prefix + "legacy")
                st.caption("Este endereço será mantido até você preencher os campos separados acima.")
        st.markdown('<div class="section-title">Foto e observações</div>', unsafe_allow_html=True)
        a, b = st.columns([1, 2])
        with a:
            upload = st.file_uploader("Foto do cliente", ["jpg", "jpeg", "png", "webp"], key=prefix + "photo")
            st.caption("JPG, PNG ou WEBP · até 10 MB")
            remove = st.checkbox("Remover foto atual", key=prefix + "remove") if customer.get("photo") else False
        notes = b.text_area("Observações sobre o cliente", customer.get("notes", ""), placeholder="Preferências e informações úteis para o atendimento.", key=prefix + "notes", height=120)
        st.caption("* Nome e telefone são obrigatórios. Os demais dados podem ser completados depois.")
        def submit():
            try:
                fields = {"name": "name", "cpf": "cpf", "phone": "phone", "phone_secondary": "secondary", "email": "email", "postal_code": "cep", "city": "city", "state": "state",
                          "street": "street", "number": "number", "neighborhood": "neighborhood", "complement": "complement", "address_reference": "reference", "notes": "notes"}
                values = {field: st.session_state.get(prefix + widget, "") for field, widget in fields.items()}
                values["address"] = st.session_state.get(prefix + "legacy", customer.get("address", ""))
                values["photo"] = customer.get("photo", "")
                # Valide os campos antes de gravar uma nova imagem no disco.
                from .domain import normalize_customer
                normalize_customer(values)
                upload = st.session_state.get(prefix + "photo")
                remove = st.session_state.get(prefix + "remove", False)
                values["photo"] = store.save_image(upload) if upload else "" if remove else values["photo"]
                saved_id = store.save_customer(values, customer.get("id"))
                st.session_state.pop(prefix + "error", None)
                if on_saved:
                    on_saved(saved_id)
            except ValueError as exc:
                st.session_state[prefix + "error"] = str(exc)
        st.form_submit_button("Salvar cliente", type="primary", icon=":material/check:", width="stretch", on_click=submit)
        if st.session_state.get(prefix + "error"):
            st.error(st.session_state[prefix + "error"])
    return None


def customers_page(store):
    clients = store.list("customers")
    mode = st.session_state.get("customer_view", "list")
    selected = st.session_state.get("customer_id")
    customer = next((c for c in clients if c["id"] == selected), None)
    if mode in ("edit", "view") and not customer:
        change_customer_view()
        mode = "list"
    if mode in ("new", "edit"):
        heading("ATENDIMENTO / CLIENTES", "Editar cliente" if mode == "edit" else "Novo cliente", "Organize os dados para facilitar o atendimento e a entrega.")
        st.button("Voltar para clientes", icon=":material/arrow_back:", on_click=change_customer_view)
        left, right = st.columns([2.6, 1], gap="large")
        with left, st.container(border=True, key="card_customers_0"):
            def saved(customer_id):
                st.session_state["notice"] = "Cadastro atualizado." if mode == "edit" else "Cliente cadastrado com sucesso."
                change_customer_view("view", customer_id)
            customer_form(store, customer if mode == "edit" else None, prefix=f"customer_{selected}_{st.session_state.get('customer_form_version', 0)}_", on_saved=saved)
        with right, st.container(border=True, key="card_customers_1"):
            if customer:
                profile_heading(customer, store)
            else:
                st.markdown("### Um cadastro, tudo organizado")
            st.markdown("**Contato**\n\nTelefone e e-mail para conversar com seu cliente.\n\n**Entrega**\n\nCEP, rua, número e complemento separados.\n\n**Histórico**\n\nOs pedidos anteriores ficam vinculados ao cadastro.")
        return

    if mode == "view":
        heading("ATENDIMENTO / CLIENTES", customer["name"], "Cadastro completo e histórico de encomendas.")
        a, b, c = st.columns([2, 1, 1])
        a.button("Todos os clientes", icon=":material/arrow_back:", on_click=change_customer_view)
        b.button("Editar cliente", icon=":material/edit:", on_click=change_customer_view, args=("edit", selected), width="stretch")
        c.button("Novo orçamento", type="primary", on_click=start_customer_quote, args=(selected,), disabled=not customer["active"], width="stretch")
        history = store.quotes(selected)
        left, right = st.columns([1, 2], gap="large")
        with left, st.container(border=True, key="card_customers_2"):
            profile_heading(customer, store, "Cliente ativo" if customer["active"] else "Cliente arquivado")
            detail("WhatsApp", phone_text(customer["phone"]))
            detail("Telefone adicional", phone_text(customer["phone_secondary"]))
            detail("E-mail", customer["email"])
            detail("CPF", customer["cpf"])
        with right:
            with st.container(border=True, key="card_customers_3"):
                st.markdown("#### Endereço de entrega")
                a, b, c = st.columns([3, 1, 1])
                with a: detail("Rua / avenida", customer["street"])
                with b: detail("Número", customer["number"])
                with c: detail("CEP", customer["postal_code"][:5] + "-" + customer["postal_code"][5:] if customer["postal_code"] else "")
                a, b, c = st.columns(3)
                with a: detail("Bairro", customer["neighborhood"])
                with b: detail("Cidade / UF", " / ".join(filter(None, [customer["city"], customer["state"]])))
                with c: detail("Complemento", customer["complement"])
                detail("Ponto de referência", customer["address_reference"])
                if customer["address"] and not customer["street"]:
                    detail("Endereço do cadastro anterior", customer["address"])
            with st.container(border=True, key="card_customers_4"):
                detail("Observações do cliente", customer["notes"])
        st.subheader("Pedidos anteriores")
        if history:
            table([{"Pedido": f"#{q['id']:04d}", "Saída": datetime.fromisoformat(q["event_at"]).strftime("%d/%m/%Y · %H:%M"), "Situação": q["status"], "Total": brl(q["totals"]["total_cents"]), "Saldo": brl(q["balance_cents"])} for q in history])
        else:
            empty_state("Nenhum pedido por aqui", "Crie o primeiro orçamento para este cliente.")
        return

    top, action = st.columns([4, 1], vertical_alignment="bottom")
    with top:
        heading("ATENDIMENTO", "Clientes", "Pessoas, contatos e histórias que fazem parte da sua confeitaria.")
    action.button("Novo cliente", type="primary", icon=":material/person_add:", on_click=change_customer_view, args=("new",), width="stretch")
    a, b, c = st.columns(3)
    all_quotes = store.quotes()
    active = [client for client in clients if client["active"]]
    a.metric("Clientes ativos", len(active))
    b.metric("Com pedidos", len({q["customer_id"] for q in all_quotes}))
    c.metric("Cadastros completos", sum(all(c[field] for field in ("email", "street", "number", "neighborhood", "city", "state", "postal_code")) for c in active))
    st.write("")
    a, b = st.columns([3, 1])
    search = a.text_input("Buscar cliente", placeholder="Nome, telefone, e-mail ou CPF", label_visibility="collapsed")
    state_filter = b.selectbox("Mostrar clientes", ["Ativos", "Arquivados", "Todos"], label_visibility="collapsed")
    digits = "".join(char for char in search if char.isdigit())
    def matches(client):
        text_match = search.casefold() in " ".join(str(client.get(field, "")) for field in ("name", "phone", "email", "cpf", "city")).casefold()
        number_match = len(digits) >= 3 and not any(char.isalpha() for char in search) and any(digits in client.get(field, "") for field in ("phone", "phone_secondary", "cpf"))
        return text_match or number_match
    visible = [c for c in clients if (state_filter == "Todos" or bool(c["active"]) == (state_filter == "Ativos")) and matches(c)]
    deleting = st.session_state.get("customer_delete_id")
    if deleting:
        target = next((c for c in clients if c["id"] == deleting), None)
        if target:
            has_orders = any(q["customer_id"] == deleting for q in all_quotes)
            with st.container(border=True, key="card_customers_5"):
                st.warning(f"{'Arquivar' if has_orders else 'Excluir'} {target['name']}?")
                st.write("O cliente sairá da lista ativa. Os pedidos e pagamentos anteriores serão preservados." if has_orders else "O cadastro será excluído. Esta ação não pode ser desfeita.")
                a, b = st.columns(2)
                if a.button("Confirmar arquivamento" if has_orders else "Confirmar exclusão", type="primary", key="confirm_delete"):
                    outcome = store.delete_customer(deleting)
                    st.session_state.pop("customer_delete_id", None)
                    st.session_state["notice"] = "Cliente arquivado. O histórico foi preservado." if outcome == "archived" else "Cliente excluído."
                    st.rerun()
                if b.button("Cancelar", key="cancel_delete"):
                    st.session_state.pop("customer_delete_id", None)
                    st.rerun()
    st.caption(f"{len(visible)} cliente(s) encontrado(s)")
    if not visible:
        empty_state("Seus clientes, bem cuidados", "Cadastre um cliente ou ajuste a busca para começar.", "♡")
    columns = st.columns(2, gap="medium")
    for i, customer in enumerate(visible):
        cid = customer["id"]
        history = [q for q in all_quotes if q["customer_id"] == cid]
        with columns[i % 2], st.container(border=True, key=f"card_customer_{cid}"):
            profile_heading(customer, store, "Cliente ativo" if customer["active"] else "Arquivado")
            location = " / ".join(filter(None, [customer["city"], customer["state"]])) or "Endereço a completar"
            contacts = contact_line("phone", phone_text(customer["phone"])) + contact_line("mail", customer["email"] or "E-mail não informado") + contact_line("place", location)
            st.markdown(f'<div class="contact-details">{contacts}</div>', unsafe_allow_html=True)
            a, b, c = st.columns([1.4, 1, 1])
            a.button("Ver cadastro", key=f"view_customer_{cid}", on_click=change_customer_view, args=("view", cid), width="stretch")
            b.button("Editar", icon=":material/edit:", key=f"edit_customer_{cid}", on_click=change_customer_view, args=("edit", cid), width="stretch")
            if customer["active"]:
                def remove(customer_id=cid):
                    st.session_state["customer_delete_id"] = customer_id
                c.button("Arquivar" if history else "Excluir", key=f"delete_customer_{cid}", on_click=remove, width="stretch")
            elif c.button("Restaurar", key=f"restore_customer_{cid}", width="stretch"):
                store.restore_customer(cid)
                st.session_state["notice"] = "Cliente restaurado."
                st.rerun()
            st.markdown(f'<div class="contact-footer">{len(history)} pedido(s) no histórico</div>', unsafe_allow_html=True)
