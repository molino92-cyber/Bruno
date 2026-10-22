"""Componentes visuais compartilhados e controles em português."""
import base64
import calendar
from datetime import date
from html import escape

import streamlit as st

from .domain import brl

MONTHS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def apply_theme():
    st.markdown("""<style>
    :root {--primary-color:#d86b52;}
    .stApp {background:#f5f6f8;color:#243346;}
    .block-container {max-width:1460px;padding:2rem 2.6rem 3rem;}
    [data-testid="stHeader"] {background:transparent;}
    [data-testid="stToolbar"], .stAppDeployButton, #MainMenu, footer {display:none!important;}
    [data-testid="stSidebar"] {background:#182a35;border-right:0;min-width:250px;max-width:270px;}
    [data-testid="stSidebar"] * {color:#dbe5e9;}
    [data-testid="stSidebar"] .block-container {padding:1.4rem;}
    [data-testid="stSidebar"] [data-testid="stRadio"] label>div {font-size:.92rem;}
    [data-testid="stSidebar"] [role="radiogroup"] {gap:5px;}
    [data-testid="stSidebar"] [role="radiogroup"]>label {padding:10px 13px;border-radius:9px;width:100%;transition:background .2s;}
    [data-testid="stSidebar"] [role="radiogroup"]>label:hover {background:#263d49;}
    [data-testid="stSidebar"] [role="radiogroup"]>label:has(input:checked) {background:#34515c;box-shadow:inset 3px 0 #f29c7e;}
    [data-testid="stSidebar"] [role="radiogroup"]>label>div:first-child {display:none;}
    [data-testid="stSidebar"] hr {border-color:#34505c;}
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#9eb3bc;font-size:.78rem;}
    h1,h2,h3,h4 {color:#213644;letter-spacing:-.025em;}
    h1 {font-size:2rem!important;font-weight:750!important;}
    h2 {font-size:1.4rem!important;} h3 {font-size:1.15rem!important;}
    p,label {font-size:.92rem;}
    .hero {margin-bottom:1.4rem;}
    .hero .eyebrow {font-size:.7rem;font-weight:700;letter-spacing:.13em;color:#87959f;margin-bottom:9px;}
    .hero h1 {margin:0;padding:0!important;}
    .hero p {color:#74828e;margin-top:9px;font-size:.92rem;}
    .brand {display:flex;align-items:center;gap:12px;margin:10px 0 30px;}
    .brand-icon {font-size:27px;background:#f1c8b9;border-radius:12px;padding:8px;line-height:1;}
    .brand strong {font-size:1.35rem;color:#fff!important;letter-spacing:-.03em;}
    .brand small {display:block;font-size:.67rem;color:#9db2bd!important;letter-spacing:.13em;margin-top:4px;}
    .nav-caption {color:#8099a7!important;font-size:.65rem;letter-spacing:.14em;margin:12px 0;}
    .sidebar-footer {margin-top:32px;border:1px solid #35505c;border-radius:12px;padding:14px;}
    .sidebar-footer strong {font-size:.8rem;display:block;color:#d8e7ec!important;}
    .sidebar-footer span {font-size:.72rem;color:#92abb6!important;}
    div[data-testid="stVerticalBlockBorderWrapper"]>div {border-radius:14px!important;}
    [data-testid="stVerticalBlockBorderWrapper"]:has(>[data-testid="stVerticalBlock"]), [data-testid="stVerticalBlockBorderWrapper"]>div[style*="border"] {background:#fff;}
    [data-testid="stVerticalBlockBorderWrapper"] {border-color:#e5e9ed!important;}
    [data-testid="stMetric"] {background:#fff;border:1px solid #e5e9ed;border-radius:13px;padding:18px 20px;min-height:105px;}
    [data-testid="stMetricLabel"] p {font-size:.78rem;color:#7a8790;}
    [data-testid="stMetricValue"] {font-size:1.65rem;font-weight:700;color:#263f4d;}
    [class*="st-key-card_"] {background:#fff!important;border-color:#e3e8ec!important;border-radius:14px!important;}
    [class*="st-key-delete_customer_"] button {color:#b7685a;border-color:#ecd9d4;}
    .stButton>button,.stDownloadButton>button,.stFormSubmitButton>button {border-radius:9px;min-height:39px;font-weight:600;font-size:.85rem;border-color:#dee4e8;}
    .stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"] {background:#d86b52;border-color:#d86b52;color:white;box-shadow:0 3px 7px #d86b5218;}
    [data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"] {border-radius:8px!important;background-color:#fbfcfd;}
    [data-testid="stCaptionContainer"] p {color:#84919a;font-size:.8rem;}
    [data-testid="InputInstructions"] {display:none;}
    .section-title {font-size:1rem;font-weight:700;color:#294453;margin:4px 0 4px;}
    .muted {color:#81909a;font-size:.82rem;}
    .badge {display:inline-flex;align-items:center;gap:5px;border-radius:6px;padding:4px 8px;font-size:.67rem;font-weight:700;background:#e9f5ee;color:#34845f;}
    .badge.pink {background:#fbece7;color:#bd654e;} .badge.gray {background:#eff2f5;color:#71808b;}
    .avatar {height:54px;width:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#f5e6df;color:#ba7864;font-size:18px;font-weight:700;flex-shrink:0;object-fit:cover;}
    .profile-heading {display:flex;gap:13px;align-items:center;margin:3px 0 17px;}
    .profile-heading strong {display:block;color:#29404d;font-size:1rem;}
    .profile-heading small {color:#87959e;font-size:.76rem;display:block;margin-top:4px;}
    .contact-details {min-height:63px;color:#75848f;font-size:.82rem;line-height:1.9;margin-bottom:13px;}
    .contact-footer {border-top:1px solid #edf0f3;padding-top:11px;color:#8b969e;font-size:.73rem;margin-top:10px;}
    .placeholder {height:160px;background:linear-gradient(130deg,#f6e5d9,#f9f2e8);display:flex;align-items:center;justify-content:center;font-size:3rem;border-radius:11px;margin-bottom:15px;}
    .tag {background:#fff0e8;color:#bd654e;font-size:.7rem;font-weight:700;border-radius:6px;padding:4px 9px;}
    .wizard-steps {display:flex;gap:10px;margin:5px 0 27px;}
    .wizard-step {flex:1;border-radius:9px;padding:13px;background:#e9edf0;color:#8c98a1;font-size:.81rem;font-weight:600;}
    .wizard-step.active {background:#fff0e9;color:#c4664b;box-shadow:inset 0 0 0 1px #efd3c7;}
    .wizard-step.done {background:#e8f3ed;color:#41846a;}
    .wizard-step b {border-radius:50%;padding:3px 7px;background:#ffffffa0;margin-right:8px;font-size:.73rem;}
    .summary-top {display:flex;justify-content:space-between;align-items:center;color:#2d4856;font-weight:700;margin-bottom:18px;}
    .summary-row {display:flex;justify-content:space-between;gap:12px;padding:7px 0;color:#7c8b95;font-size:.83rem;}
    .summary-row strong {color:#314b58;font-weight:600;}
    .summary-total {background:#203d49;border-radius:11px;color:#fff;padding:20px;margin:17px 0 10px;}
    .summary-total small {color:#b6ccd3;font-size:.76rem;display:block;}
    .summary-total b {font-size:1.9rem;letter-spacing:-.04em;display:block;margin-top:5px;}
    .summary-deposit {font-size:.76rem;color:#78918d;background:#edf6f1;border-radius:8px;padding:12px;}
    .empty-state {border:1px dashed #dce3e7;background:#fff;border-radius:14px;text-align:center;padding:35px 20px;color:#81929e;margin:10px 0;}
    .empty-state strong {display:block;color:#39515e;margin:8px;font-size:1rem;}
    .detail-label {font-size:.66rem;text-transform:uppercase;letter-spacing:.08em;color:#95a1aa;margin-bottom:5px;}
    .detail-value {font-size:.88rem;color:#334e5c;margin-bottom:17px;white-space:pre-wrap;overflow-wrap:anywhere;}
    .data-table {width:100%;border-collapse:collapse;font-size:.83rem;background:#fff;border-radius:10px;overflow:hidden;}
    .data-table th {background:#f0f3f5;text-align:left;padding:12px;color:#7c8c96;font-size:.72rem;font-weight:600;}
    .data-table td {padding:13px 12px;color:#3f5663;border-bottom:1px solid #edf1f3;}
    .media-frame {width:100%;height:170px;background:#faf4ee;border-radius:11px;overflow:hidden;display:flex;align-items:center;justify-content:center;margin-bottom:12px;}
    .media-frame img {width:100%;height:100%;object-fit:contain;display:block;}
    .st-key-mobile_navigation {display:none;}
    @media(max-width:850px) {
      .st-key-mobile_navigation {display:block;}
      [class*="st-key-metrics_"] [data-testid="stHorizontalBlock"] {flex-wrap:wrap;gap:10px;}
      [class*="st-key-metrics_"] [data-testid="stColumn"] {flex:1 1 calc(50% - 10px)!important;min-width:0!important;}
      .st-key-metrics_customers [data-testid="stColumn"] {flex-basis:calc(33.33% - 10px)!important;}
      [class*="st-key-metrics_"] [data-testid="stMetric"] {padding:12px;min-height:104px;}
      [class*="st-key-metrics_"] [data-testid="stMetricValue"] {font-size:1.25rem;}
      [class*="st-key-metrics_"] [data-testid="stMetricLabel"] p {font-size:.68rem;}
      .st-key-customer_sheet {overflow-x:auto;}
      .st-key-customer_sheet [data-testid="stHorizontalBlock"] {flex-wrap:nowrap;min-width:980px;}
      .st-key-customer_sheet [data-testid="stColumn"] {flex:1 1 0!important;min-width:0!important;}
      .st-key-customer_sheet [data-testid="stColumn"]:first-child {flex:2.8 1 0!important;}
      .st-key-customer_sheet [data-testid="stColumn"]:nth-child(2) {flex:1.6 1 0!important;}
      .st-key-customer_sheet [data-testid="stColumn"]:nth-child(3) {flex:2.1 1 0!important;}
      .st-key-customer_sheet [data-testid="stColumn"]:nth-child(4) {flex:1.4 1 0!important;}
    }
    [class*="st-key-customer_row_"], [class*="st-key-order_row_"] {background:white;border-bottom:1px solid #e5e9ed;padding:9px 12px;}
    [class*="st-key-customer_row_"] .profile-heading {margin:0;gap:9px;}
    [class*="st-key-customer_row_"] .avatar {width:34px;height:34px;font-size:12px;}
    [class*="st-key-customer_row_"] .profile-heading strong {font-size:.83rem;}
    [class*="st-key-customer_row_"] .profile-heading small {font-size:.69rem;margin-top:2px;}
    [class*="st-key-customer_row_"] p, [class*="st-key-order_row_"] p {font-size:.79rem;overflow-wrap:anywhere;}
    [class*="st-key-customer_row_"] button {font-size:.73rem;min-height:32px;padding:4px 7px;}
    [data-testid="stFileUploaderDropzoneInstructions"] {font-size:0!important;}
    [data-testid="stFileUploaderDropzoneInstructions"]>div,[data-testid="stFileUploaderDropzoneInstructions"] span,[data-testid="stFileUploaderDropzoneInstructions"] small {display:none!important;}
    [data-testid="stFileUploaderDropzoneInstructions"]:after {content:'Arraste uma imagem aqui';font-size:12px;color:#80919c;}
    [data-testid="stFileUploaderDropzone"] button {font-size:0!important;}
    [data-testid="stFileUploaderDropzone"] button:after {content:'Escolher arquivo';font-size:12px;}
    [data-testid="stFileUploaderDropzone"] {padding:13px;border:1px dashed #d8e1e6;background:#fafcfd;border-radius:10px;}
    [data-testid="stMain"] [role="radiogroup"] {gap:7px;}
    [data-testid="stMain"] [role="radiogroup"]>label {border:1px solid #e0e6e9;background:#fff;border-radius:8px;padding:7px 11px;}
    [data-testid="stMain"] [role="radiogroup"]>label:has(input:checked) {border-color:#e8b39f;background:#fff1ea;}
    @media(max-width:850px) {.block-container{padding:1.5rem 1rem;} .wizard-steps{gap:4px;} .wizard-step{padding:10px 5px;font-size:.7rem;} .wizard-step b{margin-right:3px;} h1{font-size:1.65rem!important;} [class*="st-key-customer_row_"] [data-testid="stHorizontalBlock"], [class*="st-key-order_row_"] [data-testid="stHorizontalBlock"] {gap:6px;} .data-table {display:block;overflow-x:auto;} input,textarea {font-size:16px!important;} }
    @media print {[data-testid="stSidebar"] {display:none;}}
    </style>""", unsafe_allow_html=True)


