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
    page_title="Manuscript AI Platinum - Scientific Edition",
    page_icon="🏛",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN + LUPA EFFEKTI (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    .result-box { 
        background-color: #ffffff !important; padding: 30px !important; border-radius: 15px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 40px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 18px; line-height: 1.9;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-family: 'Courier New', monospace !important; font-size: 17px; }
    .chat-user { background-color: #e2e8f0; color: #000000 !important; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a !important; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 12px !important; border: 1px solid #c5a059; height: 55px; }
    
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 15px; cursor: zoom-in; }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }
    
    .methodology-note { font-size: 14px; color: #5d4037; background: #e7d8c1; padding: 15px; border-radius: 8px; border: 1px dashed #0c1421; margin-top: 20px; font-style: italic; }
    .citation-box { font-size: 13px; color: #5d4037; background: #efebe9; padding: 12px; border-radius: 8px; border: 1px dashed #c5a059; margin-top: 15px; font-style: italic; }
    </style>
""", unsafe_allow_html=True)

# Google Verification
st.markdown('<meta name="google-site-verification" content="VoHbKw2CuXghxz44hvmjYrk4s8YVChQTMfrgzuldQG0" />', unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI MOTOR)
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
        st.markdown("<br><br><h2>🏛 AKADEMIK EKSPERTIZA PORTALI</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni kiriting", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
    st.stop()

# --- AI MOTORINI SOZLASH ---
genai.configure(api_key=GEMINI_KEY)
system_instruction = """
Siz Manuscript AI tizimining dunyo darajasidagi matnshunos, paleograf va tilshunos olimisiz. 
Sizning vazifangiz manbalarni Lachmann metodologiyasi va ilmiy-tanqidiy (critical edition) talablar asosida tahlil qilishdir.
Siz mutlaq aniqlikka intilasiz va noaniq joylar uchun ilmiy variantlarni ehtimollik foizi bilan taqdim etasiz.
"""
model = genai.GenerativeModel(model_name='gemini-flash-latest', system_instruction=system_instruction)

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (ADVANCED)
# ==========================================
def enhance_image_for_ai(img: Image.Image):
    """Rasmni tahlildan oldin raqamli restavratsiya qilish (Optimal)"""
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageOps.equalize(img)
    img = ImageEnhance.Contrast(img).enhance(2.8)
    img = ImageEnhance.Sharpness(img).enhance(2.5)
    return img

def img_to_png_payload(img: Image.Image):
    """Lossless PNG formatida API yuborish"""
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
def render_page_high_res(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
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
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.write(f"👤 **{st.session_state.u_email}**")
    live_c = fetch_live_credits(st.session_state.u_email)
    st.metric("💳 Qolgan kredit", f"{live_c} sahifa")
    st.divider()
    
    lang_sel = st.selectbox("Filologik yo'nalish:", ["Chig'atoy (Eski o'zbek)", "Fors (Klassik)", "Arab (Ilmiy)", "Eski Turkiy"])
    era_sel = st.selectbox("Paleografik uslub:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Devoniy", "Noma'lum"])
    
    st.divider()
    st.markdown("### 🛠 Tasvir Laboratoriyasi")
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
                    imgs.append(render_page_high_res(file_bytes, i, 3.8, True))
                pdf.close()
            else: imgs.append(render_page_high_res(file_bytes, 0, 1.0, False))
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
        st.info("💡 Maslahat: Kattalashtirish uchun sichqonchani rasm ustiga olib boring (Raqamli Lupa).")
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ CHUQUR AKADEMIK EKSPERTIZANI BOSHLASH'):
        if live_c >= len(selected_indices):
            # --- AKADEMIK OLTIN PROMPT (Confidence foizi bilan) ---
            prompt = f"""
            Ushbu {lang_sel} manbasini ({era_sel} xati) Akademik Oltin Standart (Platinum) asosida tahlil qiling.
            Vazifani qat'iy ravishda quyidagi tartibda bajaring:

            I. TO'LIQ SEMANTIK TARJIMA: Manbani zamonaviy o'zbek adabiy tiliga mukammal tarjima qiling.
            II. FILOLOGIK EKSPERTIZA:
            1. RAW TRANSCRIPTION: Matnni asl arab-fors imlosida o'zgarishsiz ko'chiring.
            2. DIPLOMATIC TRANSLITERATION: Harfma-harf lotin alifbosiga o'giring. Ismlar va sanalar uchun variantlarni ehtimollik foizi bilan bering: "Variant A [90%] / Variant B [10%]".
            3. PALEOGRAFIK TAVSIF: Yozuv uslubi va xattotlik xususiyatlari.
            4. TANQIDIY IZOHLAR: Tarixiy shaxslar va arxaik so'zlarga ilmiy sharh.
            """
            for idx in selected_indices:
                with st.status(f"Varaq {idx+1} ekspertizadan o'tkazilmoqda...") as s:
                    try:
                        ai_ready_img = enhance_image_for_ai(processed_imgs[idx])
                        response = model.generate_content([prompt, img_to_png_payload(ai_ready_img)])
                        st.session_state.results[idx] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"Varaq {idx+1} yakunlandi!", state="complete")
                    except Exception as e: st.error(f"Xato: {e}")
            st.rerun()
        else: st.warning("Limit tugagan!")

    # --- NATIJALAR VA CHAT ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today = datetime.now().strftime("%d.%m.%Y")
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)
                st.markdown("<div class='methodology-note'>Metodologiya: Lachmann-Lotin Transliteratsiyasi va PNG lossless rendering qo'llanildi.</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<div class='result-box'>{res}</div>", unsafe_allow_html=True)
                
                citation = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili. Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}\n\n{citation}"

                # Interaktiv Chat
                st.markdown(f"##### 💬 Varaq {idx+1} yuzasidan ilmiy muloqot")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("..."):
                            chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Platinum Edition', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORD HISOBOTINI YUKLAB OLISH", bio.getvalue(), "expert_report.docx")

    gc.collect()

