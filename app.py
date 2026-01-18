# app.py
# Manuscript AI Center — Email-only MVP (no password, no Google)
# Focus: maximum transcription+translation coverage (no summarization truncation)

import os
import io
import re
import time
import math
import random
import base64
import datetime as dt
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

import streamlit as st
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

# Optional: pdf -> images
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except Exception:
    HAS_FITZ = False

# Supabase
try:
    from supabase import create_client
    HAS_SUPABASE = True
except Exception:
    HAS_SUPABASE = False

# Gemini
try:
    import google.generativeai as genai
    HAS_GEMINI = True
except Exception:
    HAS_GEMINI = False


# =========================
# 0) CONFIG
# =========================

APP_TITLE = "Manuscript AI Center"
FREE_DEMO_MAX_PAGES = 3          # login bo‘lmasa demo limit
NEW_USER_FREE_CREDITS = 10       # email kiritib login qilganda beriladigan starter kredit
HISTORY_LIMIT = 20

# Image tiling defaults (accuracy first)
STRIPS_PER_PAGE_DEFAULT = 10     # 9-12 oralig‘ida yaxshi; 10 — balans
STRIP_OVERLAP = 0.12             # overlap qamrovni oshiradi
OCR_IMAGE_MAX_SIDE = 3400        # mayda matn uchun kattaroq

# Translation chunking
TRANSLIT_CHUNK_CHARS = 2200      # juda uzun matnni kesib yubormaslik uchun
TRANSLIT_CHUNK_OVERLAP = 120

# Retry / validation
OCR_TRIES = 2
TRANSLATION_TRIES = 2

# Delay tuning (429 kamaytirish)
DELAY_MIN = 0.55
DELAY_MAX = 1.15


# =========================
# 1) STYLE
# =========================

def inject_css():
    st.markdown(
        """
        <style>
          .block-container { padding-top: 1.2rem; padding-bottom: 2.4rem; }
          .premium-card {
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.04);
            border-radius: 16px;
            padding: 14px 14px;
          }
          .soft-card {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 12px 12px;
          }
          .muted { opacity: 0.8; font-size: 0.92rem; }
          .tiny { opacity: 0.75; font-size: 0.85rem; }
          .badge {
            display:inline-block; padding: 2px 8px;
            border-radius: 999px; font-size: 0.85rem;
            border: 1px solid rgba(255,255,255,0.14);
            background: rgba(255,255,255,0.06);
          }
          .kpi {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            border-radius: 14px;
            padding: 10px 12px;
          }
          .result-wrap {
            border: 1px solid rgba(255,255,255,0.10);
            background: rgba(255,255,255,0.03);
            border-radius: 18px;
            padding: 16px 16px;
          }
          .hr { height: 1px; background: rgba(255,255,255,0.10); margin: 10px 0; }
        </style>
        """,
        unsafe_allow_html=True
    )


# =========================
# 2) SECRETS / CLIENTS
# =========================

def get_secret(key: str, default: str = "") -> str:
    # Prefer st.secrets, fallback to env
    v = ""
    try:
        v = st.secrets.get(key, "")
    except Exception:
        v = ""
    if not v:
        v = os.environ.get(key, default)
    return v or default


SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")

MODEL_OCR = get_secret("GEMINI_MODEL_OCR", "gemini-1.5-flash-latest")
MODEL_TXT = get_secret("GEMINI_MODEL_TXT", "gemini-1.5-pro-latest")


@st.cache_resource
def get_supabase_client():
    if not HAS_SUPABASE:
        return None
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_resource
def get_gemini_models():
    if not HAS_GEMINI:
        return None, None
    if not GEMINI_API_KEY:
        return None, None
    genai.configure(api_key=GEMINI_API_KEY)
    # Two models: OCR image -> fast, translate -> accurate
    try:
        ocr = genai.GenerativeModel(MODEL_OCR)
    except Exception:
        ocr = genai.GenerativeModel("gemini-1.5-flash-latest")
    try:
        txt = genai.GenerativeModel(MODEL_TXT)
    except Exception:
        txt = genai.GenerativeModel(MODEL_OCR)
    return ocr, txt


sb = get_supabase_client()
ocr_model, txt_model = get_gemini_models()


