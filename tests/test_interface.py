"""Fluxos reais de widgets no runner oficial do Streamlit, sem dados de produção."""
from datetime import date, datetime, timedelta
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

    def client(self):
        return self.store.save_customer({"name": "Maria dos Bolos", "phone": "92999998888", "cpf": "", "address": "Rua A, 42", "photo": ""})

    def test_all_empty_pages_render(self):
        for page in ["Catálogo", "Insumos e estoque", "Clientes", "Novo orçamento", "Orçamentos e pagamentos", "Agenda de produção", "Configurações"]:
            with self.subTest(page=page):
                self.page(page)

    def test_customer_and_inventory_forms(self):
        self.page("Clientes")
        self.widget("text_input", "Nome completo *").input("Maria dos Bolos")
        self.widget("text_input", "Telefone / WhatsApp com DDD *").input("92999998888")
        self.widget("text_area", "Endereço de entrega").input("Rua A, 42")
        self.click("Salvar cliente")
        self.assertEqual(self.store.list("customers")[0]["name"], "Maria dos Bolos")
        self.page("Insumos e estoque")
        self.widget("text_input", "Nome *").input("Leite condensado")
        self.widget("text_input", "Marca").input("Italac")
        self.widget("number_input", "Conteúdo por embalagem *").set_value(395.0)
        self.widget("number_input", "Quantidade em estoque (embalagens)").set_value(5.0)
        self.widget("number_input", "Valor pago por embalagem (R$)").set_value(6.0)
        self.click("Salvar insumo")
        self.assertEqual(self.store.list("inventory")[0]["paid_cents"], 600)

    def test_category_widgets_and_brigadeiro_split(self):
        self.client()
        self.page("Novo orçamento")
        products = self.store.list("products")
        for category, allowed, forbidden in [("Bolos Simples", "Ninho", "Nutella"), ("Bolos Especiais", "Nutella", "Ninho")]:
            p = next(p for p in products if p["category"] == category)
            self.widget("selectbox", "Produto").select(p["id"]).run()
            self.assert_clean()
            labels = [w.label for w in self.app.checkbox]
            self.assertIn(allowed, labels)
            self.assertNotIn(forbidden, labels)
        p = next(p for p in products if p["category"] == "Cento de Brigadeiros")
        self.widget("selectbox", "Produto").select(p["id"]).run()
        self.widget("checkbox", "Dividir cento em 50/50").check().run()
        self.assert_clean()
        self.assertIsNotNone(self.widget("text_input", "Sabor 2"))

    def test_quote_to_payment_and_delivery(self):
        self.client()
        self.page("Novo orçamento")
        simple = next(p for p in self.store.list("products") if p["name"] == "Bolo Simples")
        self.widget("selectbox", "Produto").select(simple["id"]).run()
        self.widget("checkbox", "Ninho").check().run()
        self.widget("checkbox", "Topo de Bolo Simples").check().run()
        self.widget("number_input", "Topo de Bolo Simples · valor total (R$)").set_value(25.0)
        self.widget("checkbox", "Brinde / Cortesia").check().run()
        self.click("＋ Adicionar ao orçamento")
        self.widget("checkbox", "Aplicar desconto PIX / Dinheiro manualmente").check().run()
        self.widget("number_input", "Percentual PIX / Dinheiro (%)").set_value(10.0)
        self.widget("number_input", "Desconto manual geral (R$)").set_value(10.0)
        self.widget("number_input", "Taxa de entrega / frete (R$)").set_value(20.0)
        self.widget("text_area", "Decoração, alergias, restrições e transporte · também aparecem na ficha da cozinha").input("Sem castanhas. Tema jardim.")
        self.click("Salvar orçamento")
        q = self.store.quotes()[0]
        self.assertEqual(q["totals"]["total_cents"], 14600)
        self.assertTrue(q["lines"][0]["extras"][0]["gift"])
        self.page("Orçamentos e pagamentos")
        self.assertEqual(len(self.app.get("download_button")), 2)
        self.widget("checkbox", "Confirmo que este valor já foi recebido").check()
        self.click("Registrar recebimento")
        q = self.store.quotes()[0]
        self.assertEqual(q["status"], "Aprovado / Data Reservada")
        self.assertEqual(q["balance_cents"], 7300)
        self.widget("checkbox", "Confirmo que este valor já foi recebido").check()
        self.click("Registrar recebimento")
        self.assertEqual(self.store.quotes()[0]["balance_cents"], 0)
        self.click("Registrar entrega / retirada concluída")
        self.assertEqual(self.store.quotes()[0]["status"], "Entregue")

    def test_calendar_selects_reserved_day(self):
        client = self.client()
        product = next(p for p in self.store.list("products") if p["name"] == "Bolo Simples")
        event = datetime.now() + timedelta(days=10)
        quote_id = self.store.save_quote({"customer_id": client, "event_at": event.isoformat(timespec="minutes"), "fulfillment": "Retirada", "delivery_address": "",
                                         "lines": [make_line(product, 2, ["Ninho"])], "payment_method": "PIX", "pix_enabled": False, "pix_percent": "0", "discount_cents": 0, "delivery_cents": 0,
                                         "notes": "", "production_notes": "Tema jardim.", "reference_photo": ""})
        self.store.add_payment(quote_id, 7500, "PIX")
        self.page("Agenda de produção")
        self.widget("date_input", "Mês da agenda").set_value(event.date()).run()
        self.click(f"{event.day} · 1 pedido(s)")
        self.assertEqual(self.widget("date_input", "Encomendas do dia").value, event.date())
        self.assertEqual(len(self.app.get("download_button")), 1)


if __name__ == "__main__":
    unittest.main()
