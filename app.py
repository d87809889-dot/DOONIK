import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium

import io, gc, base64, time, random, html, re, threading
from datetime import datetime
from collections import Counter, deque

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

# ==========================================
# 2) CONSTANTS
# ==========================================
THEME = "DARK_GOLD"
DEMO_LIMIT_PAGES = 3
STARTER_CREDITS = 10
HISTORY_LIMIT = 20

# Rate-limit safety
SAFE_RPM = 7            # 15 RPM bo'lsa ham, cloud/retry uchun xavfsizroq
RATE_WINDOW_SEC = 60
MAX_RETRIES = 7

# Image quality balance (aniqlik + 429 xavfi)
JPEG_QUALITY_FULL = 82
JPEG_QUALITY_TILE = 84
FULL_MAX_SIDE = 2000
TILE_MAX_SIDE = 2400

# PDF render (matn uchun)
PDF_SCALE_DEFAULT = 2.0

# Max output (uzun translit bo'ladi)
MAX_OUT_TOKENS = 4096

# Model candidates (404 bo'lsa fallback)
MODEL_CANDIDATES = [
    "gemini-flash-latest",        # siz xohlagan
    "gemini-1.5-flash-latest",    # fallback
    "gemini-1.5-flash",           # fallback
]

# ==========================================
# 3) THEME
# ==========================================
THEMES = {
    "DARK_GOLD": {
        "app_bg": "#0b1220",
        "surface": "#10182b",
        "sidebar_bg": "#0c1421",
        "text": "#eaf0ff",
        "muted": "#c7d0e6",
        "gold": "#c5a059",
        "gold2": "#d4af37",
    }
}
C = THEMES["DARK_GOLD"]

# ==========================================
# 4) CSS
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
section[data-testid="stSidebar"] * {{
  color: var(--text) !important;
}}
section[data-testid="stSidebar"] .stCaption {{
  color: var(--muted) !important;
}}

h1, h2, h3, h4 {{
  color: var(--gold) !important;
  font-family: 'Georgia', serif;
  border-bottom: 2px solid var(--gold) !important;
  padding-bottom: 8px !important;
  text-align: center !important;
  text-shadow: 0 1px 1px rgba(0,0,0,0.35);
}}

.stMarkdown p {{
  color: var(--muted) !important;
}}