def heading(label, title, subtitle=""):
    st.markdown(f'<div class="hero"><div class="eyebrow">{escape(label)}</div><h1>{escape(title)}</h1><p>{escape(subtitle)}</p></div>', unsafe_allow_html=True)


@st.cache_data(max_entries=120, show_spinner=False)
def _thumbnail(path, modified):
    from io import BytesIO
    from PIL import Image, ImageOps
    with Image.open(path) as original:
        thumb = ImageOps.exif_transpose(original).convert("RGBA")
        thumb.thumbnail((700, 420))
        output = BytesIO()
        thumb.save(output, "PNG")
    return base64.b64encode(output.getvalue()).decode()


def media_thumbnail(name, store, height=170, label="Foto do produto"):
    path = store.image_path(name)
    if path:
        encoded = _thumbnail(str(path), path.stat().st_mtime_ns)
        content = f'<img alt="{escape(label, quote=True)}" src="data:image/png;base64,{encoded}">'
    else:
        content = '<span aria-label="Sem foto cadastrada" style="font-size:2rem">🧁</span>'
    st.markdown(f'<div class="media-frame" style="height:{int(height)}px">{content}</div>', unsafe_allow_html=True)


def avatar_html(customer, store):
    photo = store.image_path(customer.get("photo", ""))
    if photo:
        from io import BytesIO
        from PIL import Image, ImageOps
        with Image.open(photo) as original:
            thumb = ImageOps.fit(original.convert("RGB"), (108, 108))
            output = BytesIO()
            thumb.save(output, "JPEG", quality=80)
        encoded = base64.b64encode(output.getvalue()).decode()
        return f'<img class="avatar" alt="Foto do cliente" src="data:image/jpeg;base64,{encoded}">'
    initials = "".join(part[0] for part in customer.get("name", "Cliente").split()[:2])
    return f'<div class="avatar">{escape(initials.upper())}</div>'


