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
    initial_sidebar_state="expanded"
)

# --- PROFESSIONAL ANTIK DIZAYN (KUCHAYTIRILGAN CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 12px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 25px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 17px; line-height: 1.7 !important;
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

# Google Verification
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
        st.markdown("<br><br><h2>🏛 AKADEMIK KIRISH</h2>", unsafe_allow_html=True)
        email_in = st.text_input("Emailingizni yozing")
        pwd_in = st.text_input("Maxfiy parolni yozing", type="password")
        if st.button("TIZIMGA KIRISH"):
            if pwd_in == CORRECT_PASSWORD:
                st.session_state.auth, st.session_state.u_email = True, email_in
                st.rerun()
            else: st.error("Parol noto'g'ri!")
    st.stop()

# ==========================================
# 3. AI MOTORINI SOZLASH (DAXLSIZ!)
# ==========================================
genai.configure(api_key=GEMINI_KEY)

# --- AI SHAXSIYATINI BELGILASH (Professional Identity) ---
system_instruction = f"""
Siz "Manuscript AI" platformasining maxsus sozlangan akademik yordamchisiz. 
Ushbu tizim tadqiqotchi d87809889-dot tomonidan yaratilgan.
Sizdan kim ekanligingizni so'rashsa, quyidagicha javob bering:
"Men "Manuscript AI" platformasining professional akademik AI yordamchisiman. Vazifam - tarixiy manbalarni o'rganishda sizga ko'maklashish."
Akademik mezonlarga rioya qiling.
"""

# MOTOR: gemini-flash-latest (O'zgartirilmadi)
model = genai.GenerativeModel(
    model_name='gemini-flash-latest',
    system_instruction=system_instruction
)

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

# ==========================================
# 5. TADQIQOT INTERFEYSI VA PDF BOSHQARUVI
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    st.markdown("---")
    st.write(f"👤 **{st.session_state.u_email}**")
    st.metric("💳 Qolgan kredit", f"{fetch_live_credits(st.session_state.u_email)} sahifa")
    
    st.divider()
    st.markdown("### 🛠 Restavratsiya Laboratoriyasi")
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast (Siyoh o'tkirligi):", 0.5, 3.0, 1.2)
    rotate_angle = st.select_slider("Aylantirish:", options=[0, 90, 180, 270], value=0)
    
    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Ilmiy manbani yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

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
                # Max 20 sahifa render
                for i in range(min(len(pdf), 20)):
                    imgs.append(pdf[i].render(scale=2.0).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))
            
            st.session_state.imgs = imgs
            st.session_state.last_fn = uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    # --- 5-FUNKSIYA: PDF Sahifalarini boshqarish ---
    total_pages = len(st.session_state.imgs)
    st.markdown(f"📦 Jami: **{total_pages} sahifa** aniqlandi.")
    
    selected_indices = st.multiselect(
        "Tahlil qilinadigan sahifalarni tanlang:",
        options=range(total_pages),
        default=[0],
        format_func=lambda x: f"{x+1}-sahifa"
    )

    # --- RESTAVRATSIYA QILINGAN TASVIRLARNI PREVYU QILISH ---
    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = img.rotate(rotate_angle, expand=True)
        p_img = ImageEnhance.Brightness(p_img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    if not st.session_state.results:
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            cols[i % 4].image(processed_imgs[idx], caption=f"{idx+1}-sahifa (Ishlov berilgan)", width='stretch')

    # TAHLIL BOSHLASH
    if st.button('✨ TANLANGAN SAHIFALARNI TAHLIL QILISH'):
        cred = fetch_live_credits(st.session_state.u_email)
        if cred >= len(selected_indices):
            # Promptga 2-FUNKSIYA: Glossariyni qo'shish
            prompt = f"""
            Siz dunyo darajasidagi matnshunos akademiksiz. Ushbu {lang} va {era} uslubidagi qo'lyozmani tahlil qiling:
            1. PALEOGRAFIK TAVSIF.
            2. TRANSLITERATSIYA (harfma-harf lotinchaga).
            3. SEMANTIK TARJIMA (o'zbek tiliga).
            4. AQLLI LUG'AT: Matndagi eng qiyin yoki arxaik 5-10 ta so'zning izohli lug'atini jadval ko'rinishida bering.
            5. ILMIY XULOSA.
            """
            for idx in selected_indices:
                with st.status(f"{idx+1}-sahifa ekspertizadan o'tmoqda...") as s:
                    try:
                        response = model.generate_content([prompt, img_to_payload(processed_imgs[idx])])
                        st.session_state.results[idx] = response.text
                        use_credit_atomic(st.session_state.u_email)
                        s.update(label=f"{idx+1}-sahifa yakunlandi!", state="complete")
                        time.sleep(1)
                    except Exception as e:
                        st.error(f"Xato: {e}")
            st.rerun()
        else:
            st.warning("Kredit yetarli emas! Tanlangan sahifalar sonini kamaytiring.")

    # --- NATIJALAR VA CHAT ---
    if st.session_state.results:
        st.divider()
        final_doc_text = ""
        today_date = datetime.now().strftime("%d.%m.%Y")
        
        for idx in sorted(st.session_state.results.keys()):
            st.markdown(f"#### 📖 Varaq {idx+1}")
            res = st.session_state.results[idx]
            c1, c2 = st.columns([1, 1.2])
            with c1: st.image(processed_imgs[idx], use_container_width=True)
            with c2:
                st.markdown(f"<div class='result-box'><b>Ekspertiza Xulosasi:</b><br><br>{res}</div>", unsafe_allow_html=True)
                
                # 3-FUNKSIYA: Avtomatik Iqtibos
                citation = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili. Ekspertiza tizimi: d87809889-dot. Sana: {today_date}."
                st.markdown(f"<div class='citation-box'>{citation}</div>", unsafe_allow_html=True)
                
                st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"edit_{idx}")
                final_doc_text += f"\n\n--- VARAQ {idx+1} ---\n{st.session_state.results[idx]}\n\n{citation}"

                # Interaktiv Chat
                st.markdown(f"##### 💬 Varaq {idx+1} bo'yicha savol-javob")
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user' style='color:black;'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                    if user_q:
                        with st.spinner("Manuscript AI tahlil qilmoqda..."):
                            chat_res = model.generate_content([f"Hujjat: {st.session_state.results[idx]}\nSavol: {user_q}", img_to_payload(processed_imgs[idx])])
                            st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                            st.rerun()
                st.markdown("---")

        if final_doc_text:
            doc = Document()
            doc.add_heading('Academic Manuscript Report - Enterprise Master Edition', 0)
            doc.add_paragraph(final_doc_text)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 WORDDA YUKLAB OLISH (GLOSSARIY VA IQTIBOS BILAN)", bio.getvalue(), "academic_report_pro.docx")
