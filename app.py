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
# 2) APP CONSTANTS
# ==========================================
THEME = "DARK_GOLD"
DEMO_LIMIT_PAGES = 3
STARTER_CREDITS = 10
HISTORY_LIMIT = 20

# ✅ TPM/Compute bosimini kamaytirish
MAX_OUT_TOKENS = 1536

# ✅ RPM gate (server process bo'yicha)
GEMINI_RPM_LIMIT = 15
SAFE_RPM = 10           # yanada xavfsiz (taqdimot uchun)
RATE_WINDOW_SEC = 60


# ==========================================
# 3) THEMES
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
  animation: fadeUp .35s ease both;
}}
.sticky-preview img {{
  width: 100%;
  height: 540px;
  object-fit: contain;
  display: block;
}}

@keyframes fadeUp {{
  from {{ opacity: 0; transform: translateY(10px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 5) SERVICES
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# ✅ siz xohlagan alias
model = genai.GenerativeModel(model_name="gemini-flash-latest")


# ========= Global Rate Limiter (process-wide) =========
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

                sleep_for = (self.window - (now - self.ts[0])) + 0.10
            time.sleep(max(0.25, sleep_for))

@st.cache_resource
def get_rate_limiter():
    return RateLimiter(rpm=SAFE_RPM, window_sec=RATE_WINDOW_SEC)

rate_limiter = get_rate_limiter()

# ==========================================
# 6) STATE
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""
if "last_fn" not in st.session_state: st.session_state.last_fn = None

if "page_bytes" not in st.session_state: st.session_state.page_bytes = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}
if "warn_db" not in st.session_state: st.session_state.warn_db = False


# ==========================================
# 7) HELPERS (rasmni yengillashtirdik)
# ==========================================
def pil_to_jpeg_bytes(img: Image.Image, quality: int = 72, max_side: int = 1500) -> bytes:
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
            out.append(pil_to_jpeg_bytes(pil_img))
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

    return pil_to_jpeg_bytes(img)

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

def build_single_prompt(hint_lang: str, hint_era: str) -> str:
    hl = hint_lang or "yo‘q"
    he = hint_era or "yo‘q"
    return (
        "Siz qo‘lyozma o‘qish va tarjima bo‘yicha mutaxassissiz.\n"
        "Vazifa: rasm ichidagi matnni o‘qing va faqat quyidagi bo‘limlarda chiqaring.\n\n"
        "QOIDALAR:\n"
        "- Hech narsa uydirmang.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Ism/son/sana/joy nomlarini aynan matndek saqlang.\n"
        "- Transliteratsiya satrma-satr bo‘lsin.\n"
        "- Tarjima oddiy o‘zbekcha, to‘liq.\n\n"
        f"HINTLAR: til='{hl}', xat uslubi='{he}'. Agar hint 'yo‘q' bo‘lsa, o‘zingiz aniqlang.\n\n"
        "FORMAT (ANIQ SHU TARTIBDA):\n"
        "0) Tashxis:\n"
        "Til: <aniqlangan til yoki Noma'lum>\n"
        "Xat uslubi: <aniqlangan xat yoki Noma'lum>\n"
        "Ishonchlilik: <Yuqori/O‘rtacha/Past>\n\n"
        "1) Transliteratsiya:\n"
        "<satrma-satr matn>\n\n"
        "2) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<oddiy o‘zbekcha, to‘liq>\n\n"
        "6) Izoh:\n"
        "<kontekst va noaniqliklar; ehtiyotkor izoh>\n"
    )

def call_gemini_with_retry(prompt: str, payloads: list[dict], tries: int = 7) -> str:
    """
    ✅ Rate limiter + backoff.
    """
    last_err = None
    for attempt in range(tries):
        try:
            rate_limiter.wait_for_slot()
            resp = model.generate_content(
                [prompt, *payloads],
                generation_config={"max_output_tokens": MAX_OUT_TOKENS, "temperature": 0.2}
            )
            return getattr(resp, "text", "") or ""
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if ("429" in msg) or ("rate" in msg) or ("quota" in msg) or ("exhaust" in msg):
                base = min(60, (2 ** attempt))
                time.sleep(base + random.uniform(0.8, 2.0))
                continue
            raise
    raise RuntimeError("So'rovlar ko'p (429). Keyinroq qayta urinib ko'ring.") from last_err


# ==========================================
# 8) DB helpers (sizdagi kabi)
# ==========================================
def ensure_profile(email: str) -> None:
    try:
        existing = db.table("profiles").select("email,credits").eq("email", email).limit(1).execute()
        if existing.data:
            return
        db.table("profiles").insert({"email": email, "credits": STARTER_CREDITS}).execute()
    except Exception:
        st.session_state.warn_db = True

def get_credits(email: str) -> int:
    try:
        r = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(r.data["credits"]) if r.data and "credits" in r.data else 0
    except Exception:
        st.session_state.warn_db = True
        return 0

def consume_credit_safe(email: str, n: int = 1) -> bool:
    try:
        r = db.rpc("consume_credits", {"p_email": email, "p_n": n}).execute()
        return bool(r.data)
    except Exception:
        pass

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
    try:
        db.rpc("refund_credits", {"p_email": email, "p_n": n}).execute()
        return
    except Exception:
        pass

    for _ in range(2):
        try:
            cur = get_credits(email)
            upd = db.table("profiles").update({"credits": cur + n}).eq("email", email).eq("credits", cur).execute()
            if upd.data:
                return
        except Exception:
            st.session_state.warn_db = True
            return

def log_usage(email: str, doc_name: str, page_index: int, status: str, note: str = "") -> None:
    try:
        db.table("usage_logs").insert({
            "email": email,
            "doc_name": doc_name,
            "page_index": page_index,
            "status": status,
            "note": note[:240],
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        st.session_state.warn_db = True

def save_report(email: str, doc_name: str, page_index: int, result_text: str) -> None:
    try:
        db.table("reports").upsert(
            {"email": email, "doc_name": doc_name, "page_index": page_index,
             "result_text": result_text, "updated_at": datetime.utcnow().isoformat()},
            on_conflict="email,doc_name,page_index"
        ).execute()
    except Exception:
        st.session_state.warn_db = True

def load_reports(email: str, doc_name: str) -> dict:
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
# 9) WORD EXPORT (sizdagi kabi)
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

def build_word_report(app_name: str, meta: dict, pages: dict[int, str]) -> bytes:
    doc = Document()
    _doc_set_normal_style(doc)
    _add_cover(doc, app_name, "Hisobot (Tarjima + Izoh)")
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
# 10) SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)

    st.markdown("### ✉️ Email bilan kirish")
    st.caption("Email kiriting — kreditlar va premium funksiyalar ochiladi.")

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
        ">
          <div style="font-weight:900; color:{C["gold"]}; font-size:14px;">👤 Profil</div>
          <div style="color:{C["text"]}; margin-top:6px; font-weight:900;">{html.escape(st.session_state.u_email)}</div>
          <div style="margin-top:8px; color:{C["muted"]};">Kreditlar: <span style="color:{C["gold"]}; font-weight:900;">{credits}</span> sahifa</div>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state.warn_db:
            st.warning("DB yoki RPC’da vaqtinchalik muammo bo‘lishi mumkin (fallback ishlayapti).")

        if st.button("🚪 CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = ""
            st.rerun()

        with st.expander(f"🧾 History (oxirgi {HISTORY_LIMIT})", expanded=False):
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
                st.caption("History o‘qilmadi (policy/RLS yoki DB muammo).")

    st.divider()

    st.markdown("### 🧠 Hintlar")
    auto_detect = st.checkbox("🧠 Avto aniqlash (tavsiya)", value=True)
    lang = st.selectbox("Taxminiy matn tili (hint):", ["Noma'lum", "Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"], index=0)
    era = st.selectbox("Taxminiy xat uslubi (hint):", ["Noma'lum", "Nasta'liq", "Suls", "Riq'a", "Kufiy"], index=0)

    st.markdown("### 🧪 Skan sozlamalari")
    rotate = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.35)
    sharpen = st.slider("Sharpen:", 0.0, 1.5, 0.9, 0.1)

    # ✅ scale default pasaytirildi
    scale = st.slider("PDF render scale:", 1.2, 2.4, 1.5, 0.1)
    max_pages = st.slider("Preview max sahifa:", 1, 60, 30)

    st.markdown("### 🧭 Ko'rinish")
    view_mode = st.radio("Natija ko'rinishi:", ["Yonma-yon", "Tabs"], index=0, horizontal=True)


# ==========================================
# 11) MAIN
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

uploaded_file = st.file_uploader(
    "Faylni yuklang",
    type=["pdf", "png", "jpg", "jpeg"],
    label_visibility="collapsed"
)

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
            pages = [pil_to_jpeg_bytes(img)]

        st.session_state.page_bytes = pages
        st.session_state.last_fn = uploaded_file.name

        st.session_state.results = {}
        st.session_state.chats = {}
        st.session_state.warn_db = False
        gc.collect()

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
    st.warning(f"Demo rejim: maksimal {DEMO_LIMIT_PAGES} sahifa tahlil qilinadi. Premium uchun Email bilan kiring.")
    selected_indices = selected_indices[:DEMO_LIMIT_PAGES]


# ==========================================
# RUN analysis (✅ 1 request per page)
# ==========================================
if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
    if not selected_indices:
        st.warning("Avval sahifani tanlang.")
        st.stop()

    hint_lang = "" if (auto_detect or lang == "Noma'lum") else lang
    hint_era  = "" if (auto_detect or era == "Noma'lum") else era

    prompt = build_single_prompt(hint_lang, hint_era)

    total = len(selected_indices)
    done = 0
    bar = st.progress(0.0)

    for idx in selected_indices:
        # ✅ natija bor bo'lsa, qayta request yubormaymiz
        if st.session_state.results.get(idx) and not str(st.session_state.results[idx]).startswith("Xato:"):
            done += 1
            bar.progress(done / max(total, 1))
            continue

        reserved = False

        with st.status(f"Sahifa {idx+1}...") as s:
            try:
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
                payload = {"mime_type": "image/jpeg", "data": base64.b64encode(img_bytes).decode("utf-8")}

                result_text = call_gemini_with_retry(prompt, [payload], tries=7).strip()
                if not result_text:
                    raise RuntimeError("Bo‘sh natija qaytdi.")

                st.session_state.results[idx] = result_text
                s.update(label="Tayyor!", state="complete")

                if st.session_state.auth:
                    save_report(st.session_state.u_email, st.session_state.last_fn, idx, result_text)
                    log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "ok")

            except Exception as e:
                if reserved:
                    refund_credit_safe(st.session_state.u_email, 1)
                err_txt = f"Xato: {type(e).__name__}: {e}"
                st.session_state.results[idx] = err_txt
                s.update(label="Xato", state="error")
                st.error(err_txt)
                if st.session_state.auth:
                    log_usage(st.session_state.u_email, st.session_state.last_fn, idx, "error", note=str(e))

        done += 1
        bar.progress(done / max(total, 1))

    st.success("Tahlil yakunlandi.")
    gc.collect()


# ==========================================
# RESULTS + CHAT
# ==========================================
if st.session_state.results:
    st.divider()

    for idx in sorted(st.session_state.results.keys()):
        res = st.session_state.results.get(idx, "") or ""

        with st.expander(f"📖 Varaq {idx+1}", expanded=True):
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
                tabs = st.tabs(["📷 Rasm", "📝 Natija", "💬 Chat"])
                with tabs[0]:
                    st.markdown(img_html, unsafe_allow_html=True)
                with tabs[1]:
                    components.html(copy_js, height=55)
                    st.text_area("Natija:", value=res, height=360, key=f"res_{idx}")
                with tabs[2]:
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
                                        "Quyidagi matn bo‘yicha savolga javob ber.\n"
                                        "Javobni o‘zbekcha, aniq va qisqa yoz.\n\n"
                                        f"MATN:\n{res}\n\nSAVOL:\n{user_q}\n"
                                    )
                                    chat_text = call_gemini_with_retry(chat_prompt, [], tries=7).strip()
                                    st.session_state.chats[idx].append({"q": user_q, "a": chat_text})
                                    st.rerun()
            else:
                c1, c2 = st.columns([1, 1.35], gap="large")
                with c1:
                    st.markdown(img_html, unsafe_allow_html=True)
                with c2:
                    components.html(copy_js, height=55)
                    st.text_area("Natija:", value=res, height=420, key=f"res2_{idx}")

    # Word export (oddiy)
    if st.session_state.auth and st.session_state.results:
        meta = {
            "Hujjat nomi": st.session_state.last_fn,
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