def profile_heading(customer, store, subtitle=None):
    st.markdown(f'<div class="profile-heading">{avatar_html(customer, store)}<div><strong>{escape(customer["name"])}</strong><small>{escape(subtitle or phone_text(customer.get("phone", "")))}</small></div></div>', unsafe_allow_html=True)


def phone_text(number):
    country = "+55 " if len(number) in (12, 13) and number.startswith("55") else ""
    digits = number[2:] if country else number
    if len(digits) in (10, 11):
        return f"{country}({digits[:2]}) {digits[2:-4]}-{digits[-4:]}"
    return number


def contact_line(kind, text):
    paths = {"phone": '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7l.5 3a2 2 0 0 1-.6 2.1L7.7 10a16 16 0 0 0 6 6l1.2-1.3a2 2 0 0 1 2.1-.6l3 .5a2 2 0 0 1 2 2.3z"/>',
             "mail": '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m2 5 10 8L22 5"/>',
             "place": '<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>'}
    return f'<span style="display:flex;align-items:center;gap:8px"><svg aria-hidden="true" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#91a0aa" stroke-width="1.7">{paths[kind]}</svg>{escape(text)}</span>'


def empty_state(title, text, icon="✦"):
    st.markdown(f'<div class="empty-state">{escape(icon)}<strong>{escape(title)}</strong>{escape(text)}</div>', unsafe_allow_html=True)


