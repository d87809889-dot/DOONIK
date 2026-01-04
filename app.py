import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io
import gc
import asyncio
import base64
import hashlib
import logging
from datetime import datetime

# --- 1. KONFIGURATSIYA VA LOGGING ---
# Tizimdagi xatoliklarni kuzatish uchun logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Manuscript AI - Akademik Ekspertiza",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. AKADEMIK UI DIZAYN (CSS) ---
st.markdown("""
    <style>
    /* Pergament foni va qadimiy ko'rinish */
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    
    /* Tahlil natijalari kartasi */
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 8px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.7; font-size: 18px;
    }
    
    /* Tugmalar dizayni */
    .stButton>button { 
        background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; 
        color: #fdfaf1 !important; font-weight: bold; border: none; border-radius: 5px;
    }
    
    /* Sidebar dizayni */
    [data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    [data-testid="stSidebar"] .stMarkdown { color: #fdfaf1 !important; }
    </style>
""", unsafe_allow_html=True)

# --- 3. FOYDALANUVCHI FALLBACK (MOCK USER) ---
# Google OAuth ishlamay qolganda NoneType xatosini oldini olish
class MockUser:
    def __init__(self):
        self.email = "mehmon@manuscript.uz"
        self.id = "guest_user"

# --- 4. CORE SERVICES (AI VA KESH) ---

@st.cache_resource
def init_gemini():
    """AI modelini sozlash. 404 xatosini oldini olish uchun nomlar tekshirilgan."""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        # Eng barqaror model nomini tanlaymiz
        return genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        st.error(f"AI Model ulanishida xatolik: {e}")
        return None

ai_model = init_gemini()

# --- 5. RENDERLASH VA XOTIRA OPTIMIZATSIYASI ---

def get_file_hash(content: bytes) -> str:
    """Fayl keshini aniqlash uchun hash yaratish"""
    return hashlib.md5(content).hexdigest()

@st.cache_data(show_spinner=False)
def render_file_page(file_content: bytes, page_idx: int, zoom: float, is_pdf: bool) -> Image.Image:
    """PDF yoki Rasmni optimallashtirilgan holda render qilish"""
    try:
        if is_pdf:
            # PDFium: Data format error oldini olish uchun bytes ishlatiladi
            pdf = pdfium.PdfDocument(file_content)
            page = pdf[page_idx]
            # Zoom: scale parametri orqali boshqariladi
            bitmap = page.render(scale=zoom) 
            img = bitmap.to_pil()
            pdf.close() # Xotirani bo'shatish
            gc.collect()
            return img
        else:
            # Agar fayl rasm bo'lsa
            img = Image.open(io.BytesIO(file_content))
            if zoom != 1.0:
                w, h = img.size
                img = img.resize((int(w * zoom), int(h * zoom)), Image.Resampling.LANCZOS)
            return img
    except Exception as e:
        logger.error(f"Rendering error: {e}")
        return None

