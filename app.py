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
    initial_sidebar_state="auto" # Mobil qurilmalarda qulaylik uchun
)

# --- PROFESSIONAL ANTIK DIZAYN + MOBIL OPTIMIZATSIYA (CSS) ---
st.markdown("""
    <style>
    /* 1. Ortiqcha reklamalarni yashirish */
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    /* 2. SIDEBAR TUGMASINI (TOGGLE) QAYTA TIKLASH VA BRENDLASH */
    /* Bu qism menyuni yopilganda yo'qolib qolmasligini ta'minlaydi */
    header[data-testid="stHeader"] {
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
    }
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        border-radius: 8px !important;
        inset: 10px !important;
    }
    button[data-testid="stSidebarCollapseButton"]:hover {
        background-color: #c5a059 !important;
        color: #0c1421 !important;
    }

    /* 3. Mobil qurilmalar uchun asosiy kontentni surish (Padding) */
    @media (max-width: 768px) {
        .main .block-container {
            padding-top: 3.5rem !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
    }

    /* 4. Akademik dizayn qismlari */
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    .magnifier-container {
        overflow: hidden;
        border: 2px solid #c5a059;
        border-radius: 10px;
        cursor: zoom-in;
    }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }

    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE) - DAXLSIZ
# ==========================================
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
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else:
                st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ!)
# ==========================================
genai.configure(api_key=GEMINI_KEY)
system_instruction = """
Siz "Manuscript AI" platformasining professional akademik AI mutaxassisiz. 
Ushbu tizim tadqiqotchi d87809889-dot tomonidan qadimiy qo'lyozmalarni tahlil qilish uchun yaratilgan.
Sizdan kimligingizni so'rashsa, "Men Manuscript AI mutaxassisiman" deb javob bering.
Har doim akademik, jiddiy va aniq tilda ma'lumot bering.
"""
model = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    system_instruction=system_instruction
)

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR - DAXLSIZ
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
# 5. TADQIQOT INTERFEYSI (MODERNIZED)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.u_email}**")
    live_credits = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
    
    st.divider()
    analysis_mode = st.radio("Yo'nalishni tanlang:", ["Diplomatik", "Semantik"])
    
    st.divider()
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)
    rotate_angle = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    
    st.divider()
    lang = st.selectbox("Hujjat tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Manuscript AI Center")
uploaded_file = st.file_uploader("Faylni yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

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
                for i in range(min(len(pdf), 20)):
                    imgs.append(render_page_optimized(file_bytes, i, 2.0, True))
                pdf.close()
            else: imgs.append(render_page_optimized(file_bytes, 0, 2.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    total_pages = len(st.session_state.imgs)
    selected_indices = st.multiselect("Sahifalarni tanlang:", options=range(total_pages), default=[0], format_func=lambda x: f"{x+1}-sahifa")

    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = img.rotate(rotate_angle, expand=True)
        p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        cred = fetch_live_credits(st.session_state.u_email)
        if cred >= len(selected_indices):
            prompt = f"Siz Manuscript AI mutaxassisiz. {lang} va {era} uslubidagi manbani {analysis_mode} tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Arxaik lug'at. 5.Izoh."
            for idx in selected_indices:
                with st.status(f"Sahifa {idx+1}...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                        st.session_state.results[idx] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label="Tayyor!", state="complete")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Kredit yetarli emas!")

    if st.session_state.results:
        st.divider()
        final_doc = ""
        today = datetime.now().strftime("%d.%m.%Y")
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                citation = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili. Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(f"Edit {idx+1}", value=res, height=350, key=f"ed_{idx}")
                final_doc += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{citation}"

                # Chat
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("..."):
                            chat_res = model.generate_content([f"Doc: {st.session_state.results[idx]}\nQ: {user_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc:
            doc = Document()
            doc.add_paragraph(final_doc)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 DOWNLOAD REPORT", bio.getvalue(), "report.docx")

gc.collect()