.stButton>button {{
  background: linear-gradient(135deg, var(--sidebar-bg) 0%, #1e3a8a 100%) !important;
  color: var(--gold) !important;
  font-weight: 900 !important;
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

.chat-user {{
  background-color: #e2e8f0;
  color: #000;
  padding: 10px;
  border-radius: 10px;
  border-left: 5px solid #1e3a8a;
  margin-bottom: 6px;
}}
.chat-ai {{
  background-color: #ffffff;
  color: #1a1a1a;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid #d4af37;
  margin-bottom: 14px;
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
}}
.sticky-preview img {{
  width: 100%;
  height: 540px;
  object-fit: contain;
  display: block;
}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 5) SERVICES (DB + GEMINI)
# ==========================================
@st.cache_resource
def get_db_or_none():
    try:
        url = st.secrets.get("SUPABASE_URL", "")
        key = st.secrets.get("SUPABASE_KEY", "")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None

db = get_db_or_none()

# Gemini
api_key = st.secrets.get("GEMINI_API_KEY", "")
if not api_key:
    st.error("GEMINI_API_KEY topilmadi (Streamlit secrets).")
    st.stop()

genai.configure(api_key=api_key)

@st.cache_resource
def get_model_cached(name: str):
    return genai.GenerativeModel(model_name=name)


# ==========================================
# 6) RATE LIMITER (process-wide)
# ==========================================
class RateLimiter:
    def __init__(self, rpm: int, window_sec: int = 60):
        self.rpm = max(1, int(rpm))
        self.window = int(window_sec)
        self.lock = threading.Lock()
        self.ts = deque()

    def wait_for_slot(self):
        while True:
            with self.lock:
                now = time.monotonic()
                while self.ts and (now - self.ts[0]) > self.window:
                    self.ts.popleft()
                if len(self.ts) < self.rpm:
                    self.ts.append(now)
                    return
                sleep_for = (self.window - (now - self.ts[0])) + 0.15
            time.sleep(max(0.30, sleep_for))

@st.cache_resource
def get_limiter():
    return RateLimiter(SAFE_RPM, RATE_WINDOW_SEC)

limiter = get_limiter()


def _looks_like_404(msg: str) -> bool:
    m = (msg or "").lower()
    return ("404" in m) or ("not found" in m)

def _looks_like_429(msg: str) -> bool:
    m = (msg or "").lower()
    return ("429" in m) or ("quota" in m) or ("rate" in m) or ("exhaust" in m)

def safe_generate(parts: list, max_tokens: int) -> str:
    """
    - 404 bo'lsa: model fallback
    - 429/500/503/timeout bo'lsa: backoff + retry
    """
    last_err = None
    for model_name in MODEL_CANDIDATES:
        model = get_model_cached(model_name)
        for attempt in range(MAX_RETRIES):
            try:
                limiter.wait_for_slot()
                resp = model.generate_content(
                    parts,
                    generation_config={"max_output_tokens": max_tokens, "temperature": 0.15}
                )
                return getattr(resp, "text", "") or ""
            except Exception as e:
                last_err = e
                msg = str(e)

                if _looks_like_404(msg):
                    break  # keyingi modelga o'tamiz

                if _looks_like_429(msg) or ("500" in msg) or ("503" in msg) or ("timeout" in msg.lower()):
                    time.sleep(min(60, (2 ** attempt)) + random.uniform(0.8, 2.0))
                    continue

                raise  # boshqa xato

    raise RuntimeError(f"AI xatosi: {last_err}")


# ==========================================
# 7) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "last_fn" not in st.session_state: st.session_state.last_fn = None

if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "warn_db" not in st.session_state: st.session_state.warn_db = False


# ==========================================
# 8) IMAGE HELPERS
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int, max_side: int) -> bytes:
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
def render_pdf_pages_to_bytes(file_bytes: bytes, max_pages: int, scale: float):
    pdf = pdfium.PdfDocument(file_bytes)
    out = []
    try:
        n = min(len(pdf), max_pages)
        for i in range(n):
            pil_img = pdf[i].render(scale=scale).to_pil()
            out.append(pil_to_jpeg_bytes(pil_img, JPEG_QUALITY_FULL, FULL_MAX_SIDE))
    finally:
        try: pdf.close()
        except Exception: pass
    return out

@st.cache_data(show_spinner=False, max_entries=256)
def preprocess_bytes(img_bytes: bytes, brightness: float, contrast: float, rotate: int, sharpen: float) -> bytes:
    img = Image.open(io.BytesIO(img_bytes))
    img = ImageOps.exif_transpose(img)
    if rotate:
        img = img.rotate(rotate, expand=True)

    img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)

    if sharpen > 0:
        img = img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(120 * sharpen), threshold=2))

    return pil_to_jpeg_bytes(img, JPEG_QUALITY_FULL, FULL_MAX_SIDE)

def parse_pages(spec: str, max_n: int):
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