def detail(label, value):
    st.markdown(f'<div class="detail-label">{escape(label)}</div><div class="detail-value">{escape(str(value or "Não informado"))}</div>', unsafe_allow_html=True)


def table(rows):
    if not rows:
        return
    headers = list(rows[0])
    html = '<table class="data-table"><thead><tr>' + "".join(f"<th>{escape(h)}</th>" for h in headers) + "</tr></thead><tbody>"
    for row in rows:
        html += "<tr>" + "".join(f"<td>{escape(str(row.get(h, '')))}</td>" for h in headers) + "</tr>"
    st.markdown(html + "</tbody></table>", unsafe_allow_html=True)


def date_field(label, value, key, picker=True):
    text_key = key + "_text"
    if not picker:
        from datetime import datetime
        st.session_state.setdefault(text_key, value.strftime("%d/%m/%Y"))
        text = st.text_input(label, key=text_key, placeholder="DD/MM/AAAA", max_chars=10)
        try:
            return datetime.strptime(text, "%d/%m/%Y").date()
        except ValueError:
            return None
    a, b = st.columns([5, 1], vertical_alignment="bottom")
    st.session_state.setdefault(text_key, value.strftime("%d/%m/%Y"))
    text = a.text_input(label, key=text_key, placeholder="DD/MM/AAAA", max_chars=10)
    try:
        from datetime import datetime
        selected = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        selected = value
        a.caption("Use o formato DD/MM/AAAA.")
    with b.popover("", icon=":material/calendar_month:", help="Abrir calendário"):
        c1, c2 = st.columns([2, 1])
        if st.session_state.get(text_key + "_synced") != text:
            st.session_state[key + "_month"] = selected.month
            st.session_state[key + "_year"] = selected.year
            st.session_state[text_key + "_synced"] = text
        month = c1.selectbox("Mês", list(range(1, 13)), format_func=lambda m: MONTHS[m - 1], key=key + "_month")
        years = list(range(min(selected.year, date.today().year - 5), max(selected.year, date.today().year + 10) + 1))
        year = c2.selectbox("Ano", years, key=key + "_year")
        for col, day in zip(st.columns(7), ["S", "T", "Q", "Q", "S", "S", "D"]):
            col.caption(day)
        for week in calendar.Calendar().monthdayscalendar(year, month):
            for col, day in zip(st.columns(7), week):
                if day:
                    def select_day(d=date(year, month, day)):
                        st.session_state[text_key] = d.strftime("%d/%m/%Y")
                    col.button(str(day), key=f"{key}_{year}_{month}_{day}", on_click=select_day, width="stretch")
    try:
        from datetime import datetime
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def stepper(step):
    html = '<div class="wizard-steps">'
    for i, title in enumerate(["Cliente", "Produtos", "Pagamento", "Revisão"]):
        state = "active" if i == step else "done" if i < step else ""
        html += f'<div class="wizard-step {state}"><b>{"✓" if i < step else i + 1}</b>{title}</div>'
    st.markdown(html + "</div>", unsafe_allow_html=True)


