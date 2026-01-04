import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Enterprise Master v19.0", 
    page_icon="📜", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; }
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; line-height: 1.7; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100%; padding: 12px; border: 1px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA BAZA ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    db = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Email", placeholder="Emailingizni yozing...")
        pwd_in = st.text_input("Parol", type="password", placeholder="Maxfiy kod...")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Xato!")
    st.stop()

# --- 4. AI SOZLASH (BARQAROR V1) ---
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 5. YORDAMCHI FUNKSIYALAR ---
def img_to_payload(img):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except: return 0

# --- 6. ASOSIY ILOVA ---
# Sidebar
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.u_email}**")
    live_credits = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
    st.divider()
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

# Session state xotirasi (Natijalar yo'qolmasligi uchun)
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
                    imgs.append(page.render(scale=2).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results = {}
            st.session_state.chats = {}
            gc.collect()

    # Prevyu
    cols = st.columns(min(len(st.session_state.imgs), 4))
    for idx, img in enumerate(st.session_state.imgs):
        cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width=None)

    # TAHLIL TUGMASI
    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        if live_credits >= len(st.session_state.imgs):
            prompt = f"Siz matnshunos akademiksiz. {lang} va {style} uslubidagi ushbu manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
            for i, img in enumerate(st.session_state.imgs):
                with st.status(f"Varaq {i+1} o'qilmoqda...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(img)])
                        # NATIJANI SESSION STATE'GA YOZAMIZ
                        st.session_state.results[i] = response.text
                        s.update(label=f"Varaq {i+1} tayyor!", state="complete")
                        # Kreditni kamaytirish
                        db.table("profiles").update({"credits": live_credits - 1}).eq("email", st.session_state.u_email).execute()
                        live_credits -= 1
                    except Exception as e:
                        st.error(f"Xato: {e}")
            st.rerun() # Hammasi tugagach bir marta yangilaymiz
        else:
            st.warning("Kredit yetarli emas!")

    # --- NATIJALARNI CHIQARISH (BUTTON'DAN TASHQARIDA) ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        for idx, img in enumerate(st.session_state.imgs):
            if idx in st.session_state.results:
                res = st.session_state.results[idx]
                st.markdown(f"#### 📖 Varaq {idx+1}")
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(img, use_container_width=True)
                with c2: st.markdown(f"<div class='result-box'><b>AI Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                # Tahrirlash
                ed_val = st.text_area(f"Tahrir {idx+1}:", value=res, height=400, key=f"ed_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{ed_val}"

                # Chat
                st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-bubble-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("AI o'ylamoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {ed_val}\nSavol: {user_q}", img_to_payload(img)])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "report.docx")