# =========================
# 3) UTIL: VALIDATION
# =========================

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def is_valid_email(email: str) -> bool:
    return bool(email and EMAIL_RE.match(email.strip().lower()))

def now_iso() -> str:
    return dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat()

def short_sleep():
    time.sleep(DELAY_MIN + random.random() * (DELAY_MAX - DELAY_MIN))

def safe_text(x) -> str:
    return (x or "").strip()

def clamp(n: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, n))


# =========================
# 4) IMAGE PREPROCESS
# =========================

def pil_to_jpeg_bytes(img: Image.Image, quality: int = 92, max_side: int = 3200) -> bytes:
    img = img.convert("RGB")
    w, h = img.size
    scale = min(1.0, float(max_side) / float(max(w, h)))
    if scale < 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    bio = io.BytesIO()
    img.save(bio, format="JPEG", quality=quality, optimize=True)
    return bio.getvalue()

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    # Gentle but effective pipeline for scanned manuscripts
    im = img.convert("L")
    im = ImageOps.autocontrast(im)
    im = im.filter(ImageFilter.MedianFilter(size=3))
    im = ImageEnhance.Contrast(im).enhance(1.25)
    im = ImageEnhance.Sharpness(im).enhance(1.15)
    return im.convert("RGB")


# =========================
# 5) PDF -> PAGES
# =========================

def pdf_to_images(pdf_bytes: bytes, zoom: float = 2.0) -> List[Image.Image]:
    if not HAS_FITZ:
        raise RuntimeError("PyMuPDF (fitz) o‘rnatilmagan. PDF sahifalarni ajratib bo‘lmaydi.")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    mat = fitz.Matrix(zoom, zoom)
    for i in range(doc.page_count):
        p = doc.load_page(i)
        pix = p.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        pages.append(img)
    return pages


# =========================
# 6) OCR TILING (CHAP/ONG + STRIPS)
# =========================

def split_into_pages(pil_img: Image.Image) -> List[Image.Image]:
    """Agar skan 2 bet bo‘lsa, chap/o‘ngga ajratadi."""
    w, h = pil_img.size
    # heuristic: wide image likely contains two pages
    if w >= int(h * 1.15):
        mid = w // 2
        left = pil_img.crop((0, 0, mid, h))
        right = pil_img.crop((mid, 0, w, h))
        return [left, right]
    return [pil_img]

def split_vertical_strips(pil_img: Image.Image, n: int = STRIPS_PER_PAGE_DEFAULT, overlap: float = STRIP_OVERLAP) -> List[Image.Image]:
    """Bitta betni yuqoridan pastga n ta bo‘lak (strip) qilib bo‘ladi."""
    w, h = pil_img.size
    strips = []
    step = h / n
    ov = int(step * overlap)
    for i in range(n):
        y0 = max(0, int(i * step) - ov)
        y1 = min(h, int((i + 1) * step) + ov)
        strips.append(pil_img.crop((0, y0, w, y1)))
    return strips

def pil_to_payload(img: Image.Image) -> Dict:
    jb = pil_to_jpeg_bytes(img, quality=92, max_side=OCR_IMAGE_MAX_SIDE)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(jb).decode("utf-8")}

def must_have_translit(text: str) -> bool:
    t = safe_text(text)
    # coverage check — very rough but works well in practice
    if len(t) < 1200:
        return False
    # must contain multiple lines or markers
    lines = [ln for ln in t.splitlines() if ln.strip()]
    if len(lines) < 10:
        return False
    return True

def call_gemini_image(prompt: str, img_payload: Dict, tries: int = 4) -> str:
    if not ocr_model:
        raise RuntimeError("Gemini OCR model topilmadi. GEMINI_API_KEY ni tekshiring.")
    last_err = None
    for _ in range(tries):
        try:
            resp = ocr_model.generate_content([prompt, img_payload])
            txt = getattr(resp, "text", "") or ""
            txt = txt.strip()
            if txt:
                return txt
        except Exception as e:
            last_err = e
            short_sleep()
    raise RuntimeError(f"Gemini OCR xato: {last_err}")

