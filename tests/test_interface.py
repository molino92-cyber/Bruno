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
        st.cache_resource.clear()
        self.store = Store()
        self.app = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=15).run()
        self.assert_clean()

    def tearDown(self):
        st.cache_resource.clear()
        self.env.stop()
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
        self.widget("checkbox", "Dividir cento em 50/50").check().run()
        self.assert_clean()
        self.assertIsNotNone(self.widget("text_input", "Sabor 2"))

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
        self.widget("number_input", "Valor do adicional (R$)").set_value(25.0)
        self.widget("checkbox", "É cortesia").check().run()
        self.click("Adicionar ao pedido")
        self.click("Continuar para pagamento")
        self.widget("checkbox", "Conceder desconto PIX / Dinheiro").check().run()
        self.widget("number_input", "Desconto PIX / Dinheiro (%)").set_value(10.0)
        self.widget("number_input", "Desconto geral (R$)").set_value(10.0)
        self.widget("number_input", "Entrega / frete (R$)").set_value(20.0)
        self.widget("text_area", "Orientações para a cozinha").input("Sem castanhas. Tema jardim.")
        self.click("Revisar orçamento")
        self.click("Salvar orçamento e abrir pedido")
        q = self.store.quotes()[0]
        self.assertEqual(q["totals"]["total_cents"], 14600)
        self.assertTrue(q["lines"][0]["extras"][0]["gift"])
        self.assertIn("Rua A, 42", q["delivery_address"])
        self.assertEqual(self.app.sidebar.radio[0].value, "Orçamentos e pagamentos")
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
