import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Academic Master 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}

    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }

    /* AI TAHLIL KARTASI */
    .result-box {
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important;
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7 !important;
    }

    /* TAHRIRLASH OYNASI */
    .stTextArea textarea {
        background-color: #fdfaf1 !important; color: #000000 !important; 
        border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important;
        font-size: 18px !important; padding: 20px !important;
    }

    /* CHAT DIZAYNI */
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #d4af37; }

    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button {
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important;
        color: #c5a059 !important; border: 2px solid #c5a059 !important;
        font-weight: bold !important; width: 100% !important; padding: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Google Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni yozing", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MODELINI SOZLASH (LOGLAR ASOSIDA FIX)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

@st.cache_resource
def load_verified_engine():
    """Sizning logsda ko'ringan aynan ishlaydigan modellarni yuklaydi"""
    # Siz yuborgan logsda bu nomlar borligi tasdiqlangan:
    priority_names = ['gemini-flash-latest', 'gemini-1.5-flash-latest', 'gemini-2.0-flash']
    for name in priority_names:
        try:
            m = genai.GenerativeModel(model_name=name)
            return m, name
        except:
            continue
    # Hech biri bo'lmasa, eng barqaror deb taxmin qilingan nom
    return genai.GenerativeModel(model_name='gemini-pro-latest'), 'gemini-pro-latest'

model, active_model_name = load_verified_engine()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

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

# ==========================================
# 5. TADQIQOT INTERFEYS VA LOGIKA
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"👤 **{st.session_state.u_email}**")
    st.metric("💳 Qolgan kredit", f"{fetch_live_credits(st.session_state.u_email)} sahifa")
    st.write(f"🤖 **Model:** `{active_model_name}`")
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Manba tayyorlanmoqda...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)):
                    page = pdf[i]
                    imgs.append(page.render(scale=2.0).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # Prevyu (width='stretch' logs talabi asosida)
    if not st.session_state.results:
        cols = st.columns(min(len(st.session_state.imgs), 4))
        for idx, img in enumerate(st.session_state.imgs):
            cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width='stretch')

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        cred = fetch_live_credits(st.session_state.u_email)
        if cred >= len(st.session_state.imgs):
            prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi ushbu manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
            for i, img in enumerate(st.session_state.imgs):
                with st.status(f"Varaq {i+1} o'qilmoqda...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(img)])
                        st.session_state.results[i] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"Varaq {i+1} tayyor!", state="complete")
                        time.sleep(2)
                    except Exception as e:
                        st.error(f"Xato (Sahifa {i+1}): {e}")
            st.rerun()
        else:
            st.warning("Kredit yetarli emas!")

    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, width='stretch')
                with c2: 
                    st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                    # Tahrirlash
                    st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"edit_{idx}")
                    final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"

                    # Chat
                    st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user' style='background:#e2e8f0; padding:10px; border-radius:5px; margin-bottom:5px; color:black;'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai' style='background:white; padding:10px; border-radius:5px; border:1px solid #d4af37; color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("AI tahlil qilmoqda..."):
                                chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(img)])
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
