import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re
from datetime import datetime
from collections import Counter

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
    initial_sidebar_state="expanded"
)

# ==========================================
# 2) THEME
# ==========================================
THEME = "DARK_GOLD"

THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#10182b",
        "sidebar_bg": "#0c1421",
        "text": "#eaf0ff",
        "muted": "#c7d0e6",
        "gold": "#c5a059",
        "gold2": "#d4af37",
        "danger": "#ff4d4d",
        "ok": "#21c55d",
        "warn": "#fbbf24",
    },
    "PARCHMENT": {
        "app_bg": "#f4ecd8",
        "surface": "#fff7e6",
        "sidebar_bg": "#0c1421",
        "text": "#0c1421",
        "muted": "#3b4252",
        "gold": "#b98a2c",
        "gold2": "#c5a059",
        "danger": "#b91c1c",
        "ok": "#15803d",
        "warn": "#a16207",
    },
    "MIDNIGHT": {
        "app_bg": "#070b16",
        "surface": "#0e1630",
        "sidebar_bg": "#0b1020",
        "text": "#e6ecff",
        "muted": "#b6c3ea",
        "gold": "#5aa6ff",
        "gold2": "#7cc4ff",
        "danger": "#fb7185",
        "ok": "#34d399",
        "warn": "#fbbf24",
    },
}
C = THEMES.get(THEME, THEMES["DARK_GOLD"])


# ==========================================
# 3) CSS (premium / wow)
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
  --danger: {C["danger"]};
  --ok: {C["ok"]};
  --warn: {C["warn"]};
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
  padding-top: 3.2rem !important;
  padding-bottom: 1.25rem !important;
}}

footer {{visibility: hidden !important;}}
.stAppDeployButton {{display:none !important;}}
#stDecoration {{display:none !important;}}
header[data-testid="stHeader"] {{ background: rgba(0,0,0,0) !important; }}

section[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 2px solid rgba(197,160,89,0.55) !important;
}}
section[data-testid="stSidebar"] * {{
  color: var(--text) !important;
}}

h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid rgba(197,160,89,0.55) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
  text-shadow: 0 1px 1px rgba(0,0,0,0.35);
}}

.stMarkdown p {{
  color: var(--muted) !important;
}}