def transcribe_full_page_from_image(pil_img: Image.Image, tries: int = OCR_TRIES) -> str:
    TRANSCRIBE_PROMPT = (
        "Siz paleograf-ekspertsiz. VAZIFA: faqat o‘qish (transliteratsiya).\n"
        "Qoidalar:\n"
        "- Hech qachon qisqartirmang, xulosa qilmang.\n"
        "- Matnni tartib bilan yozing.\n"
        "- O‘qilmagan joy: [o‘qilmadi] yoki [?].\n"
        "- Har satr alohida satrda bo‘lsin (line breaks saqlansin).\n"
        "- Tarjima qilmang.\n"
        "Natija faqat matn bo‘lsin (hech qanday izoh/sarlavha shart emas).\n"
    )

    last = ""
    for attempt in range(tries):
        pages = split_into_pages(pil_img)
        out_parts = []

        # Retry strategiya: 2-urinishda strip sonini oshiramiz
        strips_n = STRIPS_PER_PAGE_DEFAULT if attempt == 0 else clamp(STRIPS_PER_PAGE_DEFAULT + 3, 9, 14)

        for p_i, p in enumerate(pages, start=1):
            strips = split_vertical_strips(p, n=strips_n, overlap=STRIP_OVERLAP)
            for s_i, strip in enumerate(strips, start=1):
                payload = pil_to_payload(strip)
                txt = call_gemini_image(
                    f"{TRANSCRIBE_PROMPT}\n(Bet {p_i}, Bo‘lak {s_i}/{len(strips)})",
                    payload,
                    tries=4
                )
                out_parts.append(txt.strip())
                short_sleep()

        joined = "\n".join([x for x in out_parts if x])
        last = joined
        if must_have_translit(joined):
            return joined

    return last


# =========================
# 7) TRANSLATION (TEXT-ONLY, CHUNKED) + VALIDATOR
# =========================

def chunk_text(text: str, chunk_chars: int = TRANSLIT_CHUNK_CHARS, overlap: int = TRANSLIT_CHUNK_OVERLAP) -> List[str]:
    t = safe_text(text)
    if len(t) <= chunk_chars:
        return [t]
    chunks = []
    i = 0
    while i < len(t):
        j = min(len(t), i + chunk_chars)
        chunks.append(t[i:j])
        if j >= len(t):
            break
        i = max(0, j - overlap)
    return chunks

def call_gemini_text(prompt: str, content: str, tries: int = 3) -> str:
    if not txt_model:
        raise RuntimeError("Gemini TXT model topilmadi. GEMINI_API_KEY ni tekshiring.")
    last_err = None
    for _ in range(tries):
        try:
            resp = txt_model.generate_content([prompt, content])
            txt = getattr(resp, "text", "") or ""
            txt = txt.strip()
            if txt:
                return txt
        except Exception as e:
            last_err = e
            short_sleep()
    raise RuntimeError(f"Gemini TEXT xato: {last_err}")

def translation_validator(translit: str, translation: str) -> bool:
    tr = safe_text(translation)
    tl = safe_text(translit)
    if len(tr) < 400:
        return False
    # line coverage heuristic
    tl_lines = [x for x in tl.splitlines() if x.strip()]
    tr_lines = [x for x in tr.splitlines() if x.strip()]
    if len(tl_lines) >= 20 and len(tr_lines) < max(12, int(len(tl_lines) * 0.35)):
        return False
    return True

