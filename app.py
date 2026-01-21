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
    page_title="Manuscript AI - Global Academic v26.0",
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
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a !important; font-size: 18px; line-height: 1.8;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 10px; border-radius: 8px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #000000 !important; padding: 10px; border-radius: 8px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img:hover { transform: scale(2.5); transition: transform 0.3s ease; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI)
# ==========================================
# Siz yuborgan barqaror ma'lumotlar bilan ulanish
@st.cache_resource
def init_services():
    url = "https://rjovrqronnohvyqvhgxx.supabase.co"
    key = st.secrets["SUPABASE_KEY"] # Maxfiy saqlangan kalit
    db_client = create_client(url, key)
    
    # ⚠️ QAT'IY BELGILANGAN MODEL (404 va 429 xatolarini yechimi shu)
    api_key = "AIzaSyBAdOCQDBoan8rH6SK8gbxTf4y8k7RE--s"
    genai.configure(api_key=api_key)
    # models/gemini-1.5-flash -> bu nomi v1 (stable) yo'lagidan ishlaydi
    engine = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
    
    return db_client, engine

db, ai_model = init_services()

# --- SESSYA HOLATI ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================
def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    # PNG formatida yuborish harf nuqtalarini saqlab qoladi (Lossless)
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
def render_page_optimized(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            gc.collect()
            return img
        return Image.open(io.BytesIO(file_content))
    except: return None

# ==========================================
# 4. SIDEBAR (BOSHQARUV PANELI)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    
    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Parol", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol xato!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        st.metric("💳 Kreditlar", fetch_live_credits(st.session_state.u_email))
        st.write("🤖 Model: **Gemini 1.5 Flash (Stable)**")
        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    st.divider()
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

# ==========================================
# 5. ASOSIY TADQIQOT INTERFEYSI
# ==========================================
st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Fayl raqamlashtirilmoqda...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                # Xotira uchun max 15 sahifa, DPI 200 (scale=2.1)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page_optimized(file_bytes, i, 2.1, True))
                pdf.close()
            else:
                imgs.append(render_page_optimized(file_bytes, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    selected_pages = st.multiselect("Varaqlarni tanlang:", range(len(st.session_state.imgs)), default=[0], format_func=lambda x: f"Varaq {x+1}")

    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(selected_pages), 4) if selected_pages else 1)
        for i, idx in enumerate(selected_pages):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        if not st.session_state.auth:
            st.warning("Tahlil uchun sidebar orqali kirish qiling!")
        else:
            live_c = fetch_live_credits(st.session_state.u_email)
            if live_c >= len(selected_pages):
                prompt = f"""
                Siz matnshunos akademiksiz. Ushbu {lang} qo'lyozmasini ({style} xati) tahlil qiling.
                Vazifa: 1.Transliteratsiya. 2.O'zbekcha akademik tarjima. 3.Tarixiy-paleografik izoh. 
                Ismlar va shubhali so'zlarni foiz ko'rsatkichi bilan qavsda bering.
                """
                for idx in selected_pages:
                    with st.status(f"Varaq {idx+1} tahlil qilinmoqda...") as s:
                        try:
                            response = ai_model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                            st.session_state.results[idx] = response.text
                            use_credit_atomic(st.session_state.u_email)
                            s.update(label=f"Varaq {idx+1} tayyor!", state="complete")
                            time.sleep(4) # Limit (RPM) xavfsizligi
                        except Exception as e: st.error(f"AI Xatosi: {e}")
                st.rerun()
            else: st.warning("Kredit yetarli emas!")

    # --- NATIJALAR ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today_date = datetime.now().strftime("%d.%m.%Y")
        
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>Ekspertiza Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                citation = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} ({lang}). Ekspert: d87809889-dot. Sana: {today_date}."
                st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                
                # Tahrirlash
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}\n\n{citation}"

                # Chat
                st.markdown(f"##### 💬 Varaq {idx+1} bo'yicha savol-javob")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI Javobi:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("Manuscript AI tahlil qilmoqda..."):
                            # Chatda rasm yubormaslik (tejamkorlik va 429 dan qutulish siri)
                            chat_res = ai_model.generate_content(f"Kontekst (Hujjat): {res}\nSavol: {user_q}")
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Premium Edition', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

gc.collect()
