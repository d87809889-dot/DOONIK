import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io
from docx import Document

# 1. API va Sahifa sozlamalari
genai.configure(api_key="AIzaSyDBKcljwRzHNCb__GtPu12WTIpeARe5-Ak")
model = genai.GenerativeModel('gemini-flash-lite-latest')

st.set_page_config(page_title="Manuscript AI", page_icon="📜", layout="wide")

# --- DIZAYN (Sidebar va CSS) ---
st.markdown("""<style> .main { background-color: #f5f7f9; } .stButton>button { width: 100%; border-radius: 20px; background-color: #4CAF50; color: white; } </style>""", unsafe_allow_html=True)

st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135783.png", width=100)
st.sidebar.title("Sozlamalar")
lang = st.sidebar.selectbox("Asl tilni tanlang:", ["Chig'atoy", "Fors", "Arab", "Noma'lum"])
detail = st.sidebar.slider("Tahlil chuqurligi:", 1, 5, 3)

st.title("📜 Qo'lyozma AI: Tarixni raqamlashtirish")
st.info("Eski qo'lyozma (PDF/Rasm) yuklang, AI uni lotinchaga o'girib tarjima qiladi.")

# 2. Fayl yuklash
uploaded_file = st.file_uploader("Faylni tanlang", type=['png', 'jpg', 'jpeg', 'pdf'])

if uploaded_file:
    images = []
    if uploaded_file.type == "application/pdf":
        pdf = pdfium.PdfDocument(uploaded_file)
        for i in range(len(pdf)):
            images.append(pdf[i].render(scale=2).to_pil())
    else:
        images.append(Image.open(uploaded_file))

    # Rasmlarni yonma-yon ko'rsatish
    cols = st.columns(len(images) if len(images) < 3 else 3)
    for idx, img in enumerate(images):
        cols[idx % 3].image(img, caption=f"{idx+1}-sahifa", use_container_width=True)

    # 3. Tahlil
    if st.button('Tahlilni boshlash ✨'):
        all_text = ""
        prompt = f"Siz {lang} tili bo'yicha mutaxassisiz. Daraja: {detail}. Matnni lotinchaga o'gir, o'zbekcha tarjima qil va tarixiy izoh ber."
        
        progress_bar = st.progress(0)
        for i, img in enumerate(images):
            with st.spinner(f"{i+1}-sahifa o'qilmoqda..."):
                response = model.generate_content([prompt, img])
                res_text = response.text
                st.subheader(f"📄 {i+1}-sahifa natijasi:")
                st.markdown(res_text)
                all_text += f"\n\n--- {i+1}-sahifa ---\n{res_text}"
            progress_bar.progress((i + 1) / len(images))
        
        # 4. Word fayl
        doc = Document()
        doc.add_heading('Manuscript AI: Tahlil natijalari', 0)
        doc.add_paragraph(f"Asl til: {lang}\n{all_text}")
        bio = io.BytesIO()
        doc.save(bio)
        
        st.download_button("📥 Natijani Wordda yuklab olish", bio.getvalue(), "tahlil.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        st.balloons()