def translate_and_comment(translit: str) -> str:
    """
    Output ONLY:
    1) To‘g‘ridan-to‘g‘ri tarjima (to‘liq, satrma-satr)
    2) Izoh (ehtiyotkor, uydirma qilmasin)
    """
    BASE_PROMPT = (
        "Siz qadimiy qo‘lyozmalar tarjimoni va tarixiy matnlar bilan ishlaydigan mutaxassisiz.\n"
        "Sizga TRANSLITERATSIYA MATNI beriladi.\n\n"
        "Qoidalar (qat’iy):\n"
        "- QISQARTIRMA! XULOSA QILMA! Matnni to‘liq tarjima qil.\n"
        "- O‘qilmagan joyni taxmin qilma: [o‘qilmadi] yoki [?] ni saqla.\n"
        "- Ism/son/sana: faqat ko‘ringanini tarjima qil, uydirma qilma.\n"
        "- Tarjima oddiy o‘zbekchada bo‘lsin, satrma-satr (strukturani saqla).\n"
        "- Keyin alohida 'Izoh' bo‘limida kontekst va tushuntirish ber, lekin aniq bo‘lmasa ehtiyotkor yoz.\n\n"
        "Natija formati (aniq):\n"
        "1) To‘g‘ridan-to‘g‘ri tarjima:\n"
        "<TO‘LIQ TARJIMA>\n\n"
        "2) Izoh:\n"
        "<IZOH>\n"
    )

    # Chunk translate to avoid truncation
    chunks = chunk_text(translit)
    translated_chunks = []

    for idx, ch in enumerate(chunks, start=1):
        prompt = BASE_PROMPT + f"\n(Bo‘lak {idx}/{len(chunks)})"
        part = call_gemini_text(prompt, f"TRANSLITERATSIYA:\n{ch}", tries=3)
        translated_chunks.append(part)
        short_sleep()

    combined = "\n\n".join(translated_chunks).strip()

    # Validator + retry (stronger prompt)
    if not translation_validator(translit, combined):
        STRONG_PROMPT = (
            BASE_PROMPT
            + "\nQo‘shimcha qat’iy talab:\n"
              "- Agar matn uzun bo‘lsa ham, tarjimani davom ettir.\n"
              "- Hech qachon 2-3 jumlaga tushirib yuborma.\n"
              "- Bo‘laklar bo‘yicha to‘liq tarjima ber.\n"
        )
        translated_chunks = []
        for idx, ch in enumerate(chunks, start=1):
            part = call_gemini_text(STRONG_PROMPT + f"\n(Bo‘lak {idx}/{len(chunks)})",
                                    f"TRANSLITERATSIYA:\n{ch}", tries=3)
            translated_chunks.append(part)
            short_sleep()
        combined = "\n\n".join(translated_chunks).strip()

    return combined


# =========================
# 8) SUPABASE DATA (profiles / credits / reports / usage_logs)
# =========================

@dataclass
class Profile:
    email: str
    credits: int

def sb_require():
    if not sb:
        raise RuntimeError("Supabase client topilmadi. SUPABASE_URL va SUPABASE_KEY ni tekshiring.")

def sb_get_or_create_profile(email: str) -> Profile:
    sb_require()
    email = email.strip().lower()

    res = sb.table("profiles").select("email, credits").eq("email", email).limit(1).execute()
    data = getattr(res, "data", None) or []
    if data:
        return Profile(email=email, credits=int(data[0].get("credits") or 0))

    # create new
    sb.table("profiles").insert({"email": email, "credits": NEW_USER_FREE_CREDITS}).execute()
    return Profile(email=email, credits=NEW_USER_FREE_CREDITS)

def sb_set_credits(email: str, credits: int) -> int:
    sb_require()
    email = email.strip().lower()
    res = sb.table("profiles").update({"credits": int(credits)}).eq("email", email).execute()
    data = getattr(res, "data", None) or []
    if data:
        return int(data[0].get("credits") or credits)
    return int(credits)

def sb_consume_credits(email: str, n: int = 1) -> int:
    """
    Preferred: RPC consume_credits(p_email text, p_n int)
    Fallback: atomic update with "credits = credits - n" and check in app.
    Returns updated credits (may be negative if you bypass checks; we won't).
    """
    sb_require()
    email = email.strip().lower()
    n = int(n)

    # Try RPC if exists
    try:
        # expected function: public.consume_credits(p_email text, p_n int default 1) returns table (credits int)
        resp = sb.rpc("consume_credits", {"p_email": email, "p_n": n}).execute()
        data = getattr(resp, "data", None)
        if isinstance(data, list) and data and "credits" in data[0]:
            return int(data[0]["credits"])
        if isinstance(data, dict) and "credits" in data:
            return int(data["credits"])
    except Exception:
        pass

    # Fallback: read current then update
    cur = sb_get_or_create_profile(email).credits
    newv = cur - n
    sb_set_credits(email, newv)
    return newv

