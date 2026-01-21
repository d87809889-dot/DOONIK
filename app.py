import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance
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
    initial_sidebar_state="auto"
)

# --- PROFESSIONAL ANTIK DIZAYN + MOBIL FIX (CSS) ---
st.markdown("""
    <style>
    /* 1. Keraksiz menyularni yashirish, lekin TOGGLE (>) tugmasini saqlash */
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    header[data-testid="stHeader"] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }
    
    /* Mobil Menyu tugmasi oltin rangda doim ko'rinadi */
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        position: fixed !important;
        z-index: 1000001 !important;
    }

    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    /* Tahlil natijasi oynasi */
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 15px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.8;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    
    /* Chat pufakchalari - Har doim ko'rinadigan qora matn */
    .chat-user { background-color: #e2e8f0; color: #000 !important; padding: 12px; border-radius: 10px; margin-bottom: 5px; border-left: 5px solid #1e3a8a; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; }
    
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.5); transition: transform 0.3s ease; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (DAXLSIZ)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

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
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI ENGINE (Fixed: gemini-flash-latest)
# ==========================================
genai.configure(api_key=GEMINI_KEY)
system_instruction = 'Siz Manuscript AI professional matnshunosisiz. Tadqiqotchi d87809889-dot muallifligida ishlaysiz.'
model = genai.GenerativeModel(model_name='gemini-flash-latest', system_instruction=system_instruction)

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
    except: return None

# ==========================================
# 5. ASOSIY ILOVA
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    st.metric("💳 Kredit", f"{fetch_live_credits(st.session_state.u_email)}")
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    br = st.slider("Yorqinlik:", 0.5, 2.0, 1.0); ct = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    if st.button("🚪 LOGOUT"):
        st.session_state.auth = False; st.rerun()

st.title("📜 Manuscript AI Experts")
uploaded_file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Preparing...'):
            data = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)): imgs.append(render_page(data, i, 2.1, True))
                pdf.close()
            else: imgs.append(render_page(data, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}; gc.collect()

    # XATOLIKNI TUZATISH (KIMMATLI JOY): faqat rasm bo'lsa multiselect chiqadi
    if st.session_state.imgs:
        opts = list(range(len(st.session_state.imgs)))
        sel_pages = st.multiselect("Varaqlarni tanlang:", opts, default=[0] if opts else [], format_func=lambda x: f"Varaq {x+1}")

        # Rasmga ishlov berish
        processed_imgs = []
        for img in st.session_state.imgs:
            p_img = ImageEnhance.Brightness(img).enhance(br)
            p_img = ImageEnhance.Contrast(p_img).enhance(ct)
            processed_imgs.append(p_img)

        if not st.session_state.results:
            cols = st.columns(min(len(sel_pages), 4) if sel_pages else 1)
            for i, idx in enumerate(sel_pages):
                with cols[i % 4]:
                    st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", width=None)
                    st.markdown('</div>', unsafe_allow_html=True)

        if st.button('✨ TAHLILNI BOSHLASH'):
            credits = fetch_live_credits(st.session_state.u_email)
            if credits >= len(sel_pages):
                prompt = f"Expert paleographer analysis of {lang} ({style}). 1.Transliteration 2.Translation 3.Notes."
                for idx in sel_pages:
                    with st.status(f"Page {idx+1}...") as s:
                        try:
                            response = model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                            st.session_state.results[idx] = response.text
                            use_credit_atomic(st.session_state.u_email)
                            s.update(label="OK!", state="complete")
                        except Exception as e: st.error(f"Xato: {e}")
                st.rerun()
            else: st.warning("Limit Error!")

        if st.session_state.results:
            st.divider(); final_text = ""
            for idx in sorted(st.session_state.results.keys()):
                st.markdown(f"#### 📖 Varaq {idx+1}")
                res = st.session_state.results[idx]
                c1, c2 = st.columns([1, 1.2])
                with c1: st.image(processed_imgs[idx], use_container_width=True)
                with c2:
                    st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                    st.session_state.results[idx] = st.text_area(f"Edit {idx+1}", value=res, height=300, key=f"ed_{idx}")
                    final_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"
                    
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user' style='color:black;'>{ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai' style='color:black;'>{ch['a']}</div>", unsafe_allow_html=True)
                    
                    user_q = st.text_input("Savol bering:", key=f"q_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            chat_res = model.generate_content([f"Hujjat: {res}\nQ: {user_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text}); st.rerun()
            if final_text:
                doc = Document(); doc.add_paragraph(final_text); bio = io.BytesIO(); doc.save(bio)
                st.download_button("📥 WORD DOWNLOAD", bio.getvalue(), "report.docx")

gc.collect()
