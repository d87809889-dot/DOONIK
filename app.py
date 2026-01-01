import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO
st.set_page_config(page_title="Manuscript AI Pro", layout="wide")

# --- 2. SECRETS TEKSHIRUV (ENG MUHIMI) ---
# Agar bular ishlamasa, saytda qizil yozuv chiqadi
if "GEMINI_API_KEY" not in st.secrets or "APP_PASSWORD" not in st.secrets:
    st.error("❌ Xatolik: Streamlit Cloud'da Secrets hali sozlanmagan!")
    st.write("Siz topa olmagan nomlar:", list(st.secrets.keys()))
    st.stop()

# Sirlarni o'zgaruvchiga olamiz
KEY = st.secrets["GEMINI_API_KEY"]
PWD = st.secrets["APP_PASSWORD"]

# --- 3. KIRISH TIZIMI ---
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Manuscript AI: Kirish")
    user_pass = st.text_input("Maxfiy parolni kiriting", type="password")
    if st.button("KIRISH"):
        if user_pass == PWD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Parol xato!")
    st.stop()

# --- 4. ASOSIY DASTUR ---
genai.configure(api_key=KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

st.title("📜 Qo'lyozmalar Ekspertizasi")
st.sidebar.title("Sozlamalar")
if st.sidebar.button("Chiqish"):
    st.session_state.auth = False
    st.rerun()

file = st.file_uploader("Fayl yuklang", type=['png', 'jpg', 'jpeg', 'pdf'])

if file:
    # Faylni xotirada saqlash (RAMni asrash uchun)
    if 'imgs' not in st.session_state or st.session_state.get('fn') != file.name:
        imgs = []
        if file.type == "application/pdf":
            pdf = pdfium.PdfDocument(file)
            for i in range(len(pdf)):
                imgs.append(pdf[i].render(scale=2).to_pil())
        else:
            imgs.append(Image.open(file))
        st.session_state.imgs = imgs
        st.session_state.fn = file.name
        st.session_state.res = {}

    # Ko'rsatish
    cols = st.columns(4)
    for i, img in enumerate(st.session_state.imgs):
        cols[i % 4].image(img, caption=f"{i+1}-varaq", use_container_width=True)

    if st.button("✨ TAHLILNI BOSHLASH"):
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"{i+1}-varaq tahlili..."):
                response = model.generate_content(["Ushbu qo'lyozmani tahlil qil:", img])
                st.session_state.res[i] = response.text
                st.write(response.text)

    # Wordga yuklash
    if st.session_state.res:
        doc = Document()
        for i, t in st.session_state.res.items():
            doc.add_paragraph(f"Varaq {i+1}:\n{t}")
        bio = io.BytesIO()
        doc.save(bio)
        st.download_button("📥 Word yuklash", bio.getvalue(), "report.docx")