def sb_refund_credits(email: str, n: int = 1) -> int:
    sb_require()
    email = email.strip().lower()
    n = int(n)
    try:
        resp = sb.rpc("refund_credits", {"p_email": email, "p_n": n}).execute()
        data = getattr(resp, "data", None)
        if isinstance(data, list) and data and "credits" in data[0]:
            return int(data[0]["credits"])
        if isinstance(data, dict) and "credits" in data:
            return int(data["credits"])
    except Exception:
        pass
    cur = sb_get_or_create_profile(email).credits
    newv = cur + n
    sb_set_credits(email, newv)
    return newv

def sb_insert_report(email: str, doc_name: str, page_index: int, result_text: str):
    sb_require()
    sb.table("reports").insert({
        "email": email.strip().lower(),
        "doc_name": doc_name,
        "page_index": int(page_index),
        "result_text": result_text,
        "created_at": now_iso(),
    }).execute()

def sb_insert_usage_log(email: str, filename: str, page_index: int, status: str, latency_ms: int, note: str = ""):
    sb_require()
    sb.table("usage_logs").insert({
        "email": email.strip().lower(),
        "filename": filename,
        "page_index": int(page_index),
        "status": status,
        "latency_ms": int(latency_ms),
        "note": note[:240],
        "created_at": now_iso(),
    }).execute()

def sb_fetch_history(email: str, limit: int = HISTORY_LIMIT) -> List[Dict]:
    sb_require()
    res = sb.table("reports").select("id, doc_name, page_index, created_at, result_text").eq("email", email.strip().lower()).order("created_at", desc=True).limit(limit).execute()
    return getattr(res, "data", None) or []


# =========================
# 9) SESSION
# =========================

def ss_init():
    st.session_state.setdefault("email", "")
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("credits", 0)
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("results", {})  # page_index -> result text
    st.session_state.setdefault("translit_cache", {})  # page_index -> translit
    st.session_state.setdefault("active_page_idx", 0)
    st.session_state.setdefault("demo_pages_used", 0)

def do_login(email: str):
    email = email.strip().lower()
    st.session_state["email"] = email
    st.session_state["logged_in"] = True
    if sb:
        prof = sb_get_or_create_profile(email)
        st.session_state["credits"] = prof.credits
        st.session_state["history"] = sb_fetch_history(email, HISTORY_LIMIT)
    else:
        st.session_state["credits"] = 0
        st.session_state["history"] = []

def do_logout():
    st.session_state["email"] = ""
    st.session_state["logged_in"] = False
    st.session_state["credits"] = 0
    st.session_state["history"] = []
    st.session_state["results"] = {}
    st.session_state["translit_cache"] = {}
    st.session_state["active_page_idx"] = 0
    st.session_state["demo_pages_used"] = 0


# =========================
# 10) UI: SIDEBAR (Email-only)
# =========================

