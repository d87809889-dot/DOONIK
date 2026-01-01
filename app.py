import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SEO VA SAHIFA SOZLAMALARI
st.set_page_config(page_title="Manuscript AI - Diagnostic Mode", page_icon="📜", layout="wide")

# --- 2. XAVFSIZLIK (DEBUG REJIMIDA) ---
# Biz hozir Streamlit nima ko'rayotganini tekshiramiz
available_secrets = list(st.secrets.keys())

if "GEMINI_API_KEY" not in available_secrets or "APP_PASSWORD" not in available_secrets:
    st.error("❌ SOZLAMALARDA XATO BOR!")
    st.write("Streamlit Secrets bo'limida quyidagi nomlar bo'lishi shart:")
    st.code("GEMINI_API_KEY\nAPP_PASSWORD")
    st.write(f"Hozir tizimda bor nomlar: `{available_secrets}`")
    st.info("Dashboard -> Settings -> Secrets bo'limiga kiring va nomlarni tekshiring.")
    st.stop()

# Agar hamma narsa bor bo'lsa, davom etamiz
API_KEY = st.secrets["GEMINI_API_KEY"]
CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔐 Manuscript AI: Kirish")
    pwd = st.text_input("Parol", type="password")
    if st.button("KIRISH"):
        if pwd == CORRECT_PASSWORD:
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("Xato parol!")
    st.stop()

# --- 3. ASOSIY DASTUR ---
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.sidebar.title("📜 MS AI PRO")
if st.sidebar.button("Chiqish"):
    st.session_state.auth = False
    st.rerun()

st.title("📜 Qo'lyozmalar Ekspertizasi")
file = st.file_uploader("Faylni yuklang", type=['png', 'jpg', 'jpeg', 'pdf'])

if file:
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

    if st.button("✨ Tahlilni boshlash"):
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"{i+1}-varaq tahlil qilinmoqda..."):
                response = model.generate_content(["Qo'lyozmani tahlil qil:", img])
                st.session_state.res[i] = response.text
                st.write(response.text)

    if st.session_state.get('res'):
        doc = Document()
        for i, t in st.session_state.res.items():
            doc.add_paragraph(f"Varaq {i+1}:\n{t}")
        bio = io.BytesIO()
        doc.save(bio)
        st.download_button("📥 Word yuklash", bio.getvalue(), "report.docx")
