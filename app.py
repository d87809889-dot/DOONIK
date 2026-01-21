import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, base64
from datetime import datetime
from docx import Document
from supabase import create_client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto"
)

# --- PROFESSIONAL ANTIK DIZAYN + LUPA EFFEKTI (CSS) ---
st.markdown("""
    <style>
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    header[data-testid='stHeader'] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }

    button[data-testid='stSidebarCollapseButton'] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        position: fixed !important;
        z-index: 1000001 !important;
    }

    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }

    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7;
    }

    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }

    section[data-testid='stSidebar'] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid='stSidebar'] .stMarkdown { color: #fdfaf1 !important; }

    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; border: 1px solid #c5a059; height: 50px !important; }

    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.2); transition: transform 0.3s ease; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES (SUPABASE & AI) ---
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Email")
        pwd_in = st.text_input("Parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.rerun()
            else:
                st.error("Parol xato!")
    st.stop()

# --- AI ENGINE ---
genai.configure(api_key=GEMINI_KEY)
system_instruction = "Siz Manuscript AI mutaxassisiz. Tadqiqotchi d87809889-dot muallifligida ilmiy tahlillar qilasiz."
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

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (TUZATILDI)
# ==========================================
def enhance_image_for_ai(img: Image.Image):
    """Rasmni AI tahlili uchun optimallashtirish (XATO TUZATILDI)"""
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img

def img_to_png_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")  # PNG lossless - eng aniq OCR uchun
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except:
        return 0

def use_credit_atomic(email: str, count: int = 1):
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page(file_content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(file_content))
    except:
        return None

# ==========================================
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 User: `{st.session_state.u_email}`")
    current_credits = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Kredit", f"{current_credits} sahifa")
    st.divider()

    lang = st.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()

    br = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    ct = st.slider("Kontrast:", 0.5, 3.0, 1.3)
    rot = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)

    if st.button("🚪 CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertizasi")
file = st.file_uploader("Yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

if "imgs" not in st.session_state: st.session_state.imgs = []
if "results" not in st.session_state: st.session_state.results = {}
if "chats" not in st.session_state: st.session_state.chats = {}

if file:
    if st.session_state.get("last_fn") != file.name:
        with st.spinner("Preparing..."):
            data = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 3.5, True))
                pdf.close()
            else:
                imgs.append(render_page(data, 0, 1.0, False))

            st.session_state.imgs = imgs
            st.session_state.last_fn = file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    processed = []
    for im in st.session_state.imgs:
        p = im.rotate(rot, expand=True)
        p = ImageEnhance.Brightness(p).enhance(br)
        p = ImageEnhance.Contrast(p).enhance(ct)
        processed.append(p)

    indices = st.multiselect("Varaqlarni tanlang:", range(len(processed)), default=[0], format_func=lambda x: f"Varaq {x+1}")

    if not st.session_state.results:
        cols = st.columns(min(len(indices), 4) if indices else 1)
        for i, idx in enumerate(indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        if current_credits >= len(indices):
            prompt = f"Academic analysis of {lang} manuscript ({era}). 1.Transliteration 2.Translation 3.Expert Notes."
            for idx in indices:
                with st.status(f"Varaq {idx+1} ekspertizadan o'tkazilmoqda..."):
                    try:
                        ai_img = enhance_image_for_ai(processed[idx])
                        resp = model.generate_content([prompt, img_to_png_payload(ai_img)])

                        if resp.candidates and resp.candidates[0].content.parts:
                            st.session_state.results[idx] = resp.text
                            use_credit_atomic(st.session_state.u_email)
                        else:
                            st.error("AI bloklandi")
                    except Exception as e:
                        st.error(f"Xato: {e}")
            st.rerun()
        else:
            st.warning("Kredit yetarli emas!")

    if st.session_state.results:
        st.divider()
        final_text = ""
        today = datetime.now().strftime("%d.%m.%Y")

        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])

            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                st.markdown(f"<div class='result-box'>{st.session_state.results[idx]}</div>", unsafe_allow_html=True)
                cite = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili ({lang}). Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>{cite}</div>", unsafe_allow_html=True)

                st.session_state.results[idx] = st.text_area(
                    f"Edit {idx+1}",
                    value=st.session_state.results[idx],
                    height=350,
                    key=f"ed_{idx}"
                )

                final_text += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{cite}"

                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user' style='color:black;'>{ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai' style='color:black;'>{ch['a']}</div>", unsafe_allow_html=True)

                q = st.text_input("Savol yozing:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if q:
                        with st.spinner("..."):
                            chat_res = model.generate_content([
                                f"Hujjat: {st.session_state.results[idx]}\nQ: {q}",
                                img_to_png_payload(processed[idx])
                            ])
                            st.session_state.chats[idx].append({"q": q, "a": chat_res.text})
                            st.rerun()

        if final_text:
            doc = Document()
            doc.add_paragraph(final_text)
            bio = io.BytesIO()
            doc.save(bio)

            st.download_button("📥 WORD YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

gc.collect()
