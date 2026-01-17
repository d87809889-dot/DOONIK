import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re
from datetime import datetime

from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from supabase import create_client


# ==========================================
# 1) CONFIG
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# THEME SWITCH (ALTERNATIV)
# =========================
THEME = "DARK_GOLD"  # "DARK_GOLD" | "PARCHMENT" | "MIDNIGHT"
THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#10182b",
        "sidebar_bg": "#0c1421",
        "text": "#e9eefb",
        "muted": "#b9c2d4",
        "gold": "#c5a059",
        "gold2": "#d4af37",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "PARCHMENT": {
        "app_bg": "#f4ecd8",
        "surface": "#fff7e6",
        "sidebar_bg": "#0c1421",
        "text": "#0c1421",
        "muted": "#3b4252",
        "gold": "#b98a2c",
        "gold2": "#c5a059",
        "card": "#ffffff",
        "card_text": "#111827",
    },
    "MIDNIGHT": {
        "app_bg": "#070b16",
        "surface": "#0e1630",
        "sidebar_bg": "#0b1020",
        "text": "#e6ecff",
        "muted": "#aab6d6",
        "gold": "#5aa6ff",
        "gold2": "#7cc4ff",
        "card": "#ffffff",
        "card_text": "#111827",
    },
}
C = THEMES.get(THEME, THEMES["DARK_GOLD"])