def build_payloads_from_page(img_bytes: bytes, hi_res: bool = False):
    """
    1 request ichida: full + zoom/tiles.
    - spread bo'lsa: full + left + right
    - oddiy sahifa bo'lsa: full + 2x2 tiles (overlap bilan)
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = img.size
    aspect = w / max(h, 1)

    full_side = 2200 if hi_res else FULL_MAX_SIDE
    tile_side = 2600 if hi_res else TILE_MAX_SIDE
    q_full = 84 if hi_res else JPEG_QUALITY_FULL
    q_tile = 86 if hi_res else JPEG_QUALITY_TILE

    def to_payload(b: bytes):
        return {"mime_type": "image/jpeg", "data": base64.b64encode(b).decode("utf-8")}

    payloads = [to_payload(pil_to_jpeg_bytes(img, q_full, full_side))]

    if aspect >= 1.25:
        # ikki bet spread
        left = img.crop((0, 0, w // 2, h))
        right = img.crop((w // 2, 0, w, h))
        payloads.append(to_payload(pil_to_jpeg_bytes(left, q_tile, tile_side)))
        payloads.append(to_payload(pil_to_jpeg_bytes(right, q_tile, tile_side)))
        return payloads

    # 2x2 tile + overlap
    ox = int(w * 0.06)
    oy = int(h * 0.06)
    xs = [0, w // 2]
    ys = [0, h // 2]
    for yy in ys:
        for xx in xs:
            x1 = max(0, xx - ox)
            y1 = max(0, yy - oy)
            x2 = min(w, xx + w // 2 + ox)
            y2 = min(h, yy + h // 2 + oy)
            tile = img.crop((x1, y1, x2, y2))
            payloads.append(to_payload(pil_to_jpeg_bytes(tile, q_tile, tile_side)))

    return payloads


# ==========================================
# 9) PROMPT + VALIDATION
# ==========================================
def build_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Sizga bir sahifa uchun bir nechta rasm beriladi: 1-rasm full, qolganlari zoom/tiles.\n"
        "ASOSIY: zoom/tiles rasmlardagi matnga tayanib maksimal to‘liq o‘qing.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Bo‘limlarni bo‘sh qoldirmang.\n"
        "- Matnda bor so‘zlarni tashlab ketmang.\n"
        "- Transliteratsiya satrma-satr bo‘lsin.\n\n"
        f"HINT: til='{hl}', xat uslubi='{he}'.\n\n"
        "FORMAT (aniq shu tartibda):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan til yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan xat yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Transliteratsiya:\n"
        "<satrma-satr, maksimal to‘liq>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst va noaniqliklar; ehtiyotkor izoh>\n"
    )

def has_required_sections(text: str) -> bool:
    t = (text or "").lower()
    return ("0) tashxis" in t) and ("1) transliteratsiya" in t) and ("2) to" in t) and ("6) izoh" in t)

def translit_length(text: str) -> int:
    if not text:
        return 0
    m = re.search(r"1\)\s*Transliteratsiya\s*:?\s*\n([\s\S]*?)(\n\s*2\)|\n\s*6\)|$)", text, flags=re.IGNORECASE)
    if not m:
        return 0
    return len((m.group(1) or "").strip())


# ==========================================
# 10) RESULT CARD (pretty render)
# ==========================================
def extract_diagnosis(text: str) -> dict:
    t = text or ""
    def pick(rx):
        m = re.search(rx, t, flags=re.IGNORECASE)
        return (m.group(1).strip() if m else "").strip()
    til = pick(r"Til\s*:\s*(.+)")
    xat = pick(r"Xat\s*uslubi\s*:\s*(.+)")
    conf = pick(r"Ishonchlilik\s*:\s*(.+)")
    return {"til": til.replace("|", "").strip(),
            "xat": xat.replace("|", "").strip(),
            "conf": conf.replace("|", "").strip()}

def _badge(conf: str) -> str:
    conf_l = (conf or "").lower()
    if "yuqori" in conf_l:
        cls = "b-high"; label = "Yuqori ishonch"
    elif "o‘rtacha" in conf_l or "ortacha" in conf_l:
        cls = "b-med"; label = "O‘rtacha ishonch"
    else:
        cls = "b-low"; label = "Past ishonch"
    return f'<span class="badge {cls}">{html.escape(label)}</span>'

def md_to_html(md: str) -> str:
    raw = md or ""
    diag = extract_diagnosis(raw)
    safe = html.escape(raw)
    lines = safe.splitlines()
    out = []
    i = 0

    def is_h(nline: str) -> bool:
        return bool(re.match(r"^\d+\)\s+", nline.strip()))

    while i < len(lines):
        line = lines[i].rstrip()

        if line.strip().lower().startswith("0)") and "tashxis" in line.strip().lower():
            block = [line]
            i += 1
            while i < len(lines) and not lines[i].strip().lower().startswith("1)"):
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
            out.append(f"<h3>{line.strip()}</h3>"); i += 1; continue
        if line.strip() == "---":
            out.append("<hr/>"); i += 1; continue
        if line.strip() == "":
            out.append("<br/>"); i += 1; continue

        out.append(f"<p style='white-space:pre-wrap; margin:10px 0;'>{line}</p>")
        i += 1

    return "\n".join(out)

def render_result_card(md: str, gold: str) -> str:
    body = md_to_html(md)
    return f"""
    <style>
      :root {{ --gold: {gold}; }}
      body {{ margin:0; font-family: Georgia, 'Times New Roman', serif; color:#111827; background:#ffffff; }}
      .card {{
        padding: 18px;
        border-left: 10px solid var(--gold);
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.18);
        line-height: 1.75;
      }}
      h3 {{
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
      .diag-head {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px; }}
      .diag-title {{ font-weight: 900; color: #1f2937; }}
      .badge {{
        font-size: 12px; font-weight: 900;
        padding: 6px 10px; border-radius: 999px;
        border: 1px solid rgba(0,0,0,0.08);
        box-shadow: 0 6px 14px rgba(0,0,0,0.08);
        white-space: nowrap;
      }}
      .b-high {{ background: #dcfce7; color: #14532d; }}
      .b-med  {{ background: #fef9c3; color: #713f12; }}
      .b-low  {{ background: #fee2e2; color: #7f1d1d; }}
      hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 14px 0; }}
    </style>
    <div class="card">{body}</div>
    """


# ==========================================
# 11) WORD EXPORT
# ==========================================
def _doc_set_normal_style(doc: Document):
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

def _add_cover(doc: Document, title: str, subtitle: str):
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(title); run.bold = True; run.font.size = Pt(20)
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = p2.add_run(subtitle); run2.font.size = Pt(12)
    doc.add_paragraph("")

def _add_meta_table(doc: Document, meta: dict):
    t = doc.add_table(rows=0, cols=2); t.style = "Table Grid"
    for k, v in meta.items():
        row = t.add_row().cells
        row[0].text = str(k); row[1].text = str(v)

def add_plain_text(doc: Document, txt: str):
    for line in (txt or "").splitlines():
        doc.add_paragraph(line)

def build_word_report(app_name: str, meta: dict, pages: dict) -> bytes:
    doc = Document()
    _doc_set_normal_style(doc)
    _add_cover(doc, app_name, "Hisobot (Transliteratsiya + Tarjima + Izoh)")
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

def aggregate_detected_meta(results: dict) -> dict:
    til_list, xat_list, conf_list = [], [], []
    for _, txt in results.items():
        d = extract_diagnosis(txt)
        if d["til"] and "noma" not in d["til"].lower(): til_list.append(d["til"])
        if d["xat"] and "noma" not in d["xat"].lower(): xat_list.append(d["xat"])
        if d["conf"]: conf_list.append(d["conf"])
    til = Counter(til_list).most_common(1)[0][0] if til_list else ""
    xat = Counter(xat_list).most_common(1)[0][0] if xat_list else ""
    conf = Counter(conf_list).most_common(1)[0][0] if conf_list else ""
    return {"til": til, "xat": xat, "conf": conf}


# ==========================================
# 12) DB HELPERS (optional)
# ==========================================
def ensure_profile(email: str) -> None:
    if db is None:
        return
    try:
        existing = db.table("profiles").select("email,credits").eq("email", email).limit(1).execute()
        if existing.data:
            return
        db.table("profiles").insert({"email": email, "credits": STARTER_CREDITS}).execute()
    except Exception:
        st.session_state.warn_db = True

def get_credits(email: str) -> int:
    if db is None:
        return 0
    try:
        r = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(r.data["credits"]) if r.data and "credits" in r.data else 0
    except Exception:
        st.session_state.warn_db = True
        return 0

def consume_credit_safe(email: str, n: int = 1) -> bool:
    if db is None:
        return True  # DB yo'q bo'lsa kredit bloklamaymiz (demo uchun)
    try:
        r = db.rpc("consume_credits", {"p_email": email, "p_n": n}).execute()
        return bool(r.data)
    except Exception:
        pass

    # fallback
    for _ in range(2):
        try:
            cur = get_credits(email)
            if cur < n:
                return False
            newv = cur - n
            upd = db.table("profiles").update({"credits": newv}).eq("email", email).eq("credits", cur).execute()
            if upd.data:
                return True
        except Exception:
            st.session_state.warn_db = True
            return False
    return False

def refund_credit_safe(email: str, n: int = 1) -> None:
    if db is None:
        return
    try:
        db.rpc("refund_credits", {"p_email": email, "p_n": n}).execute()
        return
    except Exception:
        pass
    try:
        cur = get_credits(email)
        db.table("profiles").update({"credits": cur + n}).eq("email", email).eq("credits", cur).execute()
    except Exception:
        st.session_state.warn_db = True

def log_usage(email: str, doc_name: str, page_index: int, status: str, note: str = "") -> None:
    if db is None:
        return
    try:
        db.table("usage_logs").insert({
            "email": email,
            "doc_name": doc_name,
            "page_index": page_index,
            "status": status,
            "note": (note or "")[:240],
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        st.session_state.warn_db = True

def save_report(email: str, doc_name: str, page_index: int, result_text: str) -> None:
    if db is None:
        return
    try:
        db.table("reports").upsert(
            {
                "email": email,
                "doc_name": doc_name,
                "page_index": page_index,
                "result_text": result_text,
                "updated_at": datetime.utcnow().isoformat()
            },
            on_conflict="email,doc_name,page_index"
        ).execute()
    except Exception:
        st.session_state.warn_db = True

def load_reports(email: str, doc_name: str) -> dict:
    if db is None:
        return {}
    try:
        r = db.table("reports").select("page_index,result_text") \
            .eq("email", email).eq("doc_name", doc_name).limit(200).execute()
        out = {}
        for row in (r.data or []):
            out[int(row["page_index"])] = row.get("result_text") or ""
        return out
    except Exception:
        st.session_state.warn_db = True
        return {}


# ==========================================
# 13) SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    st.markdown("### ✉️ Email bilan kirish")
    st.caption("Email kiriting — kreditlar, history, Word eksport ochiladi.")

    email_in = st.text_input("Email", value=(st.session_state.u_email or ""), placeholder="example@mail.com")
    if st.button("KIRISH"):
        email = (email_in or "").strip().lower()
        if not email or "@" not in email:
            st.error("Emailni to‘g‘ri kiriting.")
        else:
            st.session_state.auth = True
            st.session_state.u_email = email
            ensure_profile(email)
            st.rerun()

    if st.session_state.auth:
        st.divider()
        credits = get_credits(st.session_state.u_email)
        st.markdown(f"""
        <div style="
          background: rgba(255,255,255,0.04);
          border: 1px solid rgba(197,160,89,0.35);
          border-radius: 16px;
          padding: 12px 12px;
          box-shadow: 0 14px 30px rgba(0,0,0,0.18);
        ">
          <div style="font-weight:900; color:{C["gold"]}; font-size:14px;">👤 Profil</div>
          <div style="color:{C["text"]}; margin-top:6px; font-weight:900;">{html.escape(st.session_state.u_email)}</div>
          <div style="margin-top:8px; color:{C["muted"]};">Kreditlar: <span style="color:{C["gold"]}; font-weight:900;">{credits}</span> sahifa</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.warn_db:
            st.warning("DB/RPC vaqtinchalik muammo bo‘lishi mumkin.")

        if st.button("🚪 CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = ""
            st.rerun()

        with st.expander(f"🧾 History (oxirgi {HISTORY_LIMIT})", expanded=False):
            if db is None:
                st.caption("History: DB ulanmagan.")
            else:
                try:
                    r = db.table("usage_logs") \
                        .select("created_at,doc_name,page_index,status") \
                        .eq("email", st.session_state.u_email) \
                        .order("created_at", desc=True) \
                        .limit(HISTORY_LIMIT).execute()
                    data = r.data or []
                    if not data:
                        st.caption("History hozircha bo‘sh.")
                    else:
                        for row in data:
                            ts = (row.get("created_at") or "")[:19].replace("T", " ")
                            st.caption(f"{ts} • {row.get('doc_name','')} • sahifa {int(row.get('page_index',0))+1} • {row.get('status','')}")
                except Exception:
                    st.caption("History o‘qilmadi (RLS/DB muammo).")

    st.divider()

    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.05)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.45)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 1.0, 0.1)

    scale = st.slider("PDF render scale:", 1.4, 2.6, PDF_SCALE_DEFAULT, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 120, 40)

    st.markdown("### 🧭 Ko'rinish")
    view_mode = st.radio("Natija ko'rinishi:", ["Yonma-yon", "Tabs"], index=0, horizontal=True)

    force_rerun = st.checkbox("🔁 Oldingi natijani ham qayta hisobla", value=False)


# ==========================================
# 14) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida o‘qing, tarjima qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader("Faylni yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if uploaded_file is None:
    st.stop()

# ==========================================
# FILE LOADED
# ==========================================
if st.session_state.last_fn != uploaded_file.name:
    with st.spinner("Preparing..."):
        file_bytes = uploaded_file.getvalue()
        if uploaded_file.type == "application/pdf":
            pages = render_pdf_pages_to_bytes(file_bytes, max_pages=max_pages, scale=scale)
        else:
            img = Image.open(io.BytesIO(file_bytes))
            pages = [pil_to_jpeg_bytes(img, JPEG_QUALITY_FULL, FULL_MAX_SIDE)]

        st.session_state.page_bytes = pages
        st.session_state.last_fn = uploaded_file.name

        st.session_state.results = {}
        st.session_state.chats = {}
        st.session_state.warn_db = False

        if st.session_state.auth and st.session_state.u_email:
            restored = load_reports(st.session_state.u_email, st.session_state.last_fn)
            if restored:
                st.session_state.results.update(restored)

processed_pages = [
    preprocess_bytes(b, brightness=brightness, contrast=contrast, rotate=rotate, sharpen=sharpen)
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
else:
    page_spec = st.text_input("Sahifalar (masalan: 1-5, 9, 12-20):", value="1")
    selected_indices = parse_pages(page_spec, total_pages)

if not st.session_state.auth and len(selected_indices) > DEMO_LIMIT_PAGES:
    st.warning(f"Demo rejim: maksimal {DEMO_LIMIT_PAGES} sahifa. Premium uchun Email bilan kiring.")
    selected_indices = selected_indices[:DEMO_LIMIT_PAGES]

if not st.session_state.results and selected_indices:
    cols = st.columns(min(len(selected_indices), 4))
    for i, idx in enumerate(selected_indices[:16]):
        with cols[i % min(len(cols), 4)]:
            st.image(processed_pages[idx], caption=f"Varaq {idx+1}", use_container_width=True)


# ==========================================
# RUN ANALYSIS
# ==========================================
if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
    if not selected_indices:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
    hint_era = "" if (auto_detect or era == "Noma'lum") else era
    prompt = build_prompt(hint_lang, hint_era)

    total = len(selected_indices)
    done = 0
    bar = st.progress(0.0)

    for idx in selected_indices:
        # Agar natija bor bo'lsa va force emas -> skip
        if (not force_rerun) and st.session_state.results.get(idx) and not str(st.session_state.results[idx]).startswith("Xato:"):
            done += 1
            bar.progress(done / max(total, 1))
            continue

        reserved = False
        with st.status(f"Sahifa {idx+1}...") as s:
            try:
                # credits only if auth
                if st.session_state.auth:
                    ok = consume_credit_safe(st.session_state.u_email, 1)
                    if not ok:
                        s.update(label="Kredit yetarli emas", state="error")
                        st.warning("Kredit tugagan.")
                        log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "no_credits")
                        done += 1
                        bar.progress(done / max(total, 1))
                        continue
                    reserved = True

                img_bytes = processed_pages[idx]

                # 1-urinish: normal payloads
                payloads = build_payloads_from_page(img_bytes, hi_res=False)
                text = safe_generate([prompt, *payloads], max_tokens=MAX_OUT_TOKENS).strip()

                # Agar bo'limlar chiqmasa yoki translit juda qisqa bo'lsa: HI-RES bilan 1 retry
                if (not has_required_sections(text)) or (translit_length(text) < 250):
                    prompt2 = prompt + "\nMUHIM: Transliteratsiyani maksimal to‘liq yozing; bo‘sh qoldirmang."
                    payloads2 = build_payloads_from_page(img_bytes, hi_res=True)
                    text2 = safe_generate([prompt2, *payloads2], max_tokens=MAX_OUT_TOKENS).strip()
                    if text2 and len(text2) > len(text):
                        text = text2

                if not text:
                    raise RuntimeError("Bo‘sh natija qaytdi.")

                st.session_state.results[idx] = text
                s.update(label="Tayyor!", state="complete")

                if st.session_state.auth:
                    save_report(st.session_state.u_email, st.session_state.last_fn, idx, text)
                    log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "ok")

            except Exception as e:
                if reserved:
                    refund_credit_safe(st.session_state.u_email, 1)
                err_txt = f"Xato: {type(e).__name__}: {e}"
                st.session_state.results[idx] = err_txt
                s.update(label="Xato (refund)", state="error")
                st.error(err_txt)
                if st.session_state.auth:
                    log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "error", note=str(e))

        done += 1
        bar.progress(done / max(total, 1))

    st.success("Tahlil yakunlandi.")
    gc.collect()


# ==========================================
# RESULTS + CHAT + WORD
# ==========================================
if st.session_state.results:
    st.divider()
    keys = sorted(st.session_state.results.keys())

    jump = st.selectbox("⚡ Tez o‘tish (natija bor sahifalar):", options=keys, format_func=lambda x: f"{x+1}-sahifa")
    keys = [jump] + [k for k in keys if k != jump]

    for idx in keys:
        with st.expander(f"📖 Varaq {idx+1}", expanded=True):
            res = st.session_state.results.get(idx, "") or ""

            img_b64 = base64.b64encode(processed_pages[idx]).decode("utf-8")
            img_html = f"""
            <div class="sticky-preview">
              <img src="data:image/jpeg;base64,{img_b64}" alt="page {idx+1}" />
            </div>
            """

            copy_js = f"""
            <button id="copybtn_{idx}" style="
                width:100%;
                padding:10px 12px;
                border-radius:12px;
                border:1px solid rgba(0,0,0,0.12);
                font-weight:900;
                cursor:pointer;
            ">📋 Natijani nusxalash</button>
            <script>
              const txt_{idx} = {html.escape(res)!r};
              document.getElementById("copybtn_{idx}").onclick = async () => {{
                try {{
                  await navigator.clipboard.writeText(txt_{idx});
                  document.getElementById("copybtn_{idx}").innerText = "✅ Nusxalandi";
                  setTimeout(()=>document.getElementById("copybtn_{idx}").innerText="📋 Natijani nusxalash", 1500);
                }} catch(e) {{
                  document.getElementById("copybtn_{idx}").innerText = "❌ Clipboard ruxsat yo‘q";
                }}
              }}
            </script>
            """

            if view_mode == "Tabs":
                tabs = st.tabs(["📷 Rasm", "📝 Natija", "✍️ Tahrir", "💬 Chat"])
                with tabs[0]:
                    st.markdown(img_html, unsafe_allow_html=True)
                with tabs[1]:
                    components.html(copy_js, height=55)
                    components.html(render_result_card(res, C["gold"]), height=620, scrolling=True)
                with tabs[2]:
                    if not st.session_state.auth:
                        st.info("🔒 Tahrir premium. Email bilan kiring.")
                    else:
                        newv = st.text_area("Tahrir:", value=res, height=260, key=f"ed_{idx}")
                        st.session_state.results[idx] = newv
                        save_report(st.session_state.u_email, st.session_state.last_fn, idx, newv)
                with tabs[3]:
                    if not st.session_state.auth:
                        st.info("🔒 Chat premium. Email bilan kiring.")
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
                                        "Quyidagi natija bo‘yicha savolga javob bering.\n"
                                        "Javob o‘zbekcha, aniq va qisqa bo‘lsin.\n\n"
                                        f"NATIJA:\n{res}\n\nSAVOL:\n{user_q}\n"
                                    )
                                    chat_text = safe_generate([chat_prompt], max_tokens=1400).strip()
                                    st.session_state.chats[idx].append({"q": user_q, "a": chat_text})
                                    st.rerun()
            else:
                c1, c2 = st.columns([1, 1.35], gap="large")
                with c1:
                    st.markdown(img_html, unsafe_allow_html=True)
                with c2:
                    components.html(copy_js, height=55)
                    components.html(render_result_card(res, C["gold"]), height=560, scrolling=True)

                    if not st.session_state.auth:
                        st.info("🔒 Word/Tahrir/Chat premium. Email bilan kiring.")
                    else:
                        newv = st.text_area("Tahrir:", value=res, height=220, key=f"ed_side_{idx}")
                        st.session_state.results[idx] = newv
                        save_report(st.session_state.u_email, st.session_state.last_fn, idx, newv)

                        with st.expander("💬 AI Chat (shu varaq bo‘yicha)", expanded=False):
                            st.session_state.chats.setdefault(idx, [])
                            for ch in st.session_state.chats[idx]:
                                st.markdown(f"<div class='chat-user'><b>S:</b> {html.escape(ch['q'])}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div class='chat-ai'><b>AI:</b> {html.escape(ch['a'])}</div>", unsafe_allow_html=True)

                            user_q = st.text_input("Savol bering:", key=f"q_side_{idx}")
                            if st.button(f"So'rash (Varaq {idx+1})", key=f"btn_side_{idx}"):
                                if user_q.strip():
                                    with st.spinner("..."):
                                        chat_prompt = (
                                            "Quyidagi natija bo‘yicha savolga javob bering.\n"
                                            "Javob o‘zbekcha, aniq va qisqa bo‘lsin.\n\n"
                                            f"NATIJA:\n{res}\n\nSAVOL:\n{user_q}\n"
                                        )
                                        chat_text = safe_generate([chat_prompt], max_tokens=1400).strip()
                                        st.session_state.chats[idx].append({"q": user_q, "a": chat_text})
                                        st.rerun()

    # Word export
    if st.session_state.auth and st.session_state.results:
        detected = aggregate_detected_meta(st.session_state.results)
        meta = {
            "Hujjat nomi": st.session_state.last_fn,
            "Til (ko‘p uchragan)": detected["til"] or "Noma'lum",
            "Xat uslubi (ko‘p uchragan)": detected["xat"] or "Noma'lum",
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
