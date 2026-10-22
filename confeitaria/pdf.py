"""Dois documentos distintos: orçamento comercial e ficha sem campos financeiros."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .domain import brl, quantity_text

INK = colors.HexColor("#342C30")
ROSE = colors.HexColor("#944D63")
PALE = colors.HexColor("#F6EDEF")


def formatted_date(value):
    return datetime.fromisoformat(value).strftime("%d/%m/%Y às %H:%M")


def generate_pdf(quote, store, kitchen=False):
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=(21 * cm, 29.7 * cm), rightMargin=1.5 * cm,
                            leftMargin=1.5 * cm, topMargin=1.4 * cm, bottomMargin=1.6 * cm,
                            title=f"{'Ficha de produção' if kitchen else 'Orçamento'} #{quote['id']:04d}",
                            author=quote["shop"]["name"])
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyLocal", fontName="Helvetica", fontSize=10, leading=15, textColor=INK, spaceAfter=6))
    styles.add(ParagraphStyle(name="TitleLocal", fontName="Helvetica-Bold", fontSize=22, leading=28, textColor=ROSE, spaceAfter=12))
    styles.add(ParagraphStyle(name="SmallLocal", fontSize=8, leading=12, textColor=INK, spaceAfter=5))
    styles.add(ParagraphStyle(name="RightLocal", parent=styles["BodyLocal"], alignment=TA_RIGHT))

    def p(text, style="BodyLocal"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles[style])

    def photo(name, width=5 * cm, height=4 * cm):
        path = store.image_path(name)
        if not path:
            return p("Foto de referência não cadastrada.", "SmallLocal")
        from PIL import Image as PILImage
        with PILImage.open(path) as source:
            ratio = min(width / source.width, height / source.height)
            return Image(str(path), width=source.width * ratio, height=source.height * ratio)

    shop, customer = quote["shop"], quote["customer"]
    story = []
    if shop.get("logo") and store.image_path(shop["logo"]):
        story.extend([photo(shop["logo"], 4 * cm, 2 * cm), Spacer(1, 8)])
    story += [p(shop["name"], "TitleLocal"), p(" · ".join(filter(None, [shop.get("phone"), shop.get("document")]))), p(shop.get("address", "")), Spacer(1, 10),
              p(f"{'FICHA DE PRODUÇÃO' if kitchen else 'ORÇAMENTO'} #{quote['id']:04d}", "Heading2"),
              p(f"Cliente: {customer['name']} | WhatsApp: {customer['phone']}"),
              p(f"Saída / retirada: {formatted_date(quote['event_at'])} | {quote['fulfillment']}"),
              p(f"Endereço: {(quote.get('delivery_address') or customer.get('address') or 'Não informado') if quote['fulfillment'] == 'Entrega' else 'Retirada na loja'}")]
    if not kitchen:
        story += [p(f"CPF: {customer.get('cpf') or 'Não informado'}"),
                  p(f"Emitido em: {formatted_date(quote['created_at'])} | Válido até: {datetime.fromisoformat(quote['valid_until']).strftime('%d/%m/%Y')}"),
                  p(f"Status: {quote.get('status', 'Em Aberto')}"), Spacer(1, 8)]
    else:
        story += [Spacer(1, 8), p("REFERÊNCIA DO PEDIDO", "Heading3"), photo(quote.get("reference_photo")), Spacer(1, 8)]

    def line_description(line):
        pieces = [line["name"] + (" [BRINDE]" if line["gift"] else "")]
        if line.get("promotional") and not kitchen:
            pieces.append("Preço promocional aplicado")
        if line.get("fillings"):
            pieces.append("Recheios: " + ", ".join(line["fillings"]))
        if line.get("composition"):
            pieces.append("Composição por kit: " + "; ".join(line["composition"]))
        if line.get("negotiation", {}).get("notes"):
            pieces.append("Exceção autorizada pela confeiteira: " + line["negotiation"]["notes"])
        if line.get("brigadeiro_type"):
            pieces.append("Brigadeiros: " + line["brigadeiro_type"])
            pieces.append(("50/50 (50 de cada sabor por cento): " if line.get("split") else "Sabor: ") + " / ".join(line.get("flavors", [])))
        for extra in line.get("extras", []):
            label = f"Adicional: {extra.get('quantity', 1)} × {extra['name']}"
            label += " [BRINDE]" if extra["gift"] or line["gift"] else "" if kitchen else f" — {brl(extra['amount_cents'])}"
            pieces.append(label)
            if extra.get("flavors"):
                pieces.append(extra.get("brigadeiro_type", "") + ": " + " / ".join(extra["flavors"]))
            if extra.get("personalization"):
                pieces.append("Personalização: " + extra["personalization"])
        if line.get("details"):
            pieces.append("Detalhes: " + line["details"])
        return "\n".join(pieces)

    if kitchen:
        for line in quote["lines"]:
            story += [p(f"{quantity_text(line['quantity'])} {line['unit']} · {line['name']}", "Heading3"), p(line_description(line)), Spacer(1, 10)]
            if line.get("reference_photo"):
                story += [p("Inspiração deste item", "SmallLocal"), photo(line["reference_photo"]), Spacer(1, 10)]
            for extra in line.get("extras", []):
                if extra.get("reference_photo"):
                    story += [p("Inspiração: " + extra["name"], "SmallLocal"), photo(extra["reference_photo"]), Spacer(1, 10)]
        story += [p("DECORAÇÃO E ALERGIAS", "Heading2"), p(quote.get("production_notes") or "Nenhuma observação registrada."),
                  p("CONFERÊNCIA", "Heading3"), p("Produzido por: ____________________    Conferido por: ____________________"),
                  p("Embalagem, transporte e restrições: confira as observações de produção antes da saída.")]
    else:
        rows = [[p("Item / sabores / adicionais", "SmallLocal"), p("Qtd.", "SmallLocal"), p("Unitário", "SmallLocal"), p("Total", "SmallLocal")]]
        for line in quote["lines"]:
            rows.append([p(line_description(line), "SmallLocal"), p(f"{quantity_text(line['quantity'])} {line['unit']}", "SmallLocal"),
                         p(brl(0 if line["gift"] else line["unit_cents"]), "SmallLocal"), p(brl(line["total_cents"]), "SmallLocal")])
        table = Table(rows, colWidths=[10.2 * cm, 2 * cm, 2.9 * cm, 2.9 * cm], repeatRows=1, splitInRow=1, hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), PALE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, 0), 1, ROSE), ("LINEBELOW", (0, 1), (-1, -1), .3, colors.HexColor("#DDDDDD")),
                                   ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
        story += [table, Spacer(1, 14)]
        total = quote["totals"]
        summary = [p(f"Subtotal: {brl(total['subtotal_cents'])}", "RightLocal"),
                   p(f"Desconto geral: {brl(total['discount_cents'])} | Frete: {brl(total['delivery_cents'])}", "RightLocal"),
                   p(f"Preço Cartão: {brl(total['card_cents'])}", "RightLocal")]
        if quote["pix_enabled"]:
            summary += [p(f"Desconto PIX/Dinheiro ativado: {quote['pix_percent']}% = {brl(total['pix_discount_cents'])}", "RightLocal"),
                        p(f"Valor PIX/Dinheiro: {brl(total['total_cents'])}", "RightLocal")]
        summary += [p(f"Total acordado ({quote['payment_method']}): {brl(total['total_cents'])}", "Heading3"),
                    p(f"Sinal mínimo (50%): {brl(total['deposit_cents'])} | Recebido: {brl(quote.get('paid_cents', 0))}"),
                    p(f"Saldo devedor: {brl(total['total_cents'] - quote.get('paid_cents', 0))}")]
        story += [KeepTogether(summary), p("OBSERVAÇÕES GERAIS", "Heading3"), p(quote.get("notes") or "Nenhuma observação registrada."),
                  p("DECORAÇÃO / ALERGIAS / TRANSPORTE", "Heading3"), p(quote.get("production_notes") or "Nenhuma observação registrada."), Spacer(1, 18),
                  p("A data e produção só estarão garantidas mediante entrada de 50%. Em caso de desistência, o valor da entrada não será devolvido (Artigos 417 a 420 do Código Civil). "
                    f"Alterações no pedido aceitas até {shop['change_days']} dias antes do evento.", "SmallLocal")]

    def footer(canvas, document):
        canvas.setStrokeColor(ROSE)
        canvas.line(1.5 * cm, 1.1 * cm, 19.5 * cm, 1.1 * cm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(INK)
        canvas.drawString(1.5 * cm, .7 * cm, "Ficha interna de produção" if kitchen else "Orçamento · Conserve uma cópia deste documento")
        canvas.drawRightString(19.5 * cm, .7 * cm, f"Página {document.page}")

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