def sidebar_auth():
    st.sidebar.markdown(f"## {APP_TITLE}")

    # Status badges
    if st.session_state["logged_in"]:
        st.sidebar.markdown(f"<span class='badge'>✅ Logged in</span>", unsafe_allow_html=True)
    else:
        st.sidebar.markdown(f"<span class='badge'>🟡 Demo</span>", unsafe_allow_html=True)

    st.sidebar.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    email_in = st.sidebar.text_input("Email", value=st.session_state.get("email", ""), placeholder="example@mail.com")
    colA, colB = st.sidebar.columns([1, 1])

    with colA:
        if st.button("KIRISH", use_container_width=True):
            if not is_valid_email(email_in):
                st.sidebar.error("Email noto‘g‘ri ko‘rinadi.")
            else:
                do_login(email_in)
                st.rerun()

    with colB:
        if st.button("CHIQISH", use_container_width=True):
            do_logout()
            st.rerun()

    # Profile card
    if st.session_state["logged_in"]:
        st.sidebar.markdown(
            f"""
            <div class="soft-card">
              <div><b>{st.session_state["email"]}</b></div>
              <div class="muted">Kredit: <b>{st.session_state["credits"]}</b></div>
              <div class="tiny">Premium: Word • Tahrir • Chat • History • Save results</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.sidebar.markdown(
            f"""
            <div class="soft-card">
              <div><b>Demo rejim</b></div>
              <div class="muted">Login bo‘lmasa: <b>{FREE_DEMO_MAX_PAGES}</b> sahifa limit</div>
              <div class="tiny">Email kiriting → {NEW_USER_FREE_CREDITS} kredit bilan boshlaysiz</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.sidebar.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    # History
    if st.session_state["logged_in"] and sb:
        st.sidebar.markdown("### 🗂 History (oxirgi 20)")
        q = st.sidebar.text_input("History qidirish", value="", placeholder="keyword...")
        hist = st.session_state.get("history", []) or []
        if q.strip():
            ql = q.strip().lower()
            hist = [h for h in hist if ql in (h.get("doc_name","").lower() + " " + (h.get("result_text","").lower()))]

        if not hist:
            st.sidebar.caption("History yo‘q yoki topilmadi.")
        else:
            for h in hist[:HISTORY_LIMIT]:
                title = f"{h.get('doc_name','doc')} • varaq {int(h.get('page_index',0))+1}"
                if st.sidebar.button(title, use_container_width=True):
                    st.session_state["active_page_idx"] = int(h.get("page_index", 0))
                    st.session_state["results"][int(h.get("page_index",0))] = h.get("result_text","")
                    st.rerun()


# =========================
# 11) MAIN: CORE FLOW
# =========================

def requirements_guard():
    missing = []
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        missing.append("SUPABASE_KEY")
    if missing:
        st.error("Secrets yetishmayapti: " + ", ".join(missing))
        st.stop()
    if not HAS_GEMINI:
        st.error("google-generativeai kutubxonasi topilmadi.")
        st.stop()
    if not HAS_SUPABASE:
        st.warning("supabase-py topilmadi. DB funksiyalar (kredit/history/save) ishlamasligi mumkin.")

def premium_banner():
    st.markdown(
        """
        <div class="premium-card">
          <div><b>🔒 Premium funksiyalar</b></div>
          <div class="muted">Demo rejimda natijani ko‘rishingiz mumkin. To‘liq funksiyalar uchun email bilan tizimga kiring.</div>
          <div class="tiny">Word hisobot • Tahrir • AI Chat • History • Save results</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def file_uploader_block():
    st.markdown("### 📄 Fayl yuklash")
    up = st.file_uploader("PDF yoki rasm (PNG/JPG)", type=["pdf", "png", "jpg", "jpeg"])
    return up

def build_pages_from_upload(uploaded) -> Tuple[List[Image.Image], str]:
    filename = uploaded.name
    data = uploaded.read()

    if filename.lower().endswith(".pdf"):
        if not HAS_FITZ:
            raise RuntimeError("PDF uchun PyMuPDF (fitz) kerak.")
        pages = pdf_to_images(data, zoom=2.0)
        return pages, filename

    # image
    img = Image.open(io.BytesIO(data)).convert("RGB")
    return [img], filename

def show_page_preview(pages: List[Image.Image], idx: int):
    idx = clamp(idx, 0, len(pages)-1)
    st.image(pages[idx], caption=f"Varaq {idx+1}", use_container_width=True)

def render_copy_button(text: str, key: str):
    # Streamlit clipboard: use st.code + small JS
    st.code(text, language="markdown")
    b64 = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    st.components.v1.html(
        f"""
        <button style="
          padding:8px 12px;border-radius:10px;border:1px solid rgba(255,255,255,0.18);
          background:rgba(255,255,255,0.06);color:white;cursor:pointer;"
          onclick="navigator.clipboard.writeText(atob('{b64}'));"
        >📋 Copy</button>
        """,
        height=52
    )

def can_user_analyze(n_pages: int) -> Tuple[bool, str]:
    if st.session_state["logged_in"]:
        # must have credits
        if sb:
            credits = int(st.session_state.get("credits", 0))
            if credits < n_pages:
                return False, f"Kredit yetarli emas. Sizda {credits}, kerak {n_pages}."
        return True, ""
    else:
        # demo
        used = int(st.session_state.get("demo_pages_used", 0))
        remaining = FREE_DEMO_MAX_PAGES - used
        if n_pages > remaining:
            return False, f"Demo limit: yana {remaining} sahifa qoldi. Email bilan kiring."
        return True, ""

def consume_for_analysis(n_pages: int):
    if st.session_state["logged_in"] and sb:
        email = st.session_state["email"]
        # pre-check in app
        if st.session_state["credits"] < n_pages:
            raise RuntimeError("Kredit yetarli emas.")
        newc = sb_consume_credits(email, n_pages)
        st.session_state["credits"] = newc
    else:
        st.session_state["demo_pages_used"] = int(st.session_state.get("demo_pages_used", 0)) + n_pages

def refund_for_failure(n_pages: int):
    if st.session_state["logged_in"] and sb:
        email = st.session_state["email"]
        newc = sb_refund_credits(email, n_pages)
        st.session_state["credits"] = newc
    else:
        st.session_state["demo_pages_used"] = max(0, int(st.session_state.get("demo_pages_used", 0)) - n_pages)

def analyze_page(pil_img: Image.Image, filename: str, page_index: int) -> Tuple[str, str]:
    """
    Returns: (result_text, translit_text)
    """
    t0 = time.time()

    # preprocess -> tiling OCR
    proc = preprocess_for_ocr(pil_img)
    translit = transcribe_full_page_from_image(proc, tries=OCR_TRIES)

    if not safe_text(translit):
        raise RuntimeError("Transliteratsiya bo‘sh chiqdi (OCR coverage past).")

    # translation + izoh (text-only)
    result = translate_and_comment(translit)

    if not safe_text(result):
        raise RuntimeError("Tarjima natijasi bo‘sh chiqdi.")

    latency = int((time.time() - t0) * 1000)

    # DB save
    if st.session_state["logged_in"] and sb:
        email = st.session_state["email"]
        try:
            sb_insert_report(email, filename, page_index, result)
        except Exception:
            pass
        try:
            sb_insert_usage_log(email, filename, page_index, "ok", latency, note="analyze")
        except Exception:
            pass

    return result, translit


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_css()
    ss_init()
    requirements_guard()

    sidebar_auth()

    # Header
    st.markdown(f"# {APP_TITLE}")
    st.caption("Qadimiy hujjatlarni yuklang va AI yordamida to‘liq tarjima + izoh oling. (Aniqlik 1-o‘rinda)")

    premium_banner()

    uploaded = file_uploader_block()
    if not uploaded:
        st.info("Boshlash uchun PDF yoki rasm yuklang.")
        st.stop()

    try:
        pages, filename = build_pages_from_upload(uploaded)
    except Exception as e:
        st.error(str(e))
        st.stop()

    # Controls
    left, right = st.columns([1.05, 1.35], gap="large")

    with left:
        st.markdown("### 🖼 Preview")
        if len(pages) > 1:
            st.session_state["active_page_idx"] = st.slider(
                "Sahifa tanlang",
                0, len(pages)-1,
                value=clamp(st.session_state.get("active_page_idx", 0), 0, len(pages)-1)
            )
        else:
            st.session_state["active_page_idx"] = 0

        show_page_preview(pages, st.session_state["active_page_idx"])

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        # Page selection
        if len(pages) > 1:
            st.markdown("### ✅ Tahlil qilinadigan sahifalar")
            mode = st.radio("Tanlash", ["Faqat tanlangan sahifa", "Bir nechta sahifa"], horizontal=True)
            if mode == "Faqat tanlangan sahifa":
                selected_indices = [st.session_state["active_page_idx"]]
            else:
                # Multi-select indices
                default = [st.session_state["active_page_idx"]]
                selected_indices = st.multiselect(
                    "Sahifalar",
                    options=list(range(len(pages))),
                    default=default,
                    format_func=lambda i: f"Varaq {i+1}"
                )
                if not selected_indices:
                    selected_indices = default
        else:
            selected_indices = [0]

        st.markdown("### ⚙️ Sifat sozlamalari")
        strips = st.slider("OCR bo‘laklar soni (ko‘proq = to‘liqroq, sekinroq)", 7, 14, STRIPS_PER_PAGE_DEFAULT)
        # store runtime override
        global STRIPS_PER_PAGE_DEFAULT
        STRIPS_PER_PAGE_DEFAULT = strips

        st.caption("Tavsiya: agar tarjima qisqa chiqsa — bo‘lak sonini oshiring (12–14).")

        # Analyze button
        ok, msg = can_user_analyze(len(selected_indices))
        if not ok:
            st.warning(msg)

        run = st.button("🧠 AKADEMIK TAHLILNI BOSHLASH", type="primary", use_container_width=True, disabled=not ok)

        if run:
            try:
                # consume credits upfront (safe UX), refund if page fails
                consume_for_analysis(len(selected_indices))
            except Exception as e:
                st.error(str(e))
                st.stop()

            progress = st.progress(0)
            status = st.empty()
            success = 0

            for k, idx in enumerate(selected_indices, start=1):
                status.info(f"Varaq {idx+1}: o‘qish → tarjima...")
                try:
                    res_text, translit = analyze_page(pages[idx], filename, idx)
                    st.session_state["results"][idx] = res_text
                    st.session_state["translit_cache"][idx] = translit
                    success += 1
                except Exception as e:
                    # refund 1 credit for failed page
                    refund_for_failure(1)
                    # log error
                    if st.session_state["logged_in"] and sb:
                        try:
                            sb_insert_usage_log(st.session_state["email"], filename, idx, "error", 0, note=str(e))
                        except Exception:
                            pass
                    st.error(f"Varaq {idx+1} xato: {e}")

                progress.progress(int(k / len(selected_indices) * 100))
                short_sleep()

            status.success(f"Tayyor: {success}/{len(selected_indices)} sahifa.")

            # refresh history
            if st.session_state["logged_in"] and sb:
                st.session_state["history"] = sb_fetch_history(st.session_state["email"], HISTORY_LIMIT)

    with right:
        st.markdown("### 🧾 Natija")

        active = st.session_state.get("active_page_idx", 0)
        # If analyzed, show that page result; else show most recent from results/history
        result_text = st.session_state["results"].get(active, "")

        # navigation
        nav1, nav2, nav3 = st.columns([1, 1, 2])
        with nav1:
            if st.button("⬅ Prev", use_container_width=True, disabled=(active <= 0)):
                st.session_state["active_page_idx"] = active - 1
                st.rerun()
        with nav2:
            if st.button("Next ➡", use_container_width=True, disabled=(active >= len(pages)-1)):
                st.session_state["active_page_idx"] = active + 1
                st.rerun()
        with nav3:
            st.markdown(f"<div class='kpi'>Varaq: <b>{active+1}</b> / {len(pages)}</div>", unsafe_allow_html=True)

        st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

        # If not available in session, try history
        if not result_text and st.session_state["logged_in"] and sb:
            # find history by page index + filename
            for h in st.session_state.get("history", []):
                if int(h.get("page_index", -1)) == int(active) and (h.get("doc_name") == filename):
                    result_text = h.get("result_text", "")
                    break

        if not result_text:
            st.info("Natija yo‘q. Chap tomondan tahlilni boshlang yoki History’dan tanlang.")
        else:
            st.markdown("<div class='result-wrap'>", unsafe_allow_html=True)

            # search within results
            q = st.text_input("🔎 Natijadan qidirish", value="", placeholder="keyword...")
            if q.strip():
                ql = q.strip().lower()
                lines = result_text.splitlines()
                hits = [ln for ln in lines if ql in ln.lower()]
                if hits:
                    st.success(f"Topildi: {len(hits)} ta satr")
                    st.code("\n".join(hits[:60]))
                else:
                    st.warning("Topilmadi.")

            render_copy_button(result_text, key=f"copy_{active}")

            # Optional translit view (debug / pro users)
            with st.expander("🔍 Transliteratsiyani ko‘rish (debug)", expanded=False):
                tl = st.session_state["translit_cache"].get(active, "")
                if not tl and st.session_state["logged_in"] and sb:
                    st.caption("Bu sahifa transliteratsiyasi sessionda yo‘q (faqat natija saqlangan).")
                else:
                    st.text_area("TRANSLITERATSIYA", value=tl, height=260)

            st.markdown("</div>", unsafe_allow_html=True)

        st.caption("Eslatma: Qo‘lyozma juda mayda bo‘lsa, OCR bo‘laklar sonini oshiring (12–14) va qayta sinang.")


# =========================
# RUN
# =========================

if __name__ == "__main__":
    main()
