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
    page_title="Manuscript AI - Open Academic Portal",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="collapsed" # Mobil qurilmalarda yopiq holda ochiladi
)

# --- PROFESSIONAL ANTIK DIZAYN + MOBIL OPTIMIZATSIYA ---
st.markdown("""
    <style>
    /* Streamlit reklamalarini va menyularini yashirish */
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    #stDecoration {display:none !important;}
    
    /* Mobil qurilmalar uchun menyu tugmasini (>) tiklash */
    header[data-testid="stHeader"] { background: rgba(0,0,0,0) !important; visibility: visible !important; }
    button[data-testid="stSidebarCollapseButton"] {
        background-color: #0c1421 !important;
        color: #c5a059 !important;
        border: 1px solid #c5a059 !important;
        border-radius: 8px !important;
    }

    /* Fon va shriftlar */
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; font-family: 'Georgia', serif; border-bottom: 2px solid #c5a059; text-align: center; padding-bottom: 10px; }
    
    @media (max-width: 768px) {
        .main .block-container { padding-top: 3.5rem !important; }
    }

    /* Natija oynasi */
    .result-box { 
        background-color: #ffffff !important; padding: 25px !important; border-radius: 15px !important; 
        border-left: 10px solid #c5a059 !important; box-shadow: 0 10px 30px rgba(0,0,0,0.1) !important;
        color: #1a1a1a !important; font-size: 18px; line-height: 1.8;
    }
    
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 1px solid #c5a059 !important; }
    .chat-user { background-color: #e2e8f0; color: #000; padding: 12px; border-radius: 10px; border-left: 5px solid #1e3a8a; margin-bottom: 5px; }
    .chat-ai { background-color: #ffffff; color: #1a1a1a; padding: 12px; border-radius: 10px; border: 1px solid #d4af37; margin-bottom: 15px; }
    
    section[data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    section[data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold !important; width: 100% !important; padding: 10px !important; border: 1px solid #c5a059; }
    .magnifier-container { overflow: hidden; border: 2px solid #c5a059; border-radius: 10px; cursor: zoom-in; }
    .magnifier-container img { transition: transform 0.3s ease; }
    .magnifier-container:hover img { transform: scale(2.5); }
    .premium-alert { background: #fff3e0; border: 1px solid #ffb74d; padding: 15px; border-radius: 10px; text-align: center; color: #e65100; font-weight: bold; margin-bottom: 15px; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SERVICES (SUPABASE & AI MOTOR)
# ==========================================
@st.cache_resource
def get_db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db()
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel(model_name='gemini-flash-latest')

# --- SESSYA HOLATI ---
if "auth" not in st.session_state: st.session_state.auth = False
if "u_email" not in st.session_state: st.session_state.u_email = "Mehmon"

# ==========================================
# 3. SIDEBAR (LOGOTIP VA LOGIN INTEGRATSIYASI)
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='color:#c5a059; text-align:center;'>📜 MS AI PRO</h2>", unsafe_allow_html=True)
    
    # AGAR LOGIN QILMAGAN BO'LSA SIDEBARDA KO'RSATISH
    if not st.session_state.auth:
        st.markdown("### 🔑 Tizimga kirish")
        st.caption("Kreditlaringizdan foydalanish uchun kiring.")
        email_in = st.text_input("Email", placeholder="example@mail.com")
        pwd_in = st.text_input("Parol", type="password", placeholder="****")
        if st.button("KIRISH"):
            if pwd_in == st.secrets["APP_PASSWORD"]:
                st.session_state.auth = True
                st.session_state.u_email = email_in
                st.rerun()
            else:
                st.error("Xato!")
    else:
        st.write(f"👤 **Foydalanuvchi:** `{st.session_state.u_email}`")
        # Kreditlarni bazadan olish funksiyasi
        try:
            res = db.table("profiles").select("credits").eq("email", st.session_state.u_email).single().execute()
            live_credits = res.data["credits"] if res.data else 0
        except: live_credits = 0
        st.metric("💳 Kreditlar", f"{live_credits} sahifa")
        if st.button("🚪 TIZIMDAN CHIQISH"):
            st.session_state.auth = False
            st.session_state.u_email = "Mehmon"
            st.rerun()

    st.divider()
    lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    brightness = st.slider("Yorqinlik:", 0.5, 2.0, 1.0)
    contrast = st.slider("Kontrast:", 0.5, 3.0, 1.2)

# ==========================================
# 4. ASOSIY TADQIQOT INTERFEYSI (OCHIQ ESHIK)
# ==========================================
st.title("📜 Manuscript AI Center")
st.markdown("<p style='text-align:center;'>Qadimiy hujjatlarni yuklang va AI yordamida tahlil qiling.</p>", unsafe_allow_html=True)

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
                    imgs.append(pdf[i].render(scale=2.0).to_pil())
                pdf.close()
            else:
                imgs.append(Image.open(io.BytesIO(file_bytes)))
            st.session_state.imgs, st.session_state.last_fn = imgs, uploaded_file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()

    processed_imgs = []
    for img in st.session_state.imgs:
        p_img = ImageEnhance.Brightness(img).enhance(brightness)
        p_img = ImageEnhance.Contrast(p_img).enhance(contrast)
        processed_imgs.append(p_img)

    selected_indices = st.multiselect("Sahifalarni tanlang:", options=range(len(processed_imgs)), default=[0], format_func=lambda x: f"{x+1}-sahifa")

    if not st.session_state.results:
        cols = st.columns(min(len(selected_indices), 4) if selected_indices else 1)
        for i, idx in enumerate(selected_indices):
            with cols[i % 4]:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed_imgs[idx], caption=f"Varaq {idx+1}", width='stretch')
                st.markdown('</div>', unsafe_allow_html=True)

    if st.button('✨ AKADEMIK TAHLILNI BOSHLASH'):
        # Tahlil logikasi hamma uchun ochildi
        prompt = f"Siz Manuscript AI mutaxassisiz. {lang} va {era} uslubidagi manbani tahlil qiling: 1.Paleografiya. 2.Transliteratsiya. 3.Tarjima. 4.Arxaik lug'at. 5.Izoh."
        for idx in selected_indices:
            with st.status(f"Sahifa {idx+1}...") as s:
                try:
                    buf = io.BytesIO(); processed_imgs[idx].save(buf, format="JPEG")
                    payload = {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("utf-8")}
                    response = model.generate_content([prompt, payload])
                    st.session_state.results[idx] = response.text
                    # Agar login qilgan bo'lsa kreditni kamaytirish
                    if st.session_state.auth:
                        db.table("profiles").update({"credits": live_credits - 1}).eq("email", st.session_state.u_email).execute()
                    s.update(label="Tayyor!", state="complete")
                except Exception as e: st.error(f"Xato: {e}")
        st.rerun()

    # --- NATIJALAR ---
    if st.session_state.results:
        st.divider()
        final_doc = ""
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
                
                # --- PREMIUM LOCK: WORD VA CHATNI BERKITISH ---
                if not st.session_state.auth:
                    st.markdown("<div class='premium-alert'>🔒 Word hisobotni yuklab olish va AI Chat uchun tizimga kiring!</div>", unsafe_allow_html=True)
                else:
                    st.session_state.results[idx] = st.text_area(f"Tahrir ({idx+1}):", value=res, height=350, key=f"ed_{idx}")
                    final_doc += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}"

                    # Chat
                    st.session_state.chats.setdefault(idx, [])
                    for ch in st.session_state.chats[idx]:
                        st.markdown(f"<div class='chat-user'><b>S:</b> {ch['q']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div class='chat-ai' style='color:black;'><b>AI:</b> {ch['a']}</div>", unsafe_allow_html=True)

                    user_q = st.text_input("Savol bering:", key=f"q_in_{idx}")
                    if st.button(f"So'rash {idx+1}", key=f"btn_{idx}"):
                        if user_q:
                            with st.spinner("..."):
                                chat_res = model.generate_content([f"Doc: {st.session_state.results[idx]}\nQ: {user_q}"])
                                st.session_state.chats[idx].append({"q": user_q, "a": chat_res.text})
                                st.rerun()
                st.markdown("---")

        if st.session_state.auth and final_doc:
            doc = Document()
            doc.add_paragraph(final_doc)
            bio = io.BytesIO(); doc.save(bio)
            st.download_button("📥 DOWNLOAD REPORT", bio.getvalue(), "report.docx")

gc.collect()
