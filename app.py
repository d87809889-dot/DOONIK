import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (KUCHAYTIRILGAN CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; line-height: 1.7; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-bubble-ai { background-color: #ffffff; color: #000000 !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; padding: 10px; border: 1px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (AUTO-DETECTION FIX)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_verified_model():
    """Googledan aynan ishlovchi barqaror nomni aniqlaydi"""
    try:
        # Bepul kvotada ruxsat berilgan hamma modellarni olamiz
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # SIZDA XATO BERGAN gemini-1.5-flash-latest'NI O'RNIGA STABLE NOMI BIRINCHI QO'YILDI
        targets = ['models/gemini-1.5-flash', 'models/gemini-1.5-flash-001', 'models/gemini-flash-latest']
        
        for t in targets:
            if t in models:
                return genai.GenerativeModel(model_name=t), t
        
        # Agar biz kutgan nomlar bo'lmasa, birinchi flash modelni olish
        flash_models = [m for m in models if 'flash' in m]
        return genai.GenerativeModel(model_name=flash_models[0]), flash_models[0]
    except:
        # Hech narsa ishlamasa eng xavfsiz nomga qaytamiz
        return genai.GenerativeModel(model_name='gemini-1.5-flash'), 'gemini-1.5-flash'

model, active_model_name = load_verified_model()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    # Lossless PNG harflar tiniqligini saqlaydi
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

def use_credit_atomic(email: str):
    curr = fetch_live_credits(email)
    if curr > 0:
        db.table("profiles").update({"credits": curr - 1}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page_high_res(file_content: bytes, page_idx: int, is_pdf: bool) -> Image.Image:
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            # 3.0 scale - barqaror tiniqlik
            img = pdf[page_idx].render(scale=3.0).to_pil()
            pdf.close()
            gc.collect()
            return img
        return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 5. ASOSIY TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    st.metric("💳 Kreditlar", f"{fetch_live_credits(st.session_state.u_email)}")
    st.write(f"🤖 **Model:** `{active_model_name.split('/')[-1]}`")
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Preparing...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page_high_res(file_bytes, i, True))
                pdf.close()
            else:
                imgs.append(render_page_high_res(file_bytes, 0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # Prevyu
    if not st.session_state.results:
        cols = st.columns(min(len(st.session_state.imgs), 4))
        for idx, img in enumerate(st.session_state.imgs):
            cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width=None)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        credits = fetch_live_credits(st.session_state.u_email)
        if credits >= len(st.session_state.imgs):
            # AKADEMIK PROMPT (Professional darajada)
            prompt = f"""
            Siz Manuscript AI tizimining professional matnshunosisiz. Ushbu {lang} manbasini ({style} xati) tahlil qiling.
            Qat'iy bosqichlar:
            1. RAW TRANSCRIPTION: Asl matn arab imlosida.
            2. DIPLOMATIC TRANSLITERATION: Lotin alifbosida variantlar bilan.
            3. SCIENTIFIC TRANSLATION: Zamonaviy o'zbek tiliga akademik tarjima.
            4. EXPERT NOTE: Tarixiy va paleografik sharh.
            """
            for i, img in enumerate(st.session_state.imgs):
                with st.status(f"Sahifa {i+1}...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(img)])
                        st.session_state.results[i] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"Sahifa {i+1} tayyor!", state="complete")
                        time.sleep(3) # Limit (RPM) himoyasi
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Kredit yetarli emas!")

    # --- NATIJALAR ---
    if st.session_state.results:
        st.divider()
        final_text = ""
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, use_container_width=True)
                with c2:
                    st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                    st.session_state.results[idx] = st.text_area(f"Edit ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                    final_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"

                    # Interaktiv Chat
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-bubble-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            chat_res = model.generate_content([f"Hujjat: {res}\nSavol: {user_q}"])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text}); st.rerun()
                st.markdown("---")

        if final_text:
            doc = Document(); doc.add_paragraph(final_text); bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD HISOBOTNI YUKLAB OLISH", bio.getvalue(), "manuscript_expert_report.docx")

gc.collect()