def image_to_base64_payload(img: Image.Image):
    """Rasmni Gemini API qabul qiladigan base64 formatiga o'tkazish"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# --- 6. ASYNC AI TAHLIL ---

async def run_ai_analysis(prompt: str, img: Image.Image):
    """Streamlit'da loop conflict bo'lmasligi uchun asinxron chaqiruv"""
    try:
        img_payload = {"mime_type": "image/jpeg", "data": image_to_base64_payload(img)}
        # asyncio.to_thread Streamlit threadlarini bloklamaslikni ta'minlaydi
        response = await asyncio.to_thread(ai_model.generate_content, [prompt, img_payload])
        return response.text
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return f"AI xizmati vaqtincha javob bermadi: {e}"

# --- 7. ASOSIY ILOVA LOGIKASI ---

def main():
    # --- AUTH / LOGIN CHECK ---
    if "user" not in st.session_state:
        # Haqiqiy OAuth bo'lmasa MockUser ishlatiladi
        st.session_state.user = MockUser()

    user = st.session_state.user

    # --- SIDEBAR ---
    with st.sidebar:
        st.markdown(f"### 👤 Foydalanuvchi: \n {user.email}")
        # Kredit tizimi (Simulation)
        if "credits" not in st.session_state:
            st.session_state.credits = 10
        st.metric("💳 Qolgan kredit", st.session_state.credits)
        
        st.divider()
        st.markdown("### ⚙️ Sozlamalar")
        lang = st.selectbox("Asl til:", ["Chig'atoy", "Fors", "Arab", "Eski O'zbek"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Kufiy", "Noma'lum"])

    st.title("📜 Manuscript AI: Tadqiqot Markazi")
    
    # --- FAYL YUKLASH ---
    uploaded_file = st.file_uploader("Faylni yuklang (PDF, JPG, PNG)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        file_id = get_file_hash(file_bytes)
        is_pdf = uploaded_file.type == "application/pdf"
        
        # Session state sozlash
        if file_id not in st.session_state:
            st.session_state[file_id] = {"analysis": {}, "chat": {}}

        # --- SAHIFA VA ZOOM BOSHQARUVI ---
        col_ctrl1, col_ctrl2 = st.columns(2)
        
        total_pages = 1
        if is_pdf:
            try:
                pdf_meta = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf_meta)
                pdf_meta.close()
            except:
                st.error("Fayl formati noto'g'ri (Data format error).")
                return

        with col_ctrl1:
            page_num = st.number_input(f"Sahifa (Jami: {total_pages})", 1, total_pages, 1) - 1
        with col_ctrl2:
            zoom_lvl = st.slider("Tasvir kattaligi (Zoom)", 1.0, 4.0, 2.0, 0.5)

        # --- RENDERLASH (CACHED) ---
        img = render_file_page(file_bytes, page_num, zoom_lvl, is_pdf)

        if img:
            col_img, col_res = st.columns([1, 1.2])
            
            with col_img:
                st.subheader("🖼 Manba Tasviri")
                st.image(img, use_container_width=True)
            
            with col_res:
                tab_anal, tab_chat = st.tabs(["🖋 Akademik Tahlil", "💬 Interaktiv Chat"])
                
                # --- TAHLIL TAB ---
                with tab_anal:
                    if st.button("✨ Tahlilni boshlash"):
                        if st.session_state.credits > 0:
                            with st.spinner("AI matnni o'rganmoqda..."):
                                prompt = f"Siz matnshunos akademiksiz. Ushbu {lang} tilidagi va {style} uslubidagi qo'lyozmani tahlil qiling. 1.Transliteratsiya, 2.Ma'noviy tarjima, 3.Tarixiy izoh."
                                # Asinxron chaqiruv
                                result = asyncio.run(run_ai_analysis(prompt, img))
                                st.session_state[file_id]["analysis"][page_num] = result
                                st.session_state.credits -= 1
                                st.rerun()
                        else:
                            st.error("Kreditlaringiz tugagan!")

                    # Natijani ko'rsatish
                    analysis_result = st.session_state[file_id]["analysis"].get(page_num, "")
                    if analysis_result:
                        st.markdown(f"<div class='result-box'>{analysis_result}</div>", unsafe_allow_html=True)
                
                # --- CHAT TAB ---
                with tab_chat:
                    st.session_state[file_id]["chat"].setdefault(page_num, [])
                    chat_history = st.session_state[file_id]["chat"][page_num]

                    # Chat container
                    chat_container = st.container(height=400)
                    for msg in chat_history:
                        with chat_container.chat_message(msg["role"]):
                            st.write(msg["content"])

                    if user_q := st.chat_input("Ushbu sahifa bo'yicha savol bering..."):
                        chat_history.append({"role": "user", "content": user_q})
                        with chat_container.chat_message("user"):
                            st.write(user_q)

                        with st.spinner("AI o'ylamoqda..."):
                            context = st.session_state[file_id]["analysis"].get(page_num, "Hali tahlil qilinmagan.")
                            chat_prompt = f"Manba tahlili: {context}\nSavol: {user_q}"
                            # Chat uchun rasm qayta render bo'lmaydi, keshdan olinadi
                            ai_ans = asyncio.run(run_ai_analysis(chat_prompt, img))
                            
                            chat_history.append({"role": "assistant", "content": ai_ans})
                            with chat_container.chat_message("assistant"):
                                st.write(ai_ans)
                            st.rerun()

    # --- 8. MEMORY CLEANUP ---
    gc.collect()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Ilova kutilmaganda to'xtadi: {e}")
        st.error(f"Tizimda kutilmagan xatolik: {e}")