def quote_summary(draft, totals):
    with st.container(border=True, key="card_quote_summary"):
        st.markdown('<div class="summary-top">Resumo do orçamento <span class="badge gray">RASCUNHO</span></div>', unsafe_allow_html=True)
        lines = draft.get("lines", [])
        if not lines:
            st.caption("Seus produtos aparecerão aqui.")
        for line in lines:
            suffix = " · BRINDE" if line["gift"] else ""
            st.markdown(f'<div class="summary-row"><span>{escape(line["name"] + suffix)}<br><small>{escape(str(line["quantity"]).replace(".", ","))} {escape(line["unit"])}</small></span><strong>{brl(line["total_cents"])}</strong></div>', unsafe_allow_html=True)
        st.divider()
        for label, value in [("Subtotal", totals["subtotal_cents"]), ("Desconto geral", -totals["discount_cents"]), ("Desconto PIX / Dinheiro", -totals["pix_discount_cents"]), ("Entrega", totals["delivery_cents"])]:
            st.markdown(f'<div class="summary-row"><span>{label}</span><strong>{brl(value)}</strong></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="summary-total"><small>Total do pedido</small><b>{brl(totals["total_cents"])}</b></div><div class="summary-deposit">Sinal para reservar a data <strong>{brl(totals["deposit_cents"])}</strong></div>', unsafe_allow_html=True)
        st.caption("A reserva é confirmada após o recebimento de pelo menos 50%.")
