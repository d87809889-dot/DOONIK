import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. SAHIFA SOZLAMALARI
st.set_page_config(page_title="Manuscript AI Pro", page_icon="📜", layout="wide")

# --- 2. XAVFSIZLIK (SECRETS) ---
# Agar Secrets noto'g'ri bo'lsa, Streamlit o'zi qizil xato chiqaradi
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
except Exception as e:
    st.error(f"Sirlar yuklanmadi. Xato: {e}")
    st.info("Streamlit Dashboard -> Settings -> Secrets bo'limini tekshiring.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Manuscript AI: Kirish")
    pwd_input = st.text_input("Maxfiy parolni kiriting", type="password")
    if st.button("Kirish"):
        if pwd_input == CORRECT_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Parol noto'g'ri!")
    st.stop()

# --- 3. ASOSIY DASTUR ---
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

st.sidebar.title("📜 MS AI PRO")
lang = st.sidebar.selectbox("Til:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
if st.sidebar.button("Chiqish"):
    st.session_state.authenticated = False
    st.rerun()

st.title("📜 Raqamli Qo'lyozmalar Ekspertizasi")
file = st.file_uploader("Hujjat yuklang", type=['png', 'jpg', 'jpeg', 'pdf'])

if file:
    if st.session_state.get('fn') != file.name:
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

    st.markdown("### 🖼 Varaqlar")
    cols = st.columns(4)
    for i, img in enumerate(st.session_state.imgs):
        cols[i % 4].image(img, caption=f"{i+1}-varaq", use_container_width=True)

    if st.button("✨ Tahlilni boshlash"):
        prompt = f"Siz matnshunos akademiksiz. {lang} tilidagi qo'lyozmani tahlil qiling."
        for i, img in enumerate(st.session_state.imgs):
            with st.status(f"{i+1}-varaq..."):
                response = model.generate_content([prompt, img])
                st.session_state.res[i] = response.text
    
    if st.session_state.res:
        doc_text = ""
        for i, txt in st.session_state.res.items():
            st.subheader(f"📖 Varaq {i+1}")
            st.write(txt)
            doc_text += f"\n\n--- Varaq {i+1} ---\n{txt}"
        
        doc = Document()
        doc.add_paragraph(doc_text)
        bio = io.BytesIO()
        doc.save(bio)
        st.download_button("📥 Word yuklash", bio.getvalue(), "tahlil.docx")
