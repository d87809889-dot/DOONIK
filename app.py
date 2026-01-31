# app.py — NotebookLM-style (Sources | Chat | Studio) for Manuscript AI Center
# NOTE: Gemini model_name MUST stay: "gemini-flash-latest"

import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
import io, re, json, gc, base64
import time, random
import requests
from datetime import datetime
from supabase import create_client
try:
    from docx import Document
except Exception:
    Document = None

from google.generativeai.types import HarmCategory, HarmBlockThreshold


# =========================
# PAGE CONFIG (NotebookLM vibe)
# =========================
st.set_page_config(
    page_title="Manuscript AI Studio",
    page_icon="📓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================
# SECRETS / SERVICES
# =========================
try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets.get("APP_PASSWORD", "")
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    # Optional text providers (for demo, to reduce Gemini calls)
    CF_ACCOUNT_ID = st.secrets.get("CF_ACCOUNT_ID", "")
    CF_API_TOKEN = st.secrets.get("CF_API_TOKEN", "")
    CF_TEXT_MODEL = st.secrets.get("CF_TEXT_MODEL", "@cf/meta/llama-3.1-8b-instruct")
    DEFAULT_TEXT_PROVIDER = st.secrets.get("DEFAULT_TEXT_PROVIDER", "cloudflare").lower()
    OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY", "")
except Exception:
    st.error("Secrets sozlanmagan! (SUPABASE_URL/SUPABASE_KEY/GEMINI_API_KEY)")
    st.stop()

# =========================
# DEMO MODE (Pitch)
# =========================
DEMO_MODE = True
DEFAULT_DEMO_CREDITS = 50

def ensure_demo_user(email: str) -> None:
    try:
        res = db.table("profiles").select("email").eq("email", email).execute()
        if not res.data:
            db.table("profiles").insert({"email": email, "credits": DEFAULT_DEMO_CREDITS}).execute()
    except Exception:
        pass

def fetch_live_credits(email: str) -> int:
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return int(res.data["credits"]) if res.data else 0
    except Exception:
        return 0

def use_credit_atomic(email: str, count: int = 1) -> bool:
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False


# =========================
# SESSION STATE
# =========================
def ss_init():
    defaults = {
        "auth": False,
        "u_email": "",
        "sources": [],          # list of dict: {id,name,type,pages,chunks,selected}
        "active_source_ids": set(),
        "chat": [],             # list of dict: {role, content, citations}
        "last_retrieval": [],   # list of chunk dicts
        "studio_output": {"summary": "", "flashcards": [], "quiz": []},
        "ui_notice": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

ss_init()


# =========================
# GEMINI (UNCHANGED MODEL NAME)
# =========================
genai.configure(api_key=GEMINI_KEY)
system_instruction = (
    "You are Manuscript AI Studio assistant. "
    "You must be grounded in the provided sources. "
    "If the answer is not in sources, say so."
)

safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=system_instruction,
    safety_settings=safety_settings
)


# =========================
# NOTEBOOKLM DARK-GRAY CSS
# =========================
st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
<style>
html, body, [class*="css"]  { font-family: 'Segoe UI', 'Roboto', Arial, sans-serif; }
.stApp { background: linear-gradient(135deg, #232526 0%, #414345 100%); color: #e8eaed; }
header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; }
footer { visibility: hidden; }
#stDecoration { display:none; }
.stAppDeployButton { display:none; }

/* --- Layout containers --- */
.nlm-shell {
    display: block;
    padding: 10px 6px 0 6px;
}
.nlm-topbar {
    display:flex; align-items:center; justify-content:space-between;
    gap:12px; padding: 6px 10px 14px 10px;
    background: rgba(34,37,41,0.95);
    border-radius: 16px;
    box-shadow: 0 2px 12px rgba(34,37,41,0.12);
}
.nlm-brand {
    font-weight: 700; letter-spacing: 0.2px; font-size: 20px;
    color:#e8eaed; display:flex; gap:10px; align-items:center;
}
.nlm-brand .fa-book {
    color: #8f94fb;
    font-size: 1.5em;
}
.nlm-pill {
    font-size: 13px; color:#c7c9cc; padding: 5px 14px;
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 999px; background: rgba(255,255,255,0.07);
    margin-left: 8px;
}
.nlm-avatar {
    width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg,#8f94fb 0%,#4e54c8 100%); color: #fff; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 1.1em; margin-right: 10px; border: 2px solid #fff2; box-shadow: 0 2px 8px #8f94fb33;
}
.nlm-grid {
    display:grid;
    grid-template-columns: 1.05fr 1.6fr 1.05fr;
    gap: 16px;
    align-items: start;
}

/* --- Panels --- */
.nlm-panel {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 18px;
    padding: 18px 16px 16px 16px;
    box-shadow: 0 8px 32px rgba(34,37,41,0.18);
    margin-bottom: 8px;
    transition: box-shadow 0.2s;
}
.nlm-panel:hover {
    box-shadow: 0 12px 40px rgba(143,148,251,0.18);
}
.nlm-panel h3{
    margin: 0 0 10px 0; padding: 0;
    font-size: 15px; font-weight: 700; color:#8f94fb;
    border: none !important; text-align:left !important;
    display: flex; align-items: center; gap: 8px;
}
.nlm-panel h3 .fa { color: #8f94fb; }
.nlm-sub {
    color:#aab0b6; font-size: 13px; margin-top:-4px; margin-bottom: 10px;
}
.nlm-divider {
    height:1px; background: rgba(255,255,255,0.10);
    margin: 12px 0;
}

/* --- Buttons --- */
.stButton>button {
    background: linear-gradient(90deg, #4e54c8 0%, #8f94fb 100%) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 14px !important;
    padding: 12px 20px !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(78,84,200,0.15);
    transition: 0.2s;
}
.stButton>button:hover{
    background: linear-gradient(90deg, #8f94fb 0%, #4e54c8 100%) !important;
    box-shadow: 0 4px 16px rgba(78,84,200,0.25);
}
.small-btn .stButton>button{
    padding: 8px 10px !important;
    border-radius: 10px !important;
    font-size: 12px !important;
}

/* --- Inputs --- */
.stTextInput input, .stTextArea textarea {
    background: rgba(255,255,255,0.08) !important;
    color: #e8eaed !important;
    border-radius: 10px !important;
    border: 1px solid #4e54c8 !important;
}
.stTextInput input:focus, .stTextArea textarea:focus{
    border-color: #8f94fb !important;
    box-shadow: 0 0 0 2px #8f94fb33 !important;
}

/* --- Chip style --- */
.nlm-chip {
    display:inline-block;
    font-size: 12px; color:#c7c9cc;
    padding: 5px 10px;
    border: 1px solid rgba(255,255,255,0.13);
    border-radius: 999px;
    background: rgba(0,0,0,0.22);
    margin-right:8px; margin-top:8px;
}
.nlm-cite {
    display:inline-block;
    font-size: 12px; color:#c7c9cc;
    padding: 4px 10px;
    border: 1px dashed rgba(255,255,255,0.18);
    border-radius: 999px;
    background: rgba(255,255,255,0.07);
    margin-right:8px; margin-top:8px;
}

/* --- Chat bubbles --- */
.msg-user {
    background: rgba(255,255,255,0.10);
    border: 1px solid rgba(255,255,255,0.13);
    padding: 12px 16px; border-radius: 16px;
    margin-bottom: 12px;
    box-shadow: 0 2px 8px rgba(143,148,251,0.10);
}
.msg-ai {
    background: rgba(143,148,251,0.10);
    border: 1px solid rgba(143,148,251,0.18);
    padding: 12px 16px; border-radius: 16px;
    margin-bottom: 14px;
    box-shadow: 0 2px 8px rgba(143,148,251,0.10);
}
.msg-h {
    font-size: 13px; font-weight: 700; color:#8f94fb;
    margin-bottom: 6px;
}
.msg-t {
    font-size: 14px; line-height: 1.6; color:#e8eaed;
    white-space: pre-wrap;
}

/* --- Animated spinner --- */
.fa-spinner { animation: spin 1.2s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

/* --- Responsive --- */
@media (max-width: 1000px){
    .nlm-grid{ grid-template-columns: 1fr; }
}
</style>
""", unsafe_allow_html=True)


# =========================
# LOGIN (keep simple)
# =========================
if not st.session_state.auth:
    st.markdown("<div class='nlm-shell'>", unsafe_allow_html=True)
    st.markdown("""
      <div class="nlm-topbar">
        <div class="nlm-brand">📓 Manuscript AI Studio <span class="nlm-pill">NotebookLM-style MVP</span></div>
      </div>
    """, unsafe_allow_html=True)

    st.markdown("<div class='nlm-panel' style='max-width:520px;margin:0 auto;'>", unsafe_allow_html=True)
    st.markdown("<h3>Login</h3><div class='nlm-sub'>Demo rejim: email bilan kirish</div>", unsafe_allow_html=True)

    email_in = st.text_input("Email", placeholder="example@domain.com")

    if not DEMO_MODE:
        pwd_in = st.text_input("Parol", type="password", placeholder="Parol")

    if st.button("Kirish"):
        if not email_in:
            st.warning("Email kiriting.")
        elif DEMO_MODE:
            st.session_state.auth = True
            st.session_state.u_email = email_in.strip().lower()
            ensure_demo_user(st.session_state.u_email)
            st.rerun()
        else:
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth = True
                st.session_state.u_email = email_in.strip().lower()
                st.rerun()
            else:
                st.error("Parol noto‘g‘ri.")

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.stop()


# =========================
# HELPERS: PDF text extract + chunk + retrieval
# =========================
def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def chunk_text(text: str, chunk_chars: int = 1000, overlap: int = 120):
    text = normalize_ws(text)
    if not text:
        return []
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        j = min(i + chunk_chars, n)
        chunk = text[i:j]
        chunks.append(chunk)
        if j == n:
            break
        i = max(0, j - overlap)
    return chunks

def extract_pdf_text_pages(pdf_bytes: bytes, max_pages: int = 30):
    pages = []
    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        total = min(len(pdf), max_pages)
        for i in range(total):
            page = pdf[i]
            txt = ""
            try:
                # pypdfium2 text extraction
                textpage = page.get_textpage()
                txt = textpage.get_text_range()
            except Exception:
                txt = ""
            pages.append(txt or "")
        pdf.close()
    except Exception:
        return []
    return pages

def simple_retrieve(question: str, sources, active_ids, top_k: int = 8):
    """Cheap retrieval: keyword overlap scoring."""
    q = normalize_ws(question).lower()
    if not q:
        return []
    q_terms = set([t for t in re.findall(r"[a-zA-Z\u0400-\u04FF\u0600-\u06FF0-9']+", q) if len(t) > 2])

    pool = []
    for s in sources:
        if s["id"] not in active_ids:
            continue
        for ch in s["chunks"]:
            txt = ch["text"].lower()
            # overlap score
            score = 0
            for t in q_terms:
                if t in txt:
                    score += 1
            if score > 0:
                pool.append((score, s, ch))

    pool.sort(key=lambda x: x[0], reverse=True)
    picked = []
    for score, s, ch in pool[:top_k]:
        picked.append({
            "source_id": s["id"],
            "source_name": s["name"],
            "page": ch["page"],
            "chunk_id": ch["chunk_id"],
            "text": ch["text"],
        })
    return picked

def format_context(chunks):
    """Build grounded context with cite ids."""
    lines = []
    for i, c in enumerate(chunks, start=1):
        cite = f"[S:{c['source_name']}|p{c['page']}|c{c['chunk_id']}]"
        snippet = c["text"]
        lines.append(f"{cite}\n{snippet}\n")
    return "\n".join(lines)

def parse_citations_from_answer(answer: str):
    """Optional: if model echoes cite tags, we show them. Otherwise we show retrieved chunk tags."""
    # keep it simple
    return []

def gemini_text_generate(prompt: str):
    resp = model.generate_content([prompt])
    return getattr(resp, "text", "") or ""


# =========================
# TEXT PROVIDERS (Cloudflare Workers AI default; Gemini stays as backup)
# =========================
def _parse_retry_delay_seconds(text: str) -> float | None:
    if not text:
        return None
    # Common patterns: "Please retry in 12s" / "retry in 12s" / "Retry-After: 12"
    m = re.search(r"retry\s+in\s+(\d+(?:\.\d+)?)\s*s", text, flags=re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"Please\s+retry\s+in\s+(\d+(?:\.\d+)?)\s*s", text, flags=re.I)
    if m:
        return float(m.group(1))
    return None

def cloudflare_text_generate(prompt: str, *, max_retries: int = 5) -> str:
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        raise RuntimeError("Cloudflare secrets yo'q (CF_ACCOUNT_ID/CF_API_TOKEN).")

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run/{CF_TEXT_MODEL}"
    headers = {"Authorization": f"Bearer {CF_API_TOKEN}", "Content-Type": "application/json"}

    payload = {
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ]
    }

    base = 1.2  # seconds
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as e:
            # network -> exponential backoff
            sleep_s = min(20.0, base * (2 ** attempt)) + random.uniform(0.0, 0.6)
            time.sleep(sleep_s)
            if attempt == max_retries - 1:
                raise RuntimeError(f"Network error: {e}")
            continue

        # Success
        if 200 <= r.status_code < 300:
            data = {}
            try:
                data = r.json() if r.content else {}
            except Exception:
                return r.text or ""
            # Workers AI typically returns {"result": {...}}; try common fields safely
            result = data.get("result", data)
            if isinstance(result, dict):
                for k in ("response", "output", "text", "answer"):
                    if k in result and isinstance(result[k], str):
                        return result[k]
                # Some models return {"result": {"choices":[{"message":{"content":"..."}}]}}
                try:
                    choices = result.get("choices", [])
                    if choices and isinstance(choices, list):
                        msg = choices[0].get("message", {})
                        if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                            return msg["content"]
                except Exception:
                    pass
            if isinstance(result, str):
                return result
            return data.get("text", "") if isinstance(data.get("text", ""), str) else (r.text or "")

        # 429 rate-limit
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After", "")
            delay = None
            if retry_after.strip().isdigit():
                delay = float(retry_after.strip())
            else:
                delay = _parse_retry_delay_seconds(r.text or "")
            if delay is None:
                delay = min(20.0, base * (2 ** attempt))
            delay = delay + random.uniform(0.0, 0.8)  # jitter
            time.sleep(delay)
            continue

        # 5xx backoff
        if 500 <= r.status_code <= 599:
            sleep_s = min(20.0, base * (2 ** attempt)) + random.uniform(0.0, 0.6)
            time.sleep(sleep_s)
            continue

        # Other errors: raise with message
        raise RuntimeError(f"Cloudflare error {r.status_code}: {r.text[:400]}")

    raise RuntimeError("Cloudflare: retries exhausted")

def openrouter_text_generate(prompt: str, *, max_retries: int = 3) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OpenRouter key yo'q (OPENROUTER_API_KEY).")

    # NOTE: OpenRouter model is configurable; keep a safe default for demo
    model_id = st.secrets.get("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct").strip()
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    base = 1.0
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=60)
        except requests.RequestException as e:
            time.sleep(min(10.0, base * (2 ** attempt)) + random.uniform(0.0, 0.6))
            if attempt == max_retries - 1:
                raise RuntimeError(f"OpenRouter network error: {e}")
            continue

        if 200 <= r.status_code < 300:
            try:
                data = r.json()
                return data["choices"][0]["message"]["content"]
            except Exception:
                return r.text or ""

        if r.status_code == 429:
            # OpenRouter often provides retry-after header too
            retry_after = r.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.strip().isdigit() else min(10.0, base * (2 ** attempt))
            time.sleep(delay + random.uniform(0.0, 0.8))
            continue

        if 500 <= r.status_code <= 599:
            time.sleep(min(10.0, base * (2 ** attempt)) + random.uniform(0.0, 0.6))
            continue

        raise RuntimeError(f"OpenRouter error {r.status_code}: {r.text[:400]}")

    raise RuntimeError("OpenRouter: retries exhausted")

def text_generate(prompt: str) -> str:
    """Default: Cloudflare. Fallback: OpenRouter (if key) else Gemini."""
    provider = (DEFAULT_TEXT_PROVIDER or "cloudflare").lower()

    # 1) Try primary
    try:
        if provider == "cloudflare":
            return cloudflare_text_generate(prompt)
        if provider == "openrouter":
            return openrouter_text_generate(prompt)
        if provider == "gemini":
            return gemini_text_generate(prompt)
    except Exception:
        pass

    # 2) Fallback chain
    if provider != "cloudflare":
        try:
            return cloudflare_text_generate(prompt)
        except Exception:
            pass
    if OPENROUTER_API_KEY and provider != "openrouter":
        try:
            return openrouter_text_generate(prompt)
        except Exception:
            pass

    # Last resort: Gemini (same fixed model name)
    return gemini_text_generate(prompt)


# =========================
# TOPBAR
# =========================
credits = fetch_live_credits(st.session_state.u_email)

st.markdown("<div class='nlm-shell'>", unsafe_allow_html=True)
# --- User avatar/profile (7) ---
def get_avatar_html(email):
        initials = ""
        if email:
                parts = email.split("@")[0].split(".")
                initials = ''.join([p[0].upper() for p in parts if p])[:2]
        return f'<div class="nlm-avatar">{initials or "U"}</div>'

st.markdown(f"""
    <div class="nlm-topbar">
        <div class="nlm-brand"><i class="fa fa-book"></i> Manuscript AI Studio <span class="nlm-pill"><i class="fa fa-moon"></i> NotebookLM dark-gray</span></div>
        <div style="display:flex;align-items:center;gap:8px;">
            {get_avatar_html(st.session_state.u_email)}
            <div class="nlm-pill"><i class="fa fa-user"></i> {st.session_state.u_email} · <i class="fa fa-coins"></i> {credits} credits</div>
        </div>
    </div>
""", unsafe_allow_html=True)

# =========================
# 3-PANEL GRID
# =========================
st.markdown("<div class='nlm-grid'>", unsafe_allow_html=True)

# ---------- SOURCES (LEFT) ----------
st.markdown("<div class='nlm-panel'>", unsafe_allow_html=True)
st.markdown("<h3>Sources</h3><div class='nlm-sub'>Upload PDF or paste text. Select sources to use.</div>", unsafe_allow_html=True)

with st.expander("+ Add sources", expanded=True):
    up = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    pasted = st.text_area("Paste text", height=120, placeholder="Paste text here…", label_visibility="collapsed")
    add_cols = st.columns(2)
    with add_cols[0]:
        if st.button("Add PDF"):
            if up is None:
                st.warning("PDF tanlang.")
            else:
                pdf_bytes = up.getvalue()
                pages = extract_pdf_text_pages(pdf_bytes, max_pages=30)
                # build chunks
                chunks = []
                for pi, pt in enumerate(pages, start=1):
                    for ci, ch in enumerate(chunk_text(pt, 1000, 120), start=1):
                        chunks.append({"page": pi, "chunk_id": ci, "text": ch})

                sid = f"pdf:{up.name}:{datetime.now().timestamp()}"
                st.session_state.sources.append({
                    "id": sid,
                    "name": up.name,
                    "type": "pdf",
                    "pages": len(pages),
                    "chunks": chunks
                })
                st.session_state.active_source_ids.add(sid)
                st.session_state.ui_notice = f"✅ Added: {up.name} (pages={len(pages)}, chunks={len(chunks)})"
                st.rerun()
    with add_cols[1]:
        if st.button("Add Text"):
            if not normalize_ws(pasted):
                st.warning("Matn kiriting.")
            else:
                chunks = []
                for ci, ch in enumerate(chunk_text(pasted, 1000, 120), start=1):
                    chunks.append({"page": 1, "chunk_id": ci, "text": ch})
                sid = f"text:{datetime.now().timestamp()}"
                st.session_state.sources.append({
                    "id": sid,
                    "name": "Pasted text",
                    "type": "text",
                    "pages": 1,
                    "chunks": chunks
                })
                st.session_state.active_source_ids.add(sid)
                st.session_state.ui_notice = f"✅ Added: pasted text (chunks={len(chunks)})"
                st.rerun()

if st.session_state.ui_notice:
    st.info(st.session_state.ui_notice)

st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)

if not st.session_state.sources:
    st.markdown("<div class='nlm-sub'>No sources yet. Add a PDF or paste text.</div>", unsafe_allow_html=True)
else:
    # Quick search (inside sources)
    qsearch = st.text_input("Quick search", placeholder="Search within sources…", label_visibility="collapsed")
    if qsearch:
        hits = simple_retrieve(qsearch, st.session_state.sources, st.session_state.active_source_ids, top_k=6)
        if hits:
            st.markdown("<div class='nlm-sub'>Top hits:</div>", unsafe_allow_html=True)
            for h in hits:
                st.markdown(f"<span class='nlm-chip'>{h['source_name']} · p{h['page']} · c{h['chunk_id']}</span>", unsafe_allow_html=True)
        else:
            st.caption("No hits.")

    st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)
    st.markdown("<div class='nlm-sub'>Sources list</div>", unsafe_allow_html=True)

    for s in list(st.session_state.sources):
        row = st.columns([0.12, 0.68, 0.20])
        checked = s["id"] in st.session_state.active_source_ids
        with row[0]:
            new_checked = st.checkbox(" ", value=checked, key=f"src_chk_{s['id']}")
        with row[1]:
            st.markdown(f"**{s['name']}**  \n<span class='nlm-sub'>{s['type'].upper()} · pages {s['pages']} · chunks {len(s['chunks'])}</span>", unsafe_allow_html=True)
        with row[2]:
            st.markdown("<div class='small-btn'>", unsafe_allow_html=True)
            if st.button("Delete", key=f"del_{s['id']}"):
                st.session_state.sources = [x for x in st.session_state.sources if x["id"] != s["id"]]
                st.session_state.active_source_ids.discard(s["id"])
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        if new_checked and not checked:
            st.session_state.active_source_ids.add(s["id"])
        if (not new_checked) and checked:
            st.session_state.active_source_ids.discard(s["id"])

    total_pages = sum(s["pages"] for s in st.session_state.sources if s["id"] in st.session_state.active_source_ids)
    total_chunks = sum(len(s["chunks"]) for s in st.session_state.sources if s["id"] in st.session_state.active_source_ids)
    st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)
    st.markdown(f"<span class='nlm-chip'>Selected pages: {total_pages}</span><span class='nlm-chip'>Selected chunks: {total_chunks}</span>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # end sources panel


# ---------- CHAT (MIDDLE) ----------
st.markdown("<div class='nlm-panel'>", unsafe_allow_html=True)
st.markdown("<h3>Chat</h3><div class='nlm-sub'>Ask questions grounded in your sources (with citations).</div>", unsafe_allow_html=True)

suggest_cols = st.columns(3)
suggested = [
    "Asosiy g‘oya nima? 5-7 punkt.",
    "Muhim terminlar ro‘yxati va qisqa izohlar.",
    "Muallif maqsadi va asosiy dalillar (citations bilan)."
]
for i, text in enumerate(suggested):
    with suggest_cols[i]:
        st.markdown("<div class='small-btn'>", unsafe_allow_html=True)
        if st.button(text, key=f"sugg_{i}"):
            st.session_state["chat_input_seed"] = text
        st.markdown("</div>", unsafe_allow_html=True)

# render chat history
if st.session_state.chat:
    for m in st.session_state.chat:
        if m["role"] == "user":
            st.markdown(f"<div class='msg-user'><div class='msg-h'>You</div><div class='msg-t'>{m['content']}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='msg-ai'><div class='msg-h'>Assistant</div><div class='msg-t'>{m['content']}</div>", unsafe_allow_html=True)
            if m.get("citations"):
                for c in m["citations"]:
                    st.markdown(f"<span class='nlm-cite'>{c}</span>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("<div class='nlm-sub'>No messages yet. Add sources and ask a question.</div>", unsafe_allow_html=True)

st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)

seed = st.session_state.pop("chat_input_seed", "")
question = st.text_input("Ask", value=seed, placeholder="Ask something about your sources…", label_visibility="collapsed")

ask_cols = st.columns([0.7, 0.3])
with ask_cols[0]:
    if st.button("Send"):
        if not normalize_ws(question):
            st.warning("Savol yozing.")
        elif not st.session_state.active_source_ids:
            st.warning("Kamida 1 ta source tanlang.")
        else:
            if not use_credit_atomic(st.session_state.u_email, 1):
                st.warning("Kredit tugagan.")
            else:
                # Retrieve chunks (cheap)
                chunks = simple_retrieve(question, st.session_state.sources, st.session_state.active_source_ids, top_k=8)
                st.session_state.last_retrieval = chunks

                # DEBUG: retrieval natijasini va contextni ko'rsatish
                st.write("**[DEBUG] Retrieval natijasi (chunks):**", chunks)
                context = format_context(chunks)
                st.write("**[DEBUG] Modelga yuboriladigan context:**", context)

                prompt = f"""
    You must answer ONLY using the provided SOURCE EXCERPTS below.
    If answer is not present, say: "Manbada topilmadi."
    Always include citations by reusing the cite tags like [S:NAME|pX|cY].

    QUESTION:
    {question}

    SOURCE EXCERPTS:
    {context}

    FORMAT:
    - Answer in Uzbek
    - Use short paragraphs / bullets when helpful
    - Add citations inline like [S:...]
    """
                with st.spinner("Generating answer..."):
                    answer = text_generate(prompt)

                # If model didn't include cites, we still show retrieval tags for transparency
                cites = []
                if chunks:
                    for c in chunks[:5]:
                        cites.append(f"{c['source_name']} p{c['page']} c{c['chunk_id']}")

                st.session_state.chat.append({"role": "user", "content": question, "citations": []})
                st.session_state.chat.append({"role": "assistant", "content": answer, "citations": cites})
                st.rerun()

with ask_cols[1]:
    st.markdown("<div class='small-btn'>", unsafe_allow_html=True)
    if st.button("Clear chat"):
        st.session_state.chat = []
        st.session_state.last_retrieval = []
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)  # end chat panel


# ---------- STUDIO (RIGHT) ----------
st.markdown("<div class='nlm-panel'>", unsafe_allow_html=True)
st.markdown("<h3>Studio</h3><div class='nlm-sub'>Generate study materials from selected sources.</div>", unsafe_allow_html=True)

def studio_context():
    # If we have recent retrieval, use it; otherwise use first chunks from selected sources
    if st.session_state.last_retrieval:
        chunks = st.session_state.last_retrieval
    else:
        chunks = []
        for s in st.session_state.sources:
            if s["id"] in st.session_state.active_source_ids:
                for ch in s["chunks"][:3]:
                    chunks.append({
                        "source_id": s["id"],
                        "source_name": s["name"],
                        "page": ch["page"],
                        "chunk_id": ch["chunk_id"],
                        "text": ch["text"],
                    })
        chunks = chunks[:8]
    return format_context(chunks), chunks

btn_cols = st.columns(3)

with btn_cols[0]:
    if st.button("Summary"):
        if not st.session_state.active_source_ids:
            st.warning("Kamida 1 ta source tanlang.")
        else:
            if credits <= 0:
                st.warning("Kredit tugagan.")
            else:
                if not use_credit_atomic(st.session_state.u_email, 1):
                    st.warning("Kredit tugagan.")
                else:
                    ctx, chunks = studio_context()
                    prompt = f"""
    Create a concise study SUMMARY in Uzbek, grounded ONLY in the excerpts.
    Return:
    1) 8-12 bullet points
    2) 3 key takeaways
    Use inline citations [S:NAME|pX|cY].

    EXCERPTS:
    {ctx}
    """
                    with st.spinner("Generating summary..."):
                        out = text_generate(prompt)
                    st.session_state.studio_output["summary"] = out
                    # Optionally spend 1 credit per studio action:
                    # use_credit_atomic(st.session_state.u_email, 1)
                    st.rerun()

with btn_cols[1]:
    if st.button("Flashcards"):
        if not st.session_state.active_source_ids:
            st.warning("Kamida 1 ta source tanlang.")
        else:
            if credits <= 0:
                st.warning("Kredit tugagan.")
            else:
                if not use_credit_atomic(st.session_state.u_email, 1):
                    st.warning("Kredit tugagan.")
                else:
                    ctx, chunks = studio_context()
                    prompt = f"""
    Generate 8-12 FLASHCARDS in Uzbek, grounded ONLY in excerpts.
    Format strictly as JSON:
    [
      {{"q":"...","a":"...","cite":"[S:...]" }},
      ...
    ]
    Keep answers short. Use citations.

    EXCERPTS:
    {ctx}
    """
                    with st.spinner("Generating flashcards..."):
                        out = text_generate(prompt)
                    # parse JSON safely
                    cards = []
                    try:
                        cards = json.loads(out.strip())
                        if not isinstance(cards, list):
                            cards = []
                    except Exception:
                        cards = []
                    st.session_state.studio_output["flashcards"] = cards
                    st.rerun()

with btn_cols[2]:
    if st.button("Quiz"):
        if not st.session_state.active_source_ids:
            st.warning("Kamida 1 ta source tanlang.")
        else:
            if credits <= 0:
                st.warning("Kredit tugagan.")
            else:
                if not use_credit_atomic(st.session_state.u_email, 1):
                    st.warning("Kredit tugagan.")
                else:
                    ctx, chunks = studio_context()
                    prompt = f"""
    Generate a QUIZ of 8 questions in Uzbek grounded ONLY in excerpts.
    Return JSON:
    [
      {{"q":"...","options":["A","B","C","D"],"answer_index":0,"explain":"...","cite":"[S:...]" }},
      ...
    ]
    Make it easy for demo.

    EXCERPTS:
    {ctx}
    """
                    with st.spinner("Generating quiz..."):
                        out = text_generate(prompt)
                    quiz = []
                    try:
                        quiz = json.loads(out.strip())
                        if not isinstance(quiz, list):
                            quiz = []
                    except Exception:
                        quiz = []
                    st.session_state.studio_output["quiz"] = quiz
                    st.rerun()

st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)

# Studio outputs
out = st.session_state.studio_output

if out.get("summary"):
    st.markdown("<div class='msg-ai'><div class='msg-h'>Summary</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='msg-t'>{out['summary']}</div></div>", unsafe_allow_html=True)

if out.get("flashcards"):
    st.markdown("<div class='msg-ai'><div class='msg-h'>Flashcards</div>", unsafe_allow_html=True)
    for c in out["flashcards"][:20]:
        q = c.get("q", "")
        a = c.get("a", "")
        cite = c.get("cite", "")
        st.markdown(f"<div class='msg-t'>Q: {q}\nA: {a}\n<span class='nlm-cite'>{cite}</span></div><div class='nlm-divider'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

if out.get("quiz"):
    st.markdown("<div class='msg-ai'><div class='msg-h'>Quiz</div>", unsafe_allow_html=True)
    for i, q in enumerate(out["quiz"][:20], start=1):
        qq = q.get("q", "")
        opts = q.get("options", [])
        ans = q.get("answer_index", 0)
        cite = q.get("cite", "")
        expl = q.get("explain", "")
        st.markdown(f"<div class='msg-t'><b>{i}) {qq}</b></div>", unsafe_allow_html=True)
        for j, o in enumerate(opts):
            mark = "✅" if j == ans else "•"
            st.markdown(f"<div class='msg-t'>{mark} {o}</div>", unsafe_allow_html=True)
        if expl:
            st.markdown(f"<div class='msg-t'><i>{expl}</i></div>", unsafe_allow_html=True)
        st.markdown(f"<span class='nlm-cite'>{cite}</span><div class='nlm-divider'></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# Exports (simple)
st.markdown("<div class='nlm-divider'></div>", unsafe_allow_html=True)
export_format = st.selectbox("Export", ["TXT", "DOCX", "JSON"], label_visibility="collapsed")

export_payload = {
    "user": st.session_state.u_email,
    "date": datetime.now().isoformat(),
    "selected_sources": [s["name"] for s in st.session_state.sources if s["id"] in st.session_state.active_source_ids],
    "chat": st.session_state.chat,
    "studio": st.session_state.studio_output
}

if export_format == "JSON":
    st.download_button("Download JSON", json.dumps(export_payload, ensure_ascii=False, indent=2), "studio_export.json", mime="application/json")
elif export_format == "TXT":
    txt = []
    txt.append("=== Manuscript AI Studio Export ===")
    txt.append(f"User: {st.session_state.u_email}")
    txt.append(f"Date: {export_payload['date']}")
    txt.append("\n--- CHAT ---")
    for m in st.session_state.chat:
        txt.append(f"{m['role'].upper()}: {m['content']}")
    txt.append("\n--- STUDIO SUMMARY ---")
    txt.append(out.get("summary",""))
    txt.append("\n--- FLASHCARDS ---")
    for c in out.get("flashcards", []):
        txt.append(f"Q: {c.get('q','')}\nA: {c.get('a','')}\nCITE: {c.get('cite','')}\n")
    txt.append("\n--- QUIZ ---")
    for q in out.get("quiz", []):
        txt.append(f"Q: {q.get('q','')}\nOptions: {q.get('options',[])}\nAnswer: {q.get('answer_index',0)}\nCITE: {q.get('cite','')}\n")
    st.download_button("Download TXT", "\n".join(txt), "studio_export.txt", mime="text/plain")
else:
    if Document is None:
        st.info("DOCX export uchun python-docx kutubxonasi kerak. Hozir o'rnatilmagan.")
    else:
        doc = Document()
        doc.add_heading("Manuscript AI Studio Export", level=1)
        doc.add_paragraph(f"User: {st.session_state.u_email}")
        doc.add_paragraph(f"Date: {export_payload['date']}")
        doc.add_heading("Chat", level=2)
        for m in st.session_state.chat:
            doc.add_paragraph(f"{m['role'].upper()}: {m['content']}")
        doc.add_heading("Studio Summary", level=2)
        doc.add_paragraph(out.get("summary",""))
        doc.add_heading("Flashcards", level=2)
        for c in out.get("flashcards", []):
            doc.add_paragraph(f"Q: {c.get('q','')}")
            doc.add_paragraph(f"A: {c.get('a','')}")
            doc.add_paragraph(f"Cite: {c.get('cite','')}")
        doc.add_heading("Quiz", level=2)
        for q in out.get("quiz", []):
            doc.add_paragraph(f"Q: {q.get('q','')}")
            doc.add_paragraph(f"Options: {q.get('options',[])}")
            doc.add_paragraph(f"Answer index: {q.get('answer_index',0)}")
            doc.add_paragraph(f"Cite: {q.get('cite','')}")
            bio = io.BytesIO()
            doc.save(bio)
            st.download_button("Download DOCX", bio.getvalue(), "studio_export.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

st.markdown("</div>", unsafe_allow_html=True)  # end studio panel

st.markdown("</div>", unsafe_allow_html=True)  # end grid
st.markdown("</div>", unsafe_allow_html=True)  # end shell

gc.collect()
