import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
from PIL import Image
import io, gc, asyncio, base64, hashlib, time, uuid
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Pro Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3, h4 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.6;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-size: 16px !important; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; border: none; padding: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CORE SERVICES (SUPABASE & AI) ---
@st.cache_resource
def get_db() -> Client:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Ma'lumotlar bazasiga ulanishda xatolik: {e}")
        st.stop()

db = get_db()

def init_gemini():
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        return genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        st.error(f"AI konfiguratsiya xatosi: {e}")
        st.stop()

model = init_gemini()

# --- 4. YORDAMCHI FUNKSIYALAR (MEMORY & RENDERING) ---

def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

def image_to_base64(img: Image.Image) -> str:
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float) -> Image.Image:
    try:
        pdf = pdfium.PdfDocument(file_content)
        page = pdf[page_idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        pdf.close()
        gc.collect()
        return img
    except Exception as e:
        st.error(f"Sahifani render qilishda xatolik: {e}")
        return None

# --- 5. REAL-TIME KREDIT LOGIKASI ---

def fetch_live_credits(user_id: str):
    try:
        res = db.table("profiles").select("credits").eq("id", user_id).single().execute()
        return res.data["credits"] if res.data else 0
    except Exception:
        return 0

def use_credit_atomic(user_id: str):
    current = fetch_live_credits(user_id)
    if current > 0:
        db.table("profiles").update({"credits": current - 1}).eq("id", user_id).execute()
        return True
    return False

# --- 6. NON-BLOCKING ASYNC AI LOGIC ---

async def call_ai_async(prompt: str, img: Image.Image):
    try:
        img_payload = {"mime_type": "image/jpeg", "data": image_to_base64(img)}
        response = await asyncio.to_thread(model.generate_content, [prompt, img_payload])
        return response.text
    except Exception as e:
        return f"AI Tahlil xatosi: {str(e)}"

# --- 7. WORD EXPORT ---

def create_word_report(analysis_text, chat_history):
    doc = Document()
    doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
    doc.add_heading('Ekspertiza Xulosasi', level=1)
    doc.add_paragraph(analysis_text)
    
    if chat_history:
        doc.add_heading('Ilmiy Muloqot Tarixi', level=1)
        for msg in chat_history:
            p = doc.add_paragraph()
            p.add_run(f"{msg['role'].upper()}: ").bold = True
            p.add_run(msg['content'])
            
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 8. ASOSIY ILOVA LOGIKASI ---

def main():
    # 🔐 PAROL BILAN KIRISH TIZIMI
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        _, col_mid, _ = st.columns([1, 1.5, 1])
        with col_mid:
            st.markdown("<br><br><h2 style='text-align:center;'>🏛 Manuscript AI Kirish</h2>", unsafe_allow_html=True)
            st.info("Ilovadan foydalanish uchun maxfiy parolni kiriting.")
            
            password = st.text_input("Parol:", type="password")
            if st.button("Kirish", use_container_width=True):
                if password == "tarix-2026":
                    st.session_state.authenticated = True
                    # Sizning Supabase UID va Emailingiz
                    class MockUser:
                        id = "72b7208c-6da2-449f-a8dd-a61c7a25a42e"
                        email = "d87809889@gmail.com"
                    st.session_state.user = MockUser()
                    st.rerun()
                else:
                    st.error("Parol noto'g'ri!")
        return

    # 📊 SESSION STATE INIT
    user_id = st.session_state.user.id
    if "ai_store" not in st.session_state: st.session_state.ai_store = {}
    if "chat_store" not in st.session_state: st.session_state.chat_store = {}

    # 🛠 SIDEBAR
    live_credits = fetch_live_credits(user_id)
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.user.email}**")
        st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
        st.divider()
        lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Usmonli Turk"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Kufiy", "Riq'a", "Noma'lum"])
        if st.button("🚪 Chiqish"):
            st.session_state.authenticated = False
            st.session_state.clear()
            st.rerun()

    st.title("📜 Akademik Qo'lyozmalar Ekspertiza Markazi")
    file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if file:
        file_bytes = file.getvalue()
        file_id = get_file_hash(file_bytes)
        
        if file.type == "application/pdf":
            try:
                pdf_doc = pdfium.PdfDocument(file_bytes)
                total_pages = len(pdf_doc)
                pdf_doc.close()
                selected_page = st.number_input(f"Sahifani tanlang (1-{total_pages}):", 1, total_pages) - 1
            except Exception as e:
                st.error(f"PDF o'qishda xato: {e}")
                return
        else:
            selected_page = 0
            total_pages = 1

        state_key = f"{file_id}_{selected_page}"
        st.session_state.chat_store.setdefault(state_key, [])

        col_img, col_info = st.columns([1, 1.2])
        img_ui = render_page_optimized(file_bytes, selected_page, scale=1.5)

        if img_ui:
            with col_img:
                st.subheader("🖼 Manba Tasviri")
                zoom = st.slider("Kattalashtirish:", 1.0, 3.0, 1.2)
                st.image(img_ui, width=int(zoom * 550))
                
                if st.session_state.ai_store.get(state_key):
                    unique_name = f"Report_{state_key}_{datetime.now().strftime('%H%M%S')}.docx"
                    word_data = create_word_report(st.session_state.ai_store[state_key], st.session_state.chat_store[state_key])
                    st.download_button("📥 Hisobotni Wordda yuklash", word_data, unique_name, use_container_width=True)

            with col_info:
                tab_anal, tab_chat = st.tabs(["🖋 Akademik Tahlil", "💬 Ilmiy Muloqot"])
                
                with tab_anal:
                    if st.button("✨ Tahlilni boshlash"):
                        if fetch_live_credits(user_id) > 0:
                            with st.spinner("AI tahlil qilmoqda..."):
                                img_ai = render_page_optimized(file_bytes, selected_page, scale=3.0)
                                prompt = f"Siz matnshunos akademiksiz. {lang} va {style} uslubidagi manbani tahlil qiling: 1.Transliteratsiya 2.Tarjima 3.Izoh."
                                result = asyncio.run(call_ai_async(prompt, img_ai))
                                st.session_state.ai_store[state_key] = result
                                use_credit_atomic(user_id)
                                st.rerun()
                        else:
                            st.error("Kreditlar tugagan. Iltimos, balansni to'ldiring.")

                    if st.session_state.ai_store.get(state_key):
                        st.markdown(f"<div class='result-box'>{st.session_state.ai_store[state_key]}</div>", unsafe_allow_html=True)
                        edited = st.text_area("AI natijasini tahrirlash:", value=st.session_state.ai_store[state_key], height=300, key=f"edit_{state_key}")
                        st.session_state.ai_store[state_key] = edited

                with tab_chat:
                    chat_container = st.container(height=450)
                    for msg in st.session_state.chat_store[state_key]:
                        chat_container.chat_message(msg["role"]).write(msg["content"])

                    if user_q := st.chat_input("Savol bering...", key=f"in_{state_key}"):
                        if fetch_live_credits(user_id) > 0:
                            st.session_state.chat_store[state_key].append({"role": "user", "content": user_q})
                            chat_container.chat_message("user").write(user_q)
                            
                            with st.spinner("AI o'ylanmoqda..."):
                                context = st.session_state.ai_store.get(state_key, "")
                                chat_prompt = f"Matn tahlili: {context}\nSavol: {user_q}"
                                img_chat = render_page_optimized(file_bytes, selected_page, scale=1.5)
                                response = asyncio.run(call_ai_async(chat_prompt, img_chat))
                                
                                st.session_state.chat_store[state_key].append({"role": "assistant", "content": response})
                                chat_container.chat_message("assistant").write(response)
                                use_credit_atomic(user_id)
                                st.rerun()
                        else:
                            st.error("Kredit yetarli emas.")

    gc.collect()

if __name__ == "__main__":
    main()