# ==========================================
# 2) CSS (Pro + Fix + Diagnosis highlight)
# ==========================================
st.markdown(f"""
<style>
:root {{
  --app-bg: {C["app_bg"]};
  --surface: {C["surface"]};
  --sidebar-bg: {C["sidebar_bg"]};
  --text: {C["text"]};
  --muted: {C["muted"]};
  --gold: {C["gold"]};
  --gold2: {C["gold2"]};
}}

html, body {{
  background: var(--app-bg) !important;
  margin: 0 !important;
  padding: 0 !important;
}}
.stApp, div[data-testid="stAppViewContainer"] {{
  background: var(--app-bg) !important;
  min-height: 100vh !important;
}}
div[data-testid="stAppViewContainer"] .main .block-container {{
  padding-top: 3.25rem !important;
  padding-bottom: 1.25rem !important;
}}

footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}

section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid var(--gold) !important;
}}
section[data-testid="stSidebar"] * {{ color: var(--text) !important; }}
section[data-testid="stSidebar"] .stCaption {{ color: var(--muted) !important; }}

h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
  text-shadow: 0 1px 1px rgba(0,0,0,0.35);
}}
.stMarkdown p {{ color: var(--muted) !important; }}

.stButton>button {{
  background: linear-gradient(135deg, var(--sidebar-bg) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 800 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid var(--gold) !important;
  border-radius: 12px !important;
  box-shadow: 0 10px 22px rgba(0,0,0,0.25) !important;
  transition: transform .15s ease, filter .2s ease, box-shadow .2s ease !important;
}}
.stButton>button:hover {{
  transform: translateY(-1px);
  filter: brightness(1.08);
  box-shadow: 0 14px 28px rgba(0,0,0,0.32) !important;
}}

.stTextInput input, .stSelectbox select {{
  background-color: rgba(255,255,255,0.06) !important;
  color: var(--text) !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.stTextArea textarea {{
  background-color: #fdfaf1 !important;
  color: #000000 !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 10px !important;
}}

.premium-alert {{
  background: rgba(255,243,224,1);
  border: 1px solid #ffb74d;
  padding: 12px;
  border-radius: 12px;
  text-align: center;
  color: #e65100;
  font-weight: 800;
  margin-bottom: 12px;
}}

.chat-user {{
  background-color: #e2e8f0; color: #000; padding: 10px; border-radius: 10px;
  border-left: 5px solid #1e3a8a; margin-bottom: 6px;
}}
.chat-ai {{
  background-color: #ffffff; color: #1a1a1a; padding: 10px; border-radius: 10px;
  border: 1px solid #d4af37; margin-bottom: 14px;
}}

.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 14px;
  border: 2px solid var(--gold);
  overflow: hidden;
  box-shadow: 0 14px 35px rgba(0,0,0,0.22);
  background: rgba(0,0,0,0.15);
  max-height: 540px;
  animation: fadeUp .35s ease both;
}}
.sticky-preview img {{
  width: 100%;
  height: 540px;
  object-fit: contain;
  display: block;
  transition: transform .25s ease;
}}
.sticky-preview:hover img {{
  transform: scale(1.45);
  transform-origin: center;
  cursor: zoom-in;
}}
@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
@media (prefers-reduced-motion: reduce) {{
  * {{ animation: none !important; transition: none !important; }}
}}
@media (max-width: 768px) {{
  div[data-testid="stAppViewContainer"] .main .block-container {{
    padding-top: 3.5rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }}
  .sticky-preview {{ position: relative; top: 0; max-height: 48vh; }}
  .sticky-preview img {{ height: 48vh; }}
}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 3) SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name="gemini-flash-latest")  # o'zgarmaydi


# ==========================================
# 4) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"
if "last_fn" not in st.session_state: st.session_state.last_fn = None

if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "warn_rpc" not in st.session_state: st.session_state.warn_rpc = False


# ==========================================
# 5) HELPERS
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = 88, max_side: int = 2400) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    long_side = max(w, h)
    if long_side > max_side:
        ratio = max_side / float(long_side)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()

@st.cache_data(show_spinner=False, max_entries=12)
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float) -> list[bytes]:
    pdf = pdfium.PdfDocument(file_bytes)
    out: list[bytes] = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, quality=86, max_side=2600))
    finally:
        try:
            pdf.close()
        except Exception:
            pass
    return out

@st.cache_data(show_spinner=False, max_entries=64)
def preprocess_bytes(img_bytes: bytes, brightness: float, contrast: float, rotate: int) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(rotate, expand=True)
    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    return pil_to_jpeg_bytes(img, quality=90, max_side=2400)

def parse_pages(spec: str, max_n: int) -> list[int]:
    spec = (spec or "").strip()
    if not spec:
        return [0] if max_n > 0 else []
    out = set()
    parts = [p.strip() for p in spec.split(",") if p.strip()]
    for part in parts:
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                a = int(a.strip()); b = int(b.strip())
                if a > b: a, b = b, a
                for p in range(a, b + 1):
                    if 1 <= p <= max_n:
                        out.add(p - 1)
            else:
                p = int(part)
                if 1 <= p <= max_n:
                    out.add(p - 1)
        except Exception:
            continue
    return sorted(out) if out else ([0] if max_n > 0 else [])

def call_gemini_with_retry(prompt: str, payload: dict, tries: int = 4) -> str:
    last_err = None
    for i in range(tries):
        try:
            resp = model.generate_content([prompt, payload])
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if ("429" in msg) or ("rate" in msg) or ("quota" in msg) or ("resource" in msg):
                time.sleep((2 ** i) + random.random())
                continue
            raise
    raise RuntimeError("Juda ko'p so'rov (429). Birozdan keyin qayta urinib ko'ring.") from last_err

def reserve_credit(email: str) -> bool:
    try:
        r = db.rpc("consume_credits", {"p_email": email, "p_n": 1}).execute()
        return bool(r.data)
    except Exception:
        st.session_state.warn_rpc = True
        return False

def refund_credit(email: str) -> None:
    try:
        db.rpc("refund_credits", {"p_email": email, "p_n": 1}).execute()
    except Exception:
        pass


# ==========================================
# 6) RESULT RENDER (with Diagnosis highlight)
# ==========================================
def _is_md_table_sep(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    core = s.strip("|").strip()
    return all(ch in "-: |" for ch in core) and ("-" in core)

def _badge(conf: str) -> str:
    conf_l = (conf or "").lower()
    if "yuqori" in conf_l:
        cls = "b-high"
        label = "Yuqori ishonch"
    elif "o‘rtacha" in conf_l or "ortacha" in conf_l:
        cls = "b-med"
        label = "O‘rtacha ishonch"
    else:
        cls = "b-low"
        label = "Past ishonch"
    return f'<span class="badge {cls}">{html.escape(label)}</span>'

def _extract_conf(md: str) -> str:
    # tries to find "Ishonchlilik: ..."
    m = re.search(r"Ishonchlilik\s*:\s*(.+)", md, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""

def md_to_html_basic(md: str) -> str:
    """
    Minimal MD -> HTML, plus: if it sees a "0) Tashxis:" block at start, it wraps it in a highlight box.
    """
    raw = md or ""
    conf = _extract_conf(raw)

    safe = html.escape(raw)
    lines = safe.splitlines()

    out = []
    i = 0
    para = []
    items = []

    def flush_paragraph():
        nonlocal para
        if para:
            out.append("<p>" + "<br/>".join(para) + "</p>")
            para = []

    def flush_list():
        nonlocal items
        if items:
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            items = []

    # detect diagnosis header line
    def is_diag(line: str) -> bool:
        return line.strip().lower().startswith("0)") and "tashxis" in line.strip().lower()

    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip() == "":
            flush_paragraph(); flush_list()
            i += 1
            continue

        if line.strip() == "---":
            flush_paragraph(); flush_list()
            out.append("<hr/>")
            i += 1
            continue

        # DIAGNOSIS highlight block (0) Tashxis...)
        if is_diag(line):
            flush_paragraph(); flush_list()
            diag_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip() != "" and not re.match(r"^\d+\)\s+", lines[i].strip()):
                diag_lines.append(lines[i].rstrip())
                i += 1

            badge = _badge(conf)
            diag_html = "<br/>".join(diag_lines)
            out.append(f"""
              <div class="diag-box">
                <div class="diag-head">
                  <span class="diag-title">0) Tashxis</span>
                  {badge}
                </div>
                <div class="diag-body">{diag_html}</div>
              </div>
            """)
            continue

        if line.startswith("### "):
            flush_paragraph(); flush_list()
            out.append(f"<h3>{line[4:]}</h3>")
            i += 1
            continue
        if line.startswith("## "):
            flush_paragraph(); flush_list()
            out.append(f"<h2>{line[3:]}</h2>")
            i += 1
            continue

        if re.match(r"^\d+\)\s+", line.strip()):
            flush_paragraph(); flush_list()
            out.append(f"<h3>{line.strip()}</h3>")
            i += 1
            continue

        if line.strip().startswith("- "):
            flush_paragraph()
            items.append(line.strip()[2:])
            i += 1
            continue

        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            flush_paragraph(); flush_list()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1

            cleaned = []
            for tl in table_lines:
                if _is_md_table_sep(tl):
                    continue
                cleaned.append(tl)

            rows = []
            for tl in cleaned:
                cells = [c.strip() for c in tl.strip("|").split("|")]
                rows.append(cells)

            if rows:
                header = rows[0]
                body = rows[1:]
                out.append("<table>")
                out.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in header) + "</tr></thead>")
                out.append("<tbody>")
                for r in body:
                    out.append("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>")
                out.append("</tbody></table>")
            continue

        line = line.replace("**", "§§B§§")
        parts = line.split("§§B§§")
        if len(parts) > 1:
            rebuilt = []
            for j, p in enumerate(parts):
                rebuilt.append(f"<strong>{p}</strong>" if j % 2 == 1 else p)
            line = "".join(rebuilt)

        para.append(line)
        i += 1

    flush_paragraph(); flush_list()
    return "\n".join(out)

def render_result_card(md: str, gold: str) -> str:
    body = md_to_html_basic(md)
    return f"""
    <style>
      :root {{ --gold: {gold}; }}
      body {{
        margin: 0;
        font-family: Georgia, 'Times New Roman', serif;
        color: #111827;
        background: #ffffff;
      }}
      .card {{
        padding: 18px;
        border-left: 10px solid var(--gold);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        line-height: 1.75;
        animation: fadeUp .25s ease both;
      }}
      @keyframes fadeUp {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
      }}
      h2, h3 {{
        margin: 0 0 10px 0;
        color: var(--gold);
        border-bottom: 2px solid var(--gold);
        padding-bottom: 8px;
      }}

      .diag-box {{
        border: 1px solid rgba(17, 24, 39, 0.10);
        background: linear-gradient(180deg, rgba(197,160,89,0.14), rgba(197,160,89,0.06));
        border-radius: 14px;
        padding: 12px 12px;
        margin: 6px 0 14px 0;
      }}
      .diag-head {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 8px;
      }}
      .diag-title {{
        font-weight: 900;
        color: #1f2937;
      }}
      .badge {{
        font-size: 12px;
        font-weight: 900;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid rgba(0,0,0,0.08);
        box-shadow: 0 6px 14px rgba(0,0,0,0.08);
        white-space: nowrap;
      }}
      .b-high {{ background: #dcfce7; color: #14532d; }}
      .b-med  {{ background: #fef9c3; color: #713f12; }}
      .b-low  {{ background: #fee2e2; color: #7f1d1d; }}

      table {{
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        font-size: 14px;
      }}
      th, td {{
        border: 1px solid #e5e7eb;
        padding: 8px 10px;
        vertical-align: top;
      }}
      th {{ background: #f8fafc; }}
      hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 14px 0; }}
      p {{ margin: 10px 0; }}
      ul {{ margin: 10px 0 10px 18px; }}
    </style>
    <div class="card">
      {body}
    </div>
    """


# ==========================================
# 7) WORD EXPORT (same as before, no "Model" row)
# ==========================================
def _doc_set_normal_style(doc: Document):
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

def _add_cover(doc: Document, title: str, subtitle: str):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title)
    run.bold = True
    run.font.size = Pt(20)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(subtitle)
    run2.font.size = Pt(12)

    doc.add_paragraph("")

def _add_meta_table(doc: Document, meta: dict):
    t = doc.add_table(rows=0, cols=2)
    t.style = "Table Grid"
    for k, v in meta.items():
        row = t.add_row().cells
        row[0].text = str(k)
        row[1].text = str(v)

def _is_md_table_sep_plain(line: str) -> bool:
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return False
    core = s.strip("|").strip()
    return all(ch in "-: |" for ch in core) and ("-" in core)

def _parse_md_table(lines: list[str], start_i: int):
    table_lines = []
    i = start_i
    while i < len(lines) and lines[i].strip().startswith("|"):
        table_lines.append(lines[i].strip())
        i += 1

    cleaned = []
    for tl in table_lines:
        if _is_md_table_sep_plain(tl):
            continue
        cleaned.append(tl)

    rows = []
    for tl in cleaned:
        cells = [c.strip() for c in tl.strip("|").split("|")]
        rows.append(cells)

    return rows, i

def add_md_content_to_doc(doc: Document, md: str):
    md = md or ""
    lines = md.splitlines()
    i = 0
    buf = []

    def flush_buf():
        nonlocal buf
        if buf:
            p = doc.add_paragraph()
            for j, ln in enumerate(buf):
                p.add_run(ln)
                if j != len(buf) - 1:
                    p.add_run("\n")
            buf = []

    def add_hr():
        doc.add_paragraph("—" * 36)

    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip() == "":
            flush_buf()
            doc.add_paragraph("")
            i += 1
            continue

        if line.strip() == "---":
            flush_buf()
            add_hr()
            i += 1
            continue

        if line.startswith("## "):
            flush_buf()
            doc.add_heading(line[3:], level=2)
            i += 1
            continue

        if line.startswith("### "):
            flush_buf()
            doc.add_heading(line[4:], level=3)
            i += 1
            continue

        if re.match(r"^\d+\)\s+", line.strip()):
            flush_buf()
            doc.add_heading(line.strip(), level=3)
            i += 1
            continue

        if line.strip().startswith("|") and "|" in line.strip()[1:]:
            flush_buf()
            rows, nxt = _parse_md_table(lines, i)
            i = nxt
            if rows:
                cols = max(len(r) for r in rows)
                table = doc.add_table(rows=len(rows), cols=cols)
                table.style = "Table Grid"
                for r_i, r in enumerate(rows):
                    for c_i in range(cols):
                        table.cell(r_i, c_i).text = r[c_i] if c_i < len(r) else ""
            doc.add_paragraph("")
            continue

        if line.strip().startswith("- "):
            flush_buf()
            doc.add_paragraph(line.strip()[2:], style="List Bullet")
            i += 1
            continue

        buf.append(line)
        i += 1

    flush_buf()

def build_word_report(app_name: str, meta: dict, pages: dict[int, str]) -> bytes:
    doc = Document()
    _doc_set_normal_style(doc)

    _add_cover(
        doc,
        app_name,
        "Akademik hisobot (AI tahlil + transliteratsiya + tarjima + izoh)"
    )
    _add_meta_table(doc, meta)
    doc.add_page_break()

    page_keys = sorted(pages.keys())
    for j, idx in enumerate(page_keys):
        doc.add_heading(f"Varaq {idx+1}", level=1)
        add_md_content_to_doc(doc, pages[idx] or "")
        if j != len(page_keys) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ==========================================
# 8) SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kreditlardan foydalanish uchun kiring.")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")

        if st.button("KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = (email_in or "demo@mail.com").strip()
                try:
                    db.table("profiles").insert({"email": st.session_state.u_email, "credits": 10}).execute()
                except Exception:
                    pass
                st.rerun()
            else:
                st.error("Xato parol!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        try:
            res = db.table("profiles").select("credits").eq("email", st.session_state.u_email).single().execute()
            live_credits = int(res.data["credits"]) if res.data else 0
        except Exception:
            live_credits = 0

        st.metric("💳 Kreditlar", f"{live_credits} sahifa")

        if st.session_state.warn_rpc:
            st.warning("RPC muammo: consume_credits/refund_credits ishlamayapti.")

        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()

    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (ixtiyoriy):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (ixtiyoriy):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Laboratoriya")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

    scale = st.slider("PDF render scale:", 1.5, 3.8, 2.2, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

    st.markdown("### 🧭 Ko'rinish")
    view_mode = st.radio("Natija ko'rinishi:", ["Yonma-yon", "Tabs"], index=0, horizontal=True)


# ==========================================
# 9) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Faylni yuklang",
    type=["pdf", "png", "jpg", "jpeg"],
    label_visibility="collapsed"
)

if uploaded_file:
    if st.session_state.last_fn != uploaded_file.name:
        with st.spinner("Preparing..."):
            file_bytes = uploaded_file.getvalue()
            if uploaded_file.type == "application/pdf":
                pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
            else:
                img = Image.open(io.BytesIO(file_bytes))
                pages = [pil_to_jpeg_bytes(img, quality=90, max_side=2600)]

            st.session_state.page_bytes = pages
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            st.session_state.warn_rpc = False
            gc.collect()

    processed_pages = [
        preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate)
        for b in st.session_state.page_bytes
    ]

    total_pages = len(processed_pages)
    st.caption(f"Yuklandi: **{total_pages}** sahifa (preview limit: {max_pages}).")

    if total_pages <= 30:
        selected_indices = st.multiselect(
            "Sahifalarni tanlang:",
            options=list(range(total_pages)),
            default=[0] if total_pages else [],
            format_func=lambda x: f"{x+1}-sahifa"
        )
        page_spec = st.text_input("Range (masalan: 1-3, 7, 10-12):", value="1")
        if st.button("Range bo'yicha tanlash"):
            selected_indices = parse_pages(page_spec, total_pages)
    else:
        page_spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
        selected_indices = parse_pages(page_spec, total_pages)
        st.caption("Maslahat: juda ko'p sahifani biryo'la yubormang (429 kamayadi).")

    if not st.session_state.results and selected_indices:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices[:16]):
            with cols[i % min(len(cols), 4)]:
                st.image(processed_pages[idx], caption=f"Varaq {idx+1}", use_container_width=True)
        if len(selected_indices) > 16:
            st.info(f"Previewda faqat 16 ta ko'rsatildi. Tanlangan jami: {len(selected_indices)}.")

    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
        hint_era = "" if (auto_detect or era == "Noma'lum") else era

        # ✅ PRO: confidence bandini majburiy qilamiz
        prompt = (
            "Siz Manuscript AI mutaxassisiz.\n"
            "MUHIM: Foydalanuvchi tanlovi faqat HINT bo‘lishi mumkin. Uni haqiqat deb qabul qilmang.\n"
            "Avval rasmga qarab MUSTAQIL aniqlang: til va xat uslubi, va hint bilan mos/mos emas.\n\n"
            f"Foydalanuvchi hintlari: til='{hint_lang or 'yo‘q'}', xat='{hint_era or 'yo‘q'}'.\n\n"
            "Format (aniq shunday):\n"
            "0) Tashxis: aniqlangan til + xat uslubi + (hint mos/mos emas) + qisqa sabab\n"
            "   Ishonchlilik: past | o‘rtacha | yuqori (bittasini tanlang)\n"
            "1) Paleografiya\n"
            "2) Transliteratsiya (satrma-satr, o‘qilganicha)\n"
            "3) Tarjima (akademik, mazmuniy)\n"
            "4) Arxaik lug'at (5–10 so‘z)\n"
            "5) Izoh (kontekst, shaxs/joy/sana bo‘lsa ehtiyot bilan)\n\n"
            "Qoidalar:\n"
            "- O‘qilmagan joyni taxmin qilmang: [o‘qilmadi] yoki [?] bilan belgilang.\n"
            "- Ism/son/sana bo‘lsa aynan ko‘ringanicha yozing (tasdiqsiz uydirma qilmang).\n"
            "- Hech qachon inglizcha label ishlatma. Faqat o‘zbekcha yoz.\n"
        )

        for idx in selected_indices:
            reserved = False
            with st.status(f"Sahifa {idx+1}...") as s:
                try:
                    if st.session_state.auth:
                        ok = reserve_credit(st.session_state.u_email)
                        if not ok:
                            st.warning("Kredit tugagan. Davom etish uchun kredit qo‘shing.")
                            s.update(label="Kredit yetarli emas", state="error")
                            continue
                        reserved = True

                    img_bytes = processed_pages[idx]
                    payload = {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}
                    text = call_gemini_with_retry(prompt, payload, tries=4)

                    if not text.strip():
                        if reserved:
                            refund_credit(st.session_state.u_email)
                        s.update(label="Bo‘sh natija (refund)", state="error")
                        st.error("AI bo‘sh natija qaytardi. Qayta urinib ko‘ring.")
                        continue

                    st.session_state.results[idx] = text
                    s.update(label="Tayyor!", state="complete")

                except Exception as e:
                    if reserved:
                        refund_credit(st.session_state.u_email)
                    st.error(f"Xato: {e}")
                    s.update(label="Xato (refund)", state="error")

        gc.collect()
        st.rerun()

    if st.session_state.results:
        st.divider()
        keys = sorted(st.session_state.results.keys())

        for idx in keys:
            with st.expander(f"📖 Varaq {idx+1}", expanded=(idx == keys[0])):
                res = st.session_state.results[idx] or ""

                img_b64 = base64.b64encode(processed_pages[idx]).decode("utf-8")
                img_html = f"""
                <div class="sticky-preview">
                  <img src="data:image/jpeg;base64,{img_b64}" alt="page {idx+1}" />
                </div>
                """

                if view_mode == "Tabs":
                    tabs = st.tabs(["📷 Rasm", "📝 Natija", "✍️ Tahrir", "💬 Chat"])
                    with tabs[0]:
                        st.markdown(img_html, unsafe_allow_html=True)
                    with tabs[1]:
                        components.html(render_result_card(res, C["gold"]), height=580, scrolling=True)
                    with tabs[2]:
                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Tahrir/Word/Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=260,
                                key=f"ed_{idx}"
                            )
                    with tabs[3]:
                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.chats.setdefault(idx, [])
                            for ch in st.session_state.chats[idx]:
                                st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)
                            user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                            if st.button(f"So'rash ({idx+1})", key=f"btn_{idx}"):
                                if user_q.strip():
                                    with st.spinner("..."):
                                        chat_prompt = f"Doc: {st.session_state.results[idx]}\nQ: {user_q}"
                                        chat_resp = model.generate_content([chat_prompt])
                                        st.session_state.chats[idx].append({"q": user_q, "a": getattr(chat_resp, "text", "") or ""})
                                        st.rerun()
                else:
                    c1, c2 = st.columns([1, 1.35], gap="large")
                    with c1:
                        st.markdown(img_html, unsafe_allow_html=True)
                    with c2:
                        components.html(render_result_card(res, C["gold"]), height=580, scrolling=True)

                        if not st.session_state.auth:
                            st.markdown("<div class='premium-alert'>🔒 Tahrir/Word/Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=280,
                                key=f"ed_{idx}"
                            )

        if st.session_state.auth and st.session_state.results:
            meta = {
                "Hujjat nomi": st.session_state.last_fn,
                "Til (hint)": lang,
                "Xat uslubi (hint)": era,
                "Avto aniqlash": "Ha" if auto_detect else "Yo‘q",
                "Eksport qilingan sahifalar": ", ".join(str(i+1) for i in sorted(st.session_state.results.keys())),
                "Yaratilgan vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
            report_bytes = build_word_report("Manuscript AI", meta, st.session_state.results)
            st.download_button("📥 WORD HISOBOTNI YUKLAB OLISH (.docx)", report_bytes, file_name="Manuscript_AI_Report.docx")

gc.collect()

