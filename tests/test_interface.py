"""Fluxos completos com os controles reais do Streamlit em bases temporárias."""
from datetime import datetime, timedelta
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from confeitaria.domain import make_line
from confeitaria.storage import Store


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"CONFEITARIA_DATA_DIR": str(root / "dados"), "CONFEITARIA_MEDIA_DIR": str(root / "midia")})
        self.env.start()
        self.postal = patch("confeitaria.postal.lookup_postal_code", side_effect=ValueError("Consulta indisponível. Preencha manualmente."))
        self.postal.start()
        st.cache_resource.clear()
        self.store = Store()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=15).run()
        self.assert_clean()

    def tearDown(self):
        st.cache_resource.clear()
        self.env.stop()
        self.postal.stop()
        self.temp.cleanup()

    def assert_clean(self):
        self.assertFalse(self.app.exception, [e.message for e in self.app.exception])

    def widget(self, kind, label):
        matches = [w for w in getattr(self.app, kind) if w.label == label]
        self.assertEqual(len(matches), 1, (kind, label, [w.label for w in getattr(self.app, kind)]))
        return matches[0]

    def page(self, page):
        self.app.sidebar.radio[0].set_value(page).run()
        self.assert_clean()

    def click(self, label):
        self.widget("button", label).click().run()
        self.assert_clean()

    def click_key(self, key):
        next(w for w in self.app.button if w.key == key).click().run()
        self.assert_clean()

    def client(self):
        return self.store.save_customer({"name": "Maria dos Bolos", "phone": "92999998888", "cpf": "", "street": "Rua A", "number": "42", "city": "Manaus", "state": "AM", "postal_code": "69000000", "photo": ""})

    def test_brand_settings_replace_header_persist_and_remove_logo(self):
        from io import BytesIO
        from PIL import Image
        photo = BytesIO()
        Image.new("RGBA", (1200, 180), "#d86b52").save(photo, "PNG")
        settings = self.store.settings()
        settings["logo"] = self.store.save_image(photo)
        self.store.save_settings(settings)
        self.page("Configurações")
        self.widget("text_input", "Nome da confeitaria *").set_value('Doces & Afeto <Ateliê>')
        self.click("Salvar configurações")
        header = self.app.sidebar.markdown[0].value
        self.assertIn('Doces &amp; Afeto &lt;Ateliê&gt;', header)
        self.assertIn('alt="Logo da confeitaria"', header)
        self.assertIn('data:image/png;base64,', header)
        st.cache_resource.clear()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=15).run()
        self.assert_clean()
        self.assertIn('Doces &amp; Afeto', self.app.sidebar.markdown[0].value)
        self.assertIn('data:image/png;base64,', self.app.sidebar.markdown[0].value)
        self.page("Configurações")
        self.widget("checkbox", "Remover logo atual").check()
        self.click("Salvar configurações")
        self.assertNotIn('<img', self.app.sidebar.markdown[0].value)
        self.assertIn('Doces &amp; Afeto', self.app.sidebar.markdown[0].value)
        self.assertEqual(Store().settings()["logo"], "")

    def start_quote(self, client=None):
        client = client or self.client()
        self.page("Novo orçamento")
        self.widget("selectbox", "Cliente").select(client).run()
        self.click("Continuar para produtos")
        return client

    def add_cake(self):
        self.widget("checkbox", "Ninho").check().run()
        self.click("Adicionar ao pedido")

    def create_order(self, client):
        product = next(p for p in self.store.list("products") if p["name"] == "Bolo Simples")
        return self.store.save_quote({"customer_id": client, "event_at": (datetime.now() + timedelta(days=10)).isoformat(timespec="minutes"),
                                     "fulfillment": "Retirada", "delivery_address": "", "lines": [make_line(product, 2, ["Ninho"])], "payment_method": "PIX", "pix_enabled": False, "pix_percent": "0", "discount_cents": 0, "delivery_cents": 0,
                                     "notes": "", "production_notes": "Tema jardim.", "reference_photo": ""})

    def test_all_empty_pages_render(self):
        for page in ["Catálogo", "Insumos e estoque", "Clientes", "Novo orçamento", "Orçamentos e pagamentos", "Agenda de produção", "Configurações"]:
            with self.subTest(page=page):
                self.page(page)

    def test_complete_customer_form_and_edit_action(self):
        self.page("Clientes")
        self.click("Novo cliente")
        values = {"Nome completo *": "Maria dos Bolos", "Telefone / WhatsApp *": "(92) 99999-8888", "E-mail": "maria@exemplo.com", "CEP": "69000-000", "Cidade": "Manaus", "Rua / avenida": "Rua A", "Número": "42", "Bairro": "Centro", "Complemento": "Casa 2", "Ponto de referência": "Ao lado da praça"}
        for label, value in values.items():
            self.widget("text_input", label).input(value)
        self.widget("selectbox", "Estado (UF)").select("AM")
        self.click("Salvar cliente")
        client = self.store.list("customers")[0]
        self.assertEqual(client["email"], "maria@exemplo.com")
        self.assertIn("Rua A, 42", client["address"])
        self.click("Editar cliente")
        self.widget("text_input", "Número").input("80")
        self.click("Salvar cliente")
        self.assertEqual(self.store.get_customer(client["id"])["number"], "80")
        self.assertIn("Rua A, 80", self.store.get_customer(client["id"])["address"])

    def test_customer_delete_requires_confirmation(self):
        client = self.client()
        self.page("Clientes")
        self.click_key(f"delete_customer_{client}")
        self.assertIsNotNone(self.store.get_customer(client))
        self.click("Cancelar")
        self.assertIsNotNone(self.store.get_customer(client))
        self.click_key(f"delete_customer_{client}")
        self.click("Confirmar exclusão")
        self.assertIsNone(self.store.get_customer(client))

    def test_archive_and_restore_from_customer_list(self):
        client = self.client()
        order = self.create_order(client)
        self.page("Clientes")
        self.click_key(f"delete_customer_{client}")
        self.click("Confirmar arquivamento")
        self.assertFalse(self.store.get_customer(client)["active"])
        self.assertEqual(self.store.quotes()[0]["id"], order)
        self.widget("selectbox", "Mostrar clientes").select("Arquivados").run()
        self.click_key(f"restore_customer_{client}")
        self.assertTrue(self.store.get_customer(client)["active"])

    def test_new_client_inside_quote_keeps_delivery_date(self):
        self.page("Novo orçamento")
        event = (datetime.now() + timedelta(days=15)).strftime("%d/%m/%Y")
        self.widget("text_input", "Data da encomenda").input(event).run()
        self.click("Novo cliente")
        self.widget("text_input", "Nome completo *").input("Cliente do orçamento")
        self.widget("text_input", "Telefone / WhatsApp *").input("92999998888")
        self.widget("text_input", "E-mail").input("cliente@exemplo.com")
        self.click("Salvar cliente")
        client = self.store.list("customers")[0]
        self.assertEqual(self.widget("selectbox", "Cliente").value, client["id"])
        self.assertEqual(self.widget("text_input", "Data da encomenda").value, event)
        self.click("Continuar para produtos")
        self.assertIsNotNone(self.widget("checkbox", "Ninho"))

    def test_category_widgets_and_brigadeiro_split(self):
        self.start_quote()
        for category, allowed, forbidden in [("Bolos Simples", "Ninho", "Nutella"), ("Bolos Especiais", "Nutella", "Ninho")]:
            self.widget("radio", "Categoria").set_value(category).run()
            self.assert_clean()
            labels = [w.label for w in self.app.checkbox]
            self.assertIn(allowed, labels)
            self.assertNotIn(forbidden, labels)
        self.widget("radio", "Categoria").set_value("Cento de Brigadeiros").run()
        self.widget("selectbox", "Tipo de brigadeiro").select("Tradicional").run()
        self.widget("checkbox", "Dividir cento em 50/50").check().run()
        self.assert_clean()
        self.assertEqual(self.widget("selectbox", "Sabor 2").options, ["Chocolate", "Beijinho"])

    def test_both_cakes_require_explicit_weight_and_filling_exceptions(self):
        self.start_quote()
        for category, flavors in [("Bolos Simples", ["Chocolate", "Ninho"]), ("Bolos Especiais", ["Nutella", "Ninho com Morango"])]:
            self.widget("radio", "Categoria").set_value(category).run()
            self.widget("number_input", "Peso do bolo (kg)").set_value(1.5).run()
            for flavor in flavors:
                self.widget("checkbox", flavor).check()
            self.click("Adicionar ao pedido")
            self.assertTrue(self.app.warning)
            self.assertTrue(self.app.error)
            before = len(self.app.session_state["draft"]["lines"])
            self.widget("checkbox", "Confirmar exceção combinada com a confeiteira").check()
            self.widget("text_input", "Motivo / condição da exceção").input("Combinado por telefone com a confeiteira.")
            self.click("Adicionar ao pedido")
            self.assertFalse(self.app.error)
            lines = self.app.session_state["draft"]["lines"]
            self.assertEqual(len(lines), before+1)
            self.assertTrue(lines[-1]["negotiation"]["under_minimum"])
            self.assertTrue(lines[-1]["negotiation"]["extra_fillings"])

    def test_postal_lookup_fills_address_preserving_house_and_complement(self):
        self.page("Clientes")
        self.click("Novo cliente")
        self.widget("text_input", "Número").input("18")
        self.widget("text_input", "Complemento").input("Casa B").run()
        result = {"postal_code":"01001000", "street":"Praça da Sé", "neighborhood":"Sé", "city":"São Paulo", "state":"SP"}
        with patch("confeitaria.postal.lookup_postal_code", return_value=result):
            self.widget("text_input", "CEP").input("01001-000").run()
        self.assertEqual(self.widget("text_input", "Rua / avenida").value, "Praça da Sé")
        self.assertEqual(self.widget("text_input", "Cidade").value, "São Paulo")
        self.assertEqual(self.widget("selectbox", "Estado (UF)").value, "SP")
        self.assertEqual(self.widget("text_input", "Número").value, "18")
        self.assertEqual(self.widget("text_input", "Complemento").value, "Casa B")
        self.widget("text_input", "CEP").input("99999-999").run()
        self.assertEqual(self.widget("text_input", "Rua / avenida").value, "Praça da Sé")

    def test_kit_composition_and_brigadeiro_extras(self):
        self.start_quote()
        self.widget("radio", "Categoria").set_value("Kits Festa").run()
        self.assertEqual(len(self.widget("selectbox", "Produto").options), 4)
        self.assertIn("10 brigadeiros tradicionais", " ".join(w.value for w in self.app.markdown))
        self.widget("radio", "Categoria").set_value("Bolos Simples").run()
        self.widget("checkbox", "Ninho").check()
        self.widget("multiselect", "Adicionar ao bolo").select("Brigadeiros no Topo").run()
        self.assertEqual(self.widget("multiselect", "Sabores dos brigadeiros adicionais").options, ["Chocolate", "Beijinho"])
        self.widget("multiselect", "Sabores dos brigadeiros adicionais").select("Chocolate")
        self.widget("number_input", "Quantidade do adicional").set_value(10)
        self.widget("number_input", "Valor unitário (R$)").set_value(3.0)
        self.click("Adicionar ao pedido")
        self.assertEqual(self.app.session_state["draft"]["lines"][-1]["total_cents"], 18000)

    def test_orders_list_starts_closed_and_filters_delivered(self):
        client = self.client()
        identifier = self.create_order(client)
        self.page("Orçamentos e pagamentos")
        self.assertEqual(len(self.app.get("download_button")), 0)
        self.widget("radio", "Situação dos pedidos").set_value("Fechados").run()
        self.assertFalse(any(w.key == f"open_order_{identifier}" for w in self.app.button))
        self.widget("radio", "Situação dos pedidos").set_value("Abertos").run()
        self.click_key(f"open_order_{identifier}")
        self.assertEqual(len(self.app.get("download_button")), 2)
        self.click("Voltar para pedidos")
        self.assertEqual(len(self.app.get("download_button")), 0)

    def test_demo_toggle_keeps_real_data_separate(self):
        self.client()
        self.widget("toggle", "Ver demonstração").set_value(True).run()
        self.assert_clean()
        self.page("Clientes")
        self.assertEqual(self.app.metric[0].value, "6")
        self.widget("toggle", "Ver demonstração").set_value(False).run()
        self.assert_clean()
        self.page("Clientes")
        self.assertEqual(self.app.metric[0].value, "1")

    def test_cart_item_edit_and_step_persistence(self):
        self.start_quote()
        self.add_cake()
        self.click("Editar item")
        self.widget("number_input", "Peso do bolo (kg)").set_value(3.0)
        self.click("Salvar alterações do item")
        self.assertEqual(len(self.app.session_state["draft"]["lines"]), 1)
        self.assertEqual(self.app.session_state["draft"]["lines"][0]["total_cents"], 22500)
        self.click("Continuar para pagamento")
        self.widget("number_input", "Desconto geral (R$)").set_value(13.0).run()
        self.widget("text_area", "Orientações para a cozinha").input("Tema jardim.").run()
        self.click("Voltar")
        self.assertTrue(self.widget("checkbox", "Ninho").value)
        self.click("Continuar para pagamento")
        self.assertEqual(self.widget("number_input", "Desconto geral (R$)").value, 13.0)
        self.assertEqual(self.widget("text_area", "Orientações para a cozinha").value, "Tema jardim.")
        self.click("Voltar")
        self.click("Remover item")
        self.assertEqual(len(self.app.session_state["draft"]["lines"]), 0)

    def test_quote_to_payment_and_delivery(self):
        client = self.client()
        self.page("Novo orçamento")
        self.widget("selectbox", "Cliente").select(client).run()
        self.widget("radio", "Como o cliente vai receber?").set_value("Entrega").run()
        self.click("Continuar para produtos")
        self.widget("checkbox", "Ninho").check().run()
        self.widget("multiselect", "Adicionar ao bolo").select("Topo de Bolo Simples").run()
        self.widget("number_input", "Valor unitário (R$)").set_value(25.0)
        self.widget("checkbox", "É cortesia").check().run()
        self.click("Adicionar ao pedido")
        self.click("Continuar para pagamento")
        self.widget("checkbox", "Conceder desconto PIX / Dinheiro").check().run()
        self.widget("number_input", "Desconto PIX / Dinheiro (%)").set_value(10.0)
        self.widget("number_input", "Desconto geral (R$)").set_value(10.0)
        self.widget("number_input", "Entrega / frete (R$)").set_value(20.0)
        self.widget("text_area", "Orientações para a cozinha").input("Sem castanhas. Tema jardim.")
        self.click("Revisar orçamento")
        self.click("Salvar orçamento")
        q = self.store.quotes()[0]
        self.assertEqual(q["totals"]["total_cents"], 14600)
        self.assertTrue(q["lines"][0]["extras"][0]["gift"])
        self.assertIn("Rua A, 42", q["delivery_address"])
        self.assertEqual(self.app.sidebar.radio[0].value, "Orçamentos e pagamentos")
        self.assertEqual(len(self.app.get("download_button")), 0)
        self.click_key(f"open_order_{q['id']}")
        self.assertEqual(len(self.app.get("download_button")), 2)
        self.widget("checkbox", "Confirmo que este valor já foi recebido").check()
        self.click("Registrar recebimento")
        self.assertEqual(self.store.quotes()[0]["status"], "Aprovado / Data Reservada")
        self.assertEqual(self.store.quotes()[0]["balance_cents"], 7300)
        self.widget("checkbox", "Confirmo que este valor já foi recebido").check()
        self.click("Registrar recebimento")
        self.assertEqual(self.store.quotes()[0]["balance_cents"], 0)
        self.click("Registrar entrega / retirada concluída")
        self.assertEqual(self.store.quotes()[0]["status"], "Entregue")

    def test_wizard_prevents_incomplete_customer_or_invalid_discount(self):
        self.page("Novo orçamento")
        self.click("Continuar para produtos")
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state["draft"]["_step"], 0)
        client = self.client()
        self.app.run()
        self.widget("selectbox", "Cliente").select(client).run()
        self.click("Continuar para produtos")
        self.add_cake()
        self.click("Continuar para pagamento")
        self.widget("number_input", "Desconto geral (R$)").set_value(9999.0)
        self.click("Revisar orçamento")
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state["draft"]["_step"], 2)
        self.assertEqual(len(self.store.quotes()), 0)

    def test_calendar_selects_reserved_day(self):
        client = self.client()
        quote_id = self.create_order(client)
        self.store.add_payment(quote_id, 7500, "PIX")
        event = datetime.fromisoformat(self.store.quotes()[0]["event_at"])
        self.page("Agenda de produção")
        self.widget("selectbox", "Mês da agenda").select(event.month).run()
        self.widget("number_input", "Ano da agenda").set_value(event.year).run()
        self.click(f"{event.day} · 1 pedido(s)")
        self.assertEqual(self.widget("text_input", "Encomendas do dia").value, event.strftime("%d/%m/%Y"))
        self.assertEqual(len(self.app.get("download_button")), 1)


if __name__ == "__main__":
    unittest.main()
