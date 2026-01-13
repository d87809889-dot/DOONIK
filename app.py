import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps
import pypdfium2 as pdfium
import io, gc, hashlib, time, base64
from datetime import datetime
from docx import Document
from supabase import create_client, Client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI Platinum - Scientific Edition",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 30px !important; border-radius: 15px !important; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        color: #000; font-size: 18px; line-height: 1.9;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; font-size: 17px; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; height: 55px; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 15px; cursor: zoom-in; }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }
    .methodology-note { font-size: 14px; color: #5d4037; background: #e7d8c1; padding: 15px; border-radius: 8px; border: 1px dashed #0c1421; margin-top: 20px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Google Search Console Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. XAVFSIZLIK VA BAZA (SUPABASE)
# ==========================================
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = ""

try:
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Secrets sozlanmagan! Settings > Secrets qismini tekshiring.")
    st.stop()

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA PORTALI</h2>", unsafe_allow_html=True)
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
# 3. AI MOTORINI SOZLASH (SAFETY & 404 FIX)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

# --- XAVFSIZLIK FILTRLARINI O'CHIRISH ---
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

system_instruction = """
Siz Manuscript AI tizimining professional matnshunos va paleografisiz. 
Vazifangiz: har bir grafik belgini tahlil qilish va ilmiy xulosa berish.
"""

@st.cache_resource
def load_expert_engine():
    priority_list = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-flash-latest']
    for name in priority_list:
        try:
            return genai.GenerativeModel(model_name=name, system_instruction=system_instruction, safety_settings=safety_settings)
        except: continue
    return genai.GenerativeModel(model_name='gemini-1.5-flash', system_instruction=system_instruction, safety_settings=safety_settings)

model = load_expert_engine()

# ==========================================
# 4. YORDAMCHI FUNKSIYALAR (XATO TUZATILDI)
# ==========================================
def enhance_image_for_ai(img: Image.Image):
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageOps.equalize(img)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img

def img_to_png_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

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
def render_page_high_res(file_content, page_idx, scale, is_pdf):
    """XATO TUZATILDI: Endi scale (zoom) argumentini to'g'ri qabul qiladi"""
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            gc.collect()
            return img
        else:
            return Image.open(io.BytesIO(file_content))
    except:
        return None

# ==========================================
# 5. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **User:** `{st.session_state.u_email}`")
    live_c = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_c} sahifa")
    st.divider()
    lang_sel = st.selectbox("Filologik yo'nalish:", ["Chig'atoy (Eski o'zbek)", "Forscha", "Arabcha", "Usmonli Turk"])
    era_sel = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Devoniy", "Noma'lum"])
    st.divider()
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Siyoh o'tkirligi:", 0.5, 3.0, 1.3)
    rotate_val = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Matnshunoslik va Ekspertiza Markazi")
uploaded_file = st.file_uploader("Ilmiy manbani yuklang", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if 'imgs' not in st.session_state: st.session_state.imgs = []
if 'results' not in st.session_state: st.session_state.results = {}
if 'chats' not in st.session_state: st.session_state.chats = {}

if uploaded_file:
    if st.session_state.get('last_fn') != uploaded_file.name:
        with st.spinner('Manba yuklanmoqda...'):
            file_bytes = uploaded_file.getvalue()
            imgs = []
            if uploaded_file.type == "application/pdf":
                pdf = pdfium.PdfDocument(file_bytes)
                for i in range(min(len(pdf), 15)):
                    # PDF uchun argumentlar: bytes, index, scale, is_pdf=True
                    imgs.append(render_page_high_res(file_bytes, i, 3.8, True))
                pdf.close()
            else:
                # Rasm uchun argumentlar: bytes, index=0, scale=1.0, is_pdf=False
                imgs.append(render_page_high_res(file_bytes, 0, 1.0, False))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = img.rotate(rotate_val, expand=True)
        p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    selected_indices = st.multiselect("Tahlil uchun varaqni tanlang:", range(len(processed_imgs)), default=[0], format_func=lambda x: f"{x+1}-varaq")

    if not st.session_state.results:
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ CHUQUR AKADEMIK EKSPERTIZANI BOSHLASH'):
        if live_c >= len(selected_indices):
            prompt = f"""
            Ushbu {lang_sel} manbasini ({era_sel} xati) Akademik Oltin Standart asosida tahlil qiling.
            Vazifani qat'iy ravishda quyidagi tartibda bajaring:
            I. TO'LIQ SEMANTIK TARJIMA (Zamonaviy o'zbek tili).
            II. FILOLOGIK EKSPERTIZA: 
            1. Asl matn. 2. Transliteratsiya (lotin). 3. Paleografik tavsif. 4. Tanqidiy izohlar.
            """
            for idx in selected_indices:
                with st.status(f"Varaq {idx+1} tahlil qilinmoqda...") as s:
                    try:
                        ai_img = enhance_image_for_ai(processed_imgs[idx])
                        response = model.generate_content([prompt, img_to_png_payload(ai_img)])
                        if response.candidates and response.candidates[0].content.parts:
                            st.session_state.results[idx] = response.text
                            use_credit_atomic(st.session_state.u_email)
                            s.update(label=f"Varaq {idx+1} yakunlandi!", state="complete")
                        else:
                            st.error(f"Xatolik: AI bloklandi. Sababi: {response.candidates[0].finish_reason}")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Limit tugagan!")

    if st.session_state.results:
        st.divider()
        final_text = ""
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<div class='methodology-note'>Metodologiya: Lachmann-Lotin Transliteratsiyasi qo'llanildi.</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                final_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}"

                # Interaktiv Chat
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("Manuscript AI o'ylanmoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_png_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Platinum Edition', 0)
            doc.add_paragraph(final_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD HISOBOTNI YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

    gc.collect()