.stButton>button {{
  background: linear-gradient(135deg, rgba(12,20,33,0.95) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 900 !important;
  width: 100% !important;
  padding: 11px 12px !important;
  border: 1px solid rgba(197,160,89,0.65) !important;
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
  border-radius: 12px !important;
}}

.stTextArea textarea {{
  background-color: #fdfaf1 !important;
  color: #000000 !important;
  border: 1px solid rgba(197,160,89,0.55) !important;
  border-radius: 12px !important;
}}

.chat-user {{
  background-color: rgba(226,232,240,0.95);
  color: #0b1220;
  padding: 10px;
  border-radius: 12px;
  border-left: 6px solid #1e3a8a;
  margin-bottom: 8px;
}}
.chat-ai {{
  background-color: rgba(255,255,255,0.96);
  color: #101828;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid rgba(212,175,55,0.75);
  margin-bottom: 14px;
}}

.sticky-preview {{
  position: sticky;
  top: 4.6rem;
  border-radius: 16px;
  border: 2px solid rgba(197,160,89,0.75);
  overflow: hidden;
  box-shadow: 0 16px 40px rgba(0,0,0,0.24);
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
  transform: scale(1.35);
  transform-origin: center;
  cursor: zoom-in;
}}

.premium-lock {{
  background: linear-gradient(180deg, rgba(197,160,89,0.18), rgba(255,255,255,0.04));
  border: 1px solid rgba(197,160,89,0.40);
  border-radius: 18px;
  padding: 14px 14px;
  box-shadow: 0 18px 40px rgba(0,0,0,0.22);
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
# 4) SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name="gemini-flash-latest")  # O'ZGARMAYDI


# ==========================================
# 5) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"
if "last_fn" not in st.session_state: st.session_state.last_fn = None

if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "warn_rpc" not in st.session_state: st.session_state.warn_rpc = False

if "current_page" not in st.session_state: st.session_state.current_page = None
if "search_kw" not in st.session_state: st.session_state.search_kw = ""


# ==========================================
# 6) HELPERS
# ==========================================
def norm_email(s: str) -> str:
    s = (s or "").strip().lower()
    return s

def is_valid_email(s: str) -> bool:
    s = norm_email(s)
    return bool(re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", s))

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

@st.cache_data(show_spinner=False, max_entries=128)
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

def _pick_line(rx: str, text: str) -> str:
    m = re.search(rx, text or "", flags=re.IGNORECASE | re.MULTILINE)
    return (m.group(1).strip() if m else "").strip()

def extract_diagnosis(text: str) -> dict:
    t = text or ""
    til = _pick_line(r"^\s*Til\s*:\s*(.+?)\s*$", t)
    xat = _pick_line(r"^\s*Xat\s*us?uslubi\s*:\s*(.+?)\s*$", t) or _pick_line(r"^\s*Xat\s*uslubi\s*:\s*(.+?)\s*$", t)
    conf = _pick_line(r"^\s*Ishonchlilik\s*:\s*(.+?)\s*$", t)

    til = til.replace("|", "").strip()
    xat = xat.replace("|", "").strip()
    conf = conf.replace("|", "").strip()
    return {"til": til, "xat": xat, "conf": conf}

def is_valid_format(ai_text: str) -> bool:
    d = extract_diagnosis(ai_text or "")
    if not (d["til"] and d["xat"] and d["conf"]):
        return False
    if "noma" in d["til"].lower() and "noma" in d["xat"].lower():
        return False
    return True

def aggregate_detected_meta(results: dict[int, str]) -> dict:
    til_list, xat_list, conf_list = [], [], []
    for _, txt in results.items():
        d = extract_diagnosis(txt)
        if d["til"] and "noma" not in d["til"].lower():
            til_list.append(d["til"])
        if d["xat"] and "noma" not in d["xat"].lower():
            xat_list.append(d["xat"])
        if d["conf"]:
            conf_list.append(d["conf"])
    til = Counter(til_list).most_common(1)[0][0] if til_list else ""
    xat = Counter(xat_list).most_common(1)[0][0] if xat_list else ""
    conf = Counter(conf_list).most_common(1)[0][0] if conf_list else ""
    return {"til": til, "xat": xat, "conf": conf}

def ensure_profile(email: str, initial_credits: int = 15) -> int:
    """Profil bo'lmasa yaratadi. Bor bo'lsa kreditni o'zgartirmaydi."""
    email = norm_email(email)
    try:
        res = db.table("profiles").select("credits").eq("email", email).limit(1).execute()
        if res.data:
            return int(res.data[0].get("credits", 0) or 0)
        db.table("profiles").insert({"email": email, "credits": int(initial_credits)}).execute()
        return int(initial_credits)
    except Exception:
        return 0

def get_credits(email: str) -> int:
    try:
        res = db.table("profiles").select("credits").eq("email", norm_email(email)).limit(1).execute()
        if res.data:
            return int(res.data[0].get("credits", 0) or 0)
    except Exception:
        pass
    return 0

def reserve_credit_safe(email: str, n: int = 1) -> bool:
    email = norm_email(email)
    # 1) RPC (eng yaxshi)
    try:
        r = db.rpc("consume_credits", {"p_email": email, "p_n": int(n)}).execute()
        ok = bool(r.data)
        if ok:
            return True
    except Exception:
        st.session_state.warn_rpc = True

    # 2) Fallback (optimistic lock)
    for _ in range(4):
        cur = get_credits(email)
        if cur < n:
            return False
        try:
            upd = (
                db.table("profiles")
                .update({"credits": int(cur - n)})
                .eq("email", email)
                .eq("credits", int(cur))
                .execute()
            )
            if upd.data:
                return True
        except Exception:
            pass
        time.sleep(0.15 + random.random() * 0.25)
    return False

def refund_credit_safe(email: str, n: int = 1) -> None:
    email = norm_email(email)
    # 1) RPC
    try:
        db.rpc("refund_credits", {"p_email": email, "p_n": int(n)}).execute()
        return
    except Exception:
        st.session_state.warn_rpc = True

    # 2) Fallback optimistic
    for _ in range(4):
        cur = get_credits(email)
        try:
            upd = (
                db.table("profiles")
                .update({"credits": int(cur + n)})
                .eq("email", email)
                .eq("credits", int(cur))
                .execute()
            )
            if upd.data:
                return
        except Exception:
            pass
        time.sleep(0.12 + random.random() * 0.25)

def log_usage(email: str, filename: str, page_index: int, status: str, latency_ms: int | None = None):
    try:
        db.table("usage_logs").insert({
            "email": norm_email(email),
            "filename": filename,
            "page_index": int(page_index),
            "status": status,
            "latency_ms": int(latency_ms) if latency_ms is not None else None,
            "provider": "gemini",
        }).execute()
    except Exception:
        pass

def save_report(email: str, doc_name: str, page_index: int, result_text: str):
    """Refresh bo'lsa ham qolishi uchun Supabase'da saqlaymiz."""
    try:
        db.table("reports").upsert({
            "email": norm_email(email),
            "doc_name": doc_name,
            "page_index": int(page_index),
            "result_text": result_text,
            "updated_at": datetime.utcnow().isoformat(),
        }, on_conflict="email,doc_name,page_index").execute()
    except Exception:
        pass

def load_reports(email: str, doc_name: str) -> dict[int, str]:
    out: dict[int, str] = {}
    try:
        res = (
            db.table("reports")
            .select("page_index,result_text")
            .eq("email", norm_email(email))
            .eq("doc_name", doc_name)
            .execute()
        )
        for row in (res.data or []):
            out[int(row["page_index"])] = row.get("result_text") or ""
    except Exception:
        pass
    return out


# ==========================================
# 7) RESULT CARD HTML (premium)
# ==========================================
def _badge(conf: str) -> str:
    conf_l = (conf or "").lower()
    if "yuqori" in conf_l:
        cls = "b-high"; label = "Yuqori ishonch"
    elif "o‘rtacha" in conf_l or "ortacha" in conf_l:
        cls = "b-med"; label = "O‘rtacha ishonch"
    else:
        cls = "b-low"; label = "Past ishonch"
    return f'<span class="badge {cls}">{html.escape(label)}</span>'

def md_to_html_with_diag(md: str) -> str:
    raw = md or ""
    diag = extract_diagnosis(raw)
    safe = html.escape(raw)
    lines = safe.splitlines()

    out = []
    i = 0

    def is_h(nline: str) -> bool:
        return bool(re.match(r"^\s*([0-9]+|[A-Z])\)\s+", nline.strip()))

    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip().lower().startswith("0)") and "tashxis" in line.strip().lower():
            block = [line]
            i += 1
            while i < len(lines) and not re.match(r"^\s*1\)\s+", lines[i].strip()):
                block.append(lines[i].rstrip())
                i += 1

            badge = _badge(diag.get("conf", ""))
            block_html = "<br/>".join(block)
            out.append(f"""
              <div class="diag-box">
                <div class="diag-head">
                  <span class="diag-title">0) Tashxis</span>
                  {badge}
                </div>
                <div class="diag-body">{block_html}</div>
              </div>
            """)
            continue

        if is_h(line):
            out.append(f"<h3 style='margin:12px 0 8px 0;'>{line.strip()}</h3>")
            i += 1
            continue

        if line.strip() == "---":
            out.append("<hr/>")
            i += 1
            continue
        if line.strip() == "":
            out.append("<br/>")
            i += 1
            continue

        out.append(f"<p style='white-space:pre-wrap; margin:10px 0;'>{line}</p>")
        i += 1

    return "\n".join(out)

def render_result_card(md: str, gold: str, blur: bool = False) -> str:
    body = md_to_html_with_diag(md)
    blur_css = "filter: blur(7px); user-select: none;" if blur else ""
    overlay = ""
    if blur:
        overlay = """
        <div class="overlay">
          <div class="overlay-card">
            🔒 Premium: To‘liq natija uchun email bilan kiring
          </div>
        </div>
        """
    return f"""
    <style>
      :root {{ --gold: {gold}; }}
      body {{
        margin: 0;
        font-family: Georgia, 'Times New Roman', serif;
        color: #111827;
        background: #ffffff;
      }}
      .wrap {{
        position: relative;
      }}
      .card {{
        padding: 18px;
        border-left: 10px solid var(--gold);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        line-height: 1.75;
        animation: fadeUp .25s ease both;
        {blur_css}
      }}
      @keyframes fadeUp {{
        from {{ opacity: 0; transform: translateY(8px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
      }}
      h3 {{
        margin: 0 0 10px 0;
        color: var(--gold);
        border-bottom: 2px solid rgba(197,160,89,0.65);
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
      hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 14px 0; }}

      .overlay {{
        position:absolute;
        inset: 0;
        display:flex;
        align-items:center;
        justify-content:center;
        padding: 18px;
      }}
      .overlay-card {{
        background: rgba(12,20,33,0.92);
        color: #fff;
        border: 1px solid rgba(197,160,89,0.65);
        border-radius: 14px;
        padding: 10px 12px;
        font-weight: 900;
        box-shadow: 0 16px 40px rgba(0,0,0,0.30);
      }}
    </style>
    <div class="wrap">
      <div class="card">{body}</div>
      {overlay}
    </div>
    """


# ==========================================
# 8) WORD EXPORT
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

def add_plain_text(doc: Document, txt: str):
    for line in (txt or "").splitlines():
        doc.add_paragraph(line)

def build_word_report(app_name: str, meta: dict, pages: dict[int, str]) -> bytes:
    doc = Document()
    _doc_set_normal_style(doc)

    _add_cover(doc, app_name, "Akademik hisobot (AI tahlil + transliteratsiya + tarjima + izoh)")
    _add_meta_table(doc, meta)
    doc.add_page_break()

    page_keys = sorted(pages.keys())
    for j, idx in enumerate(page_keys):
        doc.add_heading(f"Varaq {idx+1}", level=1)
        add_plain_text(doc, pages[idx] or "")
        if j != len(page_keys) - 1:
            doc.add_page_break()

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ==========================================
# 9) SIDEBAR (email login)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 Manuscript PRO</h2>", unsafe_allow_html=True)

    st.markdown("""
    <div class="premium-lock">
      <div style="font-weight:900; font-size:14px; color:var(--gold);">Kirish</div>
      <div style="color:var(--muted); font-size:12px; margin-top:4px;">
        Email bilan kirib, kredit va premium funksiyalarni yoqing.
      </div>
    </div>
    """, unsafe_allow_html=True)

    email_in = st.text_input("Email", placeholder="example@mail.com", label_visibility="visible")

    if st.button("KIRISH"):
        if not is_valid_email(email_in):
            st.error("Email formati noto‘g‘ri.")
        else:
            st.session_state.auth = True
            st.session_state.u_email = norm_email(email_in)
            ensure_profile(st.session_state.u_email, initial_credits=15)  # yangi userga 15 kredit
            st.success("Kirish muvaffaqiyatli.")
            st.rerun()

    if st.session_state.auth:
        live_credits = get_credits(st.session_state.u_email)
        st.markdown(f"""
        <div class="premium-lock" style="margin-top:10px;">
          <div style="display:flex; justify-content:space-between; gap:10px; align-items:center;">
            <div style="font-weight:900; color:var(--text);">👤 {html.escape(st.session_state.u_email)}</div>
            <div style="font-weight:900; color:var(--gold);">💳 {live_credits}</div>
          </div>
          <div style="margin-top:6px; color:var(--muted); font-size:12px;">
            Premium: Word • Tahrir • Chat • History • Save results
          </div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.warn_rpc:
            st.warning("Kredit RPC muammo. Fallback rejim ishlayapti.")

        if st.button("🚪 CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

        with st.expander("📜 History (oxirgi 20)", expanded=False):
            try:
                rows = (
                    db.table("usage_logs")
                    .select("filename,page_index,status,latency_ms,created_at")
                    .eq("email", norm_email(st.session_state.u_email))
                    .order("created_at", desc=True)
                    .limit(20)
                    .execute()
                )
                data = rows.data or []
                if not data:
                    st.caption("Hali tarix yo‘q.")
                else:
                    for r in data:
                        st.markdown(
                            f"- **{r.get('status','')}** • sahifa: `{(r.get('page_index',0) or 0)+1}` • "
                            f"{r.get('filename','')} • {r.get('latency_ms','-')}ms • {r.get('created_at','')}"
                        )
            except Exception:
                st.caption("History o‘qilmadi (RLS/policy tekshiring).")

    st.divider()

    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Laboratoriya")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

    scale = st.slider("PDF render scale:", 1.5, 3.8, 2.2, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

    st.markdown("### 🧭 Ko'rinish")
    view_mode = st.radio("Natija ko'rinishi:", ["Yonma-yon", "Tabs"], index=0, horizontal=True)

    st.markdown("### ✨ UI Features")
    ui_progress = st.checkbox("Top progress bar (tavsiya)", value=True)
    ui_empty = st.checkbox("Empty state hero (fayl yo'q payt)", value=True)

    st.markdown("### 🧩 Demo/Premium")
    demo_limit = 3  # siz so‘ragan
    st.caption(f"Demo rejim: login bo‘lmasa {demo_limit} sahifagacha tahlil.")


# ==========================================
# 10) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Faylni yuklang",
    type=["pdf", "png", "jpg", "jpeg"],
    label_visibility="collapsed"
)

# Empty state hero
if (uploaded_file is None) and ui_empty:
    st.markdown(f"""
    <div style="
      background: linear-gradient(180deg, rgba(197,160,89,0.18), rgba(255,255,255,0.04));
      border: 1px solid rgba(197,160,89,0.40);
      border-radius: 18px;
      padding: 18px 18px;
      box-shadow: 0 18px 40px rgba(0,0,0,0.22);
      max-width: 980px;
      margin: 18px auto 0 auto;
    ">
      <div style="display:flex; gap:14px; align-items:center; justify-content:space-between; flex-wrap:wrap;">
        <div>
          <div style="font-size:18px; font-weight:900; color:{C["gold"]};">📜 Manuscript AI — Tez demo</div>
          <div style="color:{C["muted"]}; margin-top:4px;">
            1) PDF/rasm yuklang → 2) Sahifani tanlang → 3) Akademik tahlilni boshlang
          </div>
        </div>
        <div style="
          background: rgba(12,20,33,0.55);
          border: 1px solid rgba(197,160,89,0.35);
          border-radius: 14px;
          padding: 10px 12px;
          color:{C["text"]};
          font-weight:900;
        ">
          ✅ Drag & drop ham ishlaydi
        </div>
      </div>
      <div style="margin-top:12px; color:{C["muted"]}; font-size:14px; line-height:1.6;">
        * Skan sifatini oshirish uchun sidebar’dagi Yorqinlik/Kontrastdan foydalaning.
        <br/>* Katta PDF bo‘lsa, “Preview max sahifa”ni 20–30 atrofida qoldiring.
      </div>
    </div>
    """, unsafe_allow_html=True)

if uploaded_file:
    # Load/render once per file
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
            st.session_state.current_page = None

            # ✅ load saved reports (premium)
            if st.session_state.auth:
                saved = load_reports(st.session_state.u_email, st.session_state.last_fn)
                if saved:
                    st.session_state.results.update(saved)

            gc.collect()

    processed_pages = [
        preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate)
        for b in st.session_state.page_bytes
    ]

    total_pages = len(processed_pages)
    st.caption(f"Yuklandi: **{total_pages}** sahifa (preview limit: {max_pages}).")

    # Page selection UX
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

    # Demo limit enforcement
    if (not st.session_state.auth) and selected_indices:
        if len(selected_indices) > demo_limit:
            st.warning(f"Demo rejimda maksimum {demo_limit} sahifa tahlil qilinadi. Birinchi {demo_limit} sahifa olinadi.")
            selected_indices = selected_indices[:demo_limit]

    # Preview grid (faqat natija yo'q bo'lsa)
    if not st.session_state.results and selected_indices:
        cols = st.columns(min(len(selected_indices), 4))
        for i, idx in enumerate(selected_indices[:16]):
            with cols[i % min(len(cols), 4)]:
                st.image(processed_pages[idx], caption=f"Varaq {idx+1}", use_container_width=True)
        if len(selected_indices) > 16:
            st.info(f"Previewda faqat 16 ta ko'rsatildi. Tanlangan jami: {len(selected_indices)}.")

    # Premium banner
    st.markdown(f"""
    <div style="
      background: rgba(255,243,224,1);
      border: 1px solid #ffb74d;
      border-radius: 14px;
      padding: 14px 14px;
      margin: 14px 0 14px 0;
      max-width: 980px;
      margin-left:auto; margin-right:auto;
      box-shadow: 0 18px 40px rgba(0,0,0,0.10);
    ">
      <div style="font-weight:900; color:#e65100; font-size:16px;">
        🔒 Word hisobot • Tahrir • AI Chat • History • Save results — Premium
      </div>
      <div style="margin-top:6px; color:#5a3a00; line-height:1.6;">
        Demo rejimda natijani ko‘rishingiz mumkin. To‘liq funksiyalar uchun email bilan kiring.
      </div>
      <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap; align-items:center; justify-content:space-between;">
        <div style="background: rgba(12,20,33,0.10); border: 1px dashed rgba(230,81,0,0.35);
                    border-radius: 12px; padding: 8px 10px; color:#5a3a00; font-weight:900; font-size:13px;">
          Email bilan kirish ✅
        </div>
        <div style="color:#5a3a00; font-size:13px;">Premium rejimda natija refreshdan keyin ham saqlanadi</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Run analysis
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
        hint_era = "" if (auto_detect or era == "Noma'lum") else era

        prompt_base = (
            "Siz Manuscript AI mutaxassisiz.\n"
            "MUHIM: Foydalanuvchi tanlovi faqat HINT. Uni haqiqat deb qabul qilmang.\n"
            "Avval rasmga qarab MUSTAQIL aniqlang: til va xat uslubi.\n\n"
            f"Foydalanuvchi hintlari: til='{hint_lang or 'yo‘q'}', xat='{hint_era or 'yo‘q'}'.\n\n"
            "Format (aniq shunday):\n"
            "0) Tashxis:\n"
            "Til: <aniqlangan til>\n"
            "Xat uslubi: <aniqlangan xat uslubi>\n"
            "Hint mosligi: <mos | mos emas | hint yo‘q>\n"
            "Ishonchlilik: past | o‘rtacha | yuqori\n"
            "Sabab: <1-2 jumla>\n"
            "1) To‘g‘ridan-to‘g‘ri tarjima (oddiy o‘zbekcha)\n"
            "2) Paleografiya\n"
            "3) Transliteratsiya (satrma-satr, o‘qilganicha)\n"
            "4) Tarjima (akademik, mazmuniy)\n"
            "5) Arxaik lug'at (5–10 so‘z)\n"
            "6) Izoh (kontekst; aniq bo‘lmasa ehtiyot bo‘l)\n\n"
            "Qoidalar:\n"
            "- O‘qilmagan joyni taxmin qilmang: [o‘qilmadi] yoki [?] bilan belgilang.\n"
            "- Ism/son/sana bo‘lsa aynan ko‘ringanicha yozing (tasdiqsiz uydirma qilmang).\n"
            "- Hech qachon inglizcha label ishlatma. Faqat o‘zbekcha yoz.\n"
        )

        prompt_retry = (
            prompt_base
            + "\n"
            + "MUHIM TEKSHIRUV:\n"
            + "- Agar Til/Xat uslubi/Ishonchlilik satrlari chiqmasa, formatni to‘g‘rilab qayta yoz.\n"
            + "- Juda qisqa yoki bo‘sh javob bermang.\n"
        )

        total = len(selected_indices)
        done = 0
        progress_ph = st.empty()
        bar = st.progress(0.0) if (ui_progress and total > 0) else None

        def _update_progress():
            if bar:
                ratio = done / max(total, 1)
                bar.progress(ratio)
                progress_ph.markdown(
                    f"<div style='text-align:center; color:{C['muted']}; font-weight:900;'>"
                    f"📈 Tahlil jarayoni: <span style='color:{C['gold']};'>{done}/{total}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        _update_progress()

        # batch 2-3 pages
        batch_size = 3 if total <= 6 else 2
        batches = [selected_indices[i:i+batch_size] for i in range(0, total, batch_size)]

        for batch in batches:
            for idx in batch:
                # Premium: kredit yechish. Demo: kredit yo‘q.
                reserved = False
                if st.session_state.auth:
                    ok = reserve_credit_safe(st.session_state.u_email, 1)
                    if not ok:
                        st.warning("Kredit tugagan. Davom etish uchun kredit qo‘shing.")
                        continue
                    reserved = True

                with st.status(f"Sahifa {idx+1}...") as s:
                    t0 = time.time()
                    try:
                        img_bytes = processed_pages[idx]
                        payload = {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}

                        text = call_gemini_with_retry(prompt_base, payload, tries=4)

                        # validator + 1 retry
                        if (not text.strip()) or (not is_valid_format(text)):
                            text2 = call_gemini_with_retry(prompt_retry, payload, tries=3)
                            if text2.strip() and is_valid_format(text2):
                                text = text2

                        if not text.strip():
                            if reserved:
                                refund_credit_safe(st.session_state.u_email, 1)
                            s.update(label="Bo‘sh natija (refund)", state="error")
                            st.error("AI bo‘sh natija qaytardi. Qayta urinib ko‘ring.")
                            if st.session_state.auth:
                                log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "error", int((time.time()-t0)*1000))
                            continue

                        st.session_state.results[idx] = text
                        s.update(label="Tayyor!", state="complete")

                        if st.session_state.auth:
                            save_report(st.session_state.u_email, st.session_state.last_fn, idx, text)
                            log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "ok", int((time.time()-t0)*1000))

                    except Exception as e:
                        if reserved:
                            refund_credit_safe(st.session_state.u_email, 1)
                        s.update(label="Xato (refund)", state="error")
                        st.error(f"Xato: {e}")
                        if st.session_state.auth:
                            log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "error", int((time.time()-t0)*1000))

                done += 1
                _update_progress()

                # bigger random delay (429 kamayadi)
                time.sleep(0.85 + random.random() * 1.25)

            # batch pause
            time.sleep(0.8 + random.random() * 1.1)

        if bar:
            bar.progress(1.0)

        gc.collect()
        st.rerun()

    # Results area
    if st.session_state.results:
        st.divider()

        keys_all = sorted(st.session_state.results.keys())
        if st.session_state.current_page is None and keys_all:
            st.session_state.current_page = keys_all[0]

        # Search + navigation (wow UX)
        top = st.container()
        with top:
            cA, cB, cC = st.columns([1.25, 0.5, 0.5], gap="medium")
            with cA:
                st.session_state.search_kw = st.text_input(
                    "🔎 Natijalardan qidirish (keyword):",
                    value=st.session_state.search_kw,
                    placeholder="masalan: Samarqand, Mir Muhammad, sanad..."
                )
            with cB:
                if st.button("⬅️ Prev"):
                    if keys_all:
                        i = keys_all.index(st.session_state.current_page)
                        st.session_state.current_page = keys_all[max(0, i-1)]
                        st.rerun()
            with cC:
                if st.button("Next ➡️"):
                    if keys_all:
                        i = keys_all.index(st.session_state.current_page)
                        st.session_state.current_page = keys_all[min(len(keys_all)-1, i+1)]
                        st.rerun()

        # filter by search
        keys = keys_all
        kw = (st.session_state.search_kw or "").strip().lower()
        if kw:
            keys = [k for k in keys_all if kw in (st.session_state.results.get(k, "").lower())]
            st.caption(f"Topildi: **{len(keys)}** sahifa (jami: {len(keys_all)}).")

        for idx in keys:
            expanded = (idx == st.session_state.current_page)
            with st.expander(f"📖 Varaq {idx+1}", expanded=expanded):
                res = st.session_state.results[idx] or ""

                img_b64 = base64.b64encode(processed_pages[idx]).decode("utf-8")
                img_html = f"""
                <div class="sticky-preview">
                  <img src="data:image/jpeg;base64,{img_b64}" alt="page {idx+1}" />
                </div>
                """

                blur_full = (not st.session_state.auth)

                if view_mode == "Tabs":
                    tabs = st.tabs(["📷 Rasm", "📝 Natija", "✍️ Tahrir", "💬 Chat"])
                    with tabs[0]:
                        st.markdown(img_html, unsafe_allow_html=True)
                    with tabs[1]:
                        components.html(render_result_card(res, C["gold"], blur=blur_full), height=580, scrolling=True)
                        # Copy (premium)
                        if st.session_state.auth:
                            components.html(f"""
                            <button id="copybtn" style="
                              margin-top:10px; padding:10px 12px; border-radius:12px;
                              border:1px solid rgba(197,160,89,0.65);
                              background: rgba(12,20,33,0.92); color: {C["gold"]};
                              font-weight:900; cursor:pointer;
                            ">📋 Natijani nusxalash</button>
                            <script>
                              const t = {html.escape(repr(res))};
                              document.getElementById("copybtn").onclick = async () => {{
                                try {{ await navigator.clipboard.writeText(t); alert("Nusxalandi ✅"); }}
                                catch(e) {{ alert("Clipboard ishlamadi"); }}
                              }};
                            </script>
                            """, height=70)
                    with tabs[2]:
                        if not st.session_state.auth:
                            st.info("🔒 Tahrir — Premium (email bilan kiring).")
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=260,
                                key=f"ed_{idx}"
                            )
                            save_report(st.session_state.u_email, st.session_state.last_fn, idx, st.session_state.results[idx])
                    with tabs[3]:
                        if not st.session_state.auth:
                            st.info("🔒 Chat — Premium (email bilan kiring).")
                        else:
                            st.session_state.chats.setdefault(idx, [])
                            for ch in st.session_state.chats[idx]:
                                st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                            user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                            if st.button(f"So'rash ({idx+1})", key=f"btn_{idx}"):
                                if user_q.strip():
                                    with st.spinner("..."):
                                        chat_prompt = (
                                            f"Matn: {st.session_state.results[idx]}\n"
                                            f"Savol: {user_q}\n"
                                            "Javobni o‘zbekcha, aniq va qisqa yoz. "
                                            "Tasdiqsiz uydirma qilmang."
                                        )
                                        chat_resp = model.generate_content([chat_prompt])
                                        st.session_state.chats[idx].append({"q": user_q, "a": getattr(chat_resp, "text", "") or ""})
                                        st.rerun()

                else:
                    c1, c2 = st.columns([1, 1.35], gap="large")
                    with c1:
                        st.markdown(img_html, unsafe_allow_html=True)

                    with c2:
                        components.html(render_result_card(res, C["gold"], blur=blur_full), height=520, scrolling=True)

                        if not st.session_state.auth:
                            st.info("🔒 Word/Tahrir/Chat/Save/History — Premium (email bilan kiring).")
                        else:
                            st.session_state.results[idx] = st.text_area(
                                f"Tahrir ({idx+1}):",
                                value=st.session_state.results[idx],
                                height=220,
                                key=f"ed_{idx}"
                            )
                            save_report(st.session_state.u_email, st.session_state.last_fn, idx, st.session_state.results[idx])

                            with st.expander("💬 AI Chat (shu varaq bo‘yicha)", expanded=True):
                                st.session_state.chats.setdefault(idx, [])
                                for ch in st.session_state.chats[idx]:
                                    st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                                user_q = st.text_input("Savol bering:", key=f"q_side_{idx}")
                                if st.button(f"So'rash (Varaq {idx+1})", key=f"btn_side_{idx}"):
                                    if user_q.strip():
                                        with st.spinner("..."):
                                            chat_prompt = (
                                                f"Matn: {st.session_state.results[idx]}\n"
                                                f"Savol: {user_q}\n"
                                                "Javobni o‘zbekcha, aniq va qisqa yoz. "
                                                "Tasdiqsiz uydirma qilmang."
                                            )
                                            chat_resp = model.generate_content([chat_prompt])
                                            st.session_state.chats[idx].append({"q": user_q, "a": getattr(chat_resp, "text", "") or ""})
                                            st.rerun()

        # Word Export (premium)
        if st.session_state.auth and st.session_state.results:
            detected = aggregate_detected_meta(st.session_state.results)

            meta = {
                "Hujjat nomi": st.session_state.last_fn,
                "Til (aniqlangan)": detected["til"] or "Noma'lum",
                "Xat uslubi (aniqlangan)": detected["xat"] or "Noma'lum",
                "Avto aniqlash": "Ha" if auto_detect else "Yo‘q",
                "Til (hint)": lang,
                "Xat uslubi (hint)": era,
                "Eksport qilingan sahifalar": ", ".join(str(i+1) for i in sorted(st.session_state.results.keys())),
                "Yaratilgan vaqt": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }

            report_bytes = build_word_report("Manuscript AI", meta, st.session_state.results)
            st.download_button(
                "📥 WORD HISOBOTNI YUKLAB OLISH (.docx)",
                report_bytes,
                file_name="Manuscript_AI_Report.docx"
            )

gc.collect()
