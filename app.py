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
    page_title="Manuscript AI - Academic Master v20.0", 
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
    .result-box { background-color: #ffffff; padding: 25px; border-radius: 12px; border-left: 10px solid #c5a059; box-shadow: 0 10px 25px rgba(0,0,0,0.1); color: #1a1a1a !important; font-size: 17px; line-height: 1.7; margin-bottom: 20px; }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-bubble-user { background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 10px; border-radius: 8px; margin-bottom: 15px; border: 1px solid #d4af37; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100% !important; padding: 12px; border: 1px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 3. XAVFSIZLIK VA BAZA ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

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
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Email")
        pwd_in = st.text_input("Parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
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

# --- 6. ASOSIY ILOVA LOGIKASI ---
# Session state xotiralarini yaratish
if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.u_email}**")
    live_credits = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    if st.button("🚪 CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertizasi")
uploaded_file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Manba yuklanmoqda...'):
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
            st.session_state.results = {} # Noldan boshlash
            st.session_state.chats = {}
            gc.collect()

    # Prevyu (Agar natijalar hali bo'lmasa ko'rinadi)
    if not st.session_state.results:
        cols = st.columns(min(len(st.session_state.imgs), 4))
        for idx, img in enumerate(st.session_state.imgs):
            cols[idx % 4].image(img, caption=f"Varaq {idx+1}", width=None)

    # TAHLIL TUGMASI
    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        if live_credits >= len(st.session_state.imgs):
            prompt = f"Siz matnshunos akademiksiz. {lang} va {style} xatidagi ushbu qo'lyozmani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Izoh."
            
            # Progress bar yaratamiz
            progress_text = "Ekspertiza o'tkazilmoqda. Iltimos kuting..."
            my_bar = st.progress(0, text=progress_text)
            
            for i, img in enumerate(st.session_state.imgs):
                try:
                    # AIga so'rov yuborish
                    response = model.generate_content([prompt, img_to_payload(img)])
                    st.session_state.results[i] = response.text
                    
                    # Kreditni bazada kamaytirish
                    db.table("profiles").update({"credits": live_credits - 1}).eq("email", st.session_state.u_email).execute()
                    live_credits -= 1
                    
                    # Progressni yangilash
                    percent = int(((i + 1) / len(st.session_state.imgs)) * 100)
                    my_bar.progress(percent, text=f"{i+1}-sahifa tayyor...")
                except Exception as e:
                    st.error(f"Xato (Varaq {i+1}): {e}")
            
            st.rerun() # Hammasi tugagach natijalarni ko'rsatish uchun sahifani yangilaymiz
        else:
            st.warning("Kredit yetarli emas!")

# --- NATIJALARNI KO'RSATISH (TUGMADAN TASHQARIDA - DOIM KO'RINADI) ---
if st.session_state.results:
    st.divider()
    st.markdown("### 🖋 Ekspertiza Natijalari")
    final_report = ""

    for idx, img in enumerate(st.session_state.imgs):
        if idx in st.session_state.results:
            res = st.session_state.results[idx]
            st.markdown(f"#### 📖 Varaq {idx+1}")
            c1, c2 = st.columns([1, 1.2])
            
            with c1:
                st.image(img, use_container_width=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>AI Akademik Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                # Tahrirlash oynasi
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"edit_{idx}")
                final_report += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"

                # Chat
                st.markdown(f"##### 💬 Varaq {idx+1} muloqoti")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-bubble-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-bubble-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                # Savol yuborish
                chat_input_key = f"input_{idx}"
                user_q = st.text_input("Savol bering:", key=chat_input_key)
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("AI tahlil qilmoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(img)])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
            st.markdown("---")

    if final_report:
        doc = Document()
        doc.add_heading('Academic Manuscript Report', 0)
        doc.add_paragraph(final_report)
        bio = io.BytesIO(); doc.save(bio)
        st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "academic_report.docx")
