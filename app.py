import streamlit as st
import google.generativeai as genai
from PIL import Image
import pypdfium2 as pdfium
import io, gc, asyncio, hashlib, time
from datetime import datetime
from docx import Document
from supabase import create_client, Client

# --- 1. TIZIM VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Pro Academic 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PROFESSIONAL ANTIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden !important;}
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.6;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000000 !important; border: 2px solid #c5a059 !important; font-size: 16px; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; border: none; padding: 12px; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CORE SERVICES (SUPABASE & AI) ---
@st.cache_resource
def get_db_client() -> Client:
    """Supabase ulanishini keshlab saqlash"""
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

db = get_db_client()

@st.cache_resource
def init_gemini():
    """Gemini AI modelini barqaror sozlash"""
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-1.5-flash')

ai_model = init_gemini()

# --- 4. YORDAMCHI FUNKSIYALAR (MEMORY & CACHE) ---

def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

@st.cache_data(show_spinner=False)
def render_page_cached(file_content: bytes, page_idx: int, scale: float = 2.5) -> Image.Image:
    """Memory-safe PDF render: Keshlanadi va PDF yopiladi"""
    try:
        pdf = pdfium.PdfDocument(file_content)
        page = pdf[page_idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        pdf.close() # Xotirani bo'shatish
        gc.collect()
        return img
    except Exception as e:
        st.error(f"PDF Render xatosi: {e}")
        return None

def image_to_bytes(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return buffered.getvalue()

# --- 5. REAL-TIME KREDIT TIZIMI ---

def fetch_current_credits(user_id: str):
    """Snapshot emas, realtime kreditni bazadan olish"""
    res = db.table("profiles").select("credits").eq("id", user_id).single().execute()
    return res.data["credits"] if res.data else 0

def use_credit_realtime(user_id: str):
    """Kreditni bazada kamaytirish"""
    current = fetch_current_credits(user_id)
    if current > 0:
        db.table("profiles").update({"credits": current - 1}).eq("id", user_id).execute()
        return True
    return False

# --- 6. NON-BLOCKING ASYNC AI LOGIC ---

async def call_ai_async(prompt: str, img: Image.Image):
    """Streamlit threadni bloklamagan holda AI tahlil qilish"""
    img_bytes = image_to_bytes(img)
    payload = {"mime_type": "image/jpeg", "data": img_bytes}
    # Gemini SDK sync chaqiruvni asinxron threadga o'tkazamiz
    response = await asyncio.to_thread(ai_model.generate_content, [prompt, payload])
    return response.text

# --- 7. WORD EXPORT ---

def create_full_report(analysis_text, chat_history):
    """Tahlil va barcha chatni unique Word faylga jamlash"""
    doc = Document()
    doc.add_heading('Manuscript AI: Akademik Ekspertiza Hisoboti', 0)
    doc.add_heading('1. Ekspertiza Xulosasi', level=1)
    doc.add_paragraph(analysis_text)
    
    if chat_history:
        doc.add_heading('2. Tadqiqot Muloqotlari Tarixi', level=1)
        for msg in chat_history:
            p = doc.add_paragraph()
            p.add_run(f"{msg['role'].upper()}: ").bold = True
            p.add_run(msg['content'])
            
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 8. ASOSIY ILOVA ---

def main():
    # --- AUTH FLOW ---
    if "user" not in st.session_state: st.session_state.user = None
    try:
        user_res = db.auth.get_user()
        st.session_state.user = user_res.user if user_res else None
    except: pass

    if not st.session_state.user:
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.markdown("<br><br><h2>🏛 Manuscript AI Login</h2>", unsafe_allow_html=True)
            if st.button("🌐 Google orqali kirish", use_container_width=True):
                res = db.auth.sign_in_with_oauth({"provider": "google", "options": {"redirect_to": st.secrets["REDIRECT_URL"]}})
                st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
        return

    # --- SESSION STATE INIT ---
    user_id = st.session_state.user.id
    if "ai_results" not in st.session_state: st.session_state.ai_results = {}
    if "chat_history" not in st.session_state: st.session_state.chat_history = {}

    # --- SIDEBAR ---
    credits = fetch_current_credits(user_id)
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.user.email}**")
        st.metric("💳 Qolgan kredit", f"{credits} sahifa")
        st.divider()
        lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Usmonli Turk"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Kufiy", "Noma'lum"])
        if st.button("🚪 Chiqish"):
            db.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    st.title("📜 Akademik Qo'lyozmalar Ekspertiza Markazi")
    file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'])

    if file:
        file_bytes = file.getvalue()
        file_hash = get_file_hash(file_bytes)
        
        # Sahifa navigatsiyasi
        if file.type == "application/pdf":
            try:
                with pdfium.PdfDocument(file_bytes) as pdf:
                    total_pages = len(pdf)
                selected_page = st.number_input(f"Sahifani tanlang (1-{total_pages}):", 1, total_pages) - 1
            except: st.error("PDF o'qishda xato."); return
        else:
            selected_page = 0
            total_pages = 1

        state_key = f"{file_hash}_{selected_page}"
        st.session_state.chat_history.setdefault(state_key, [])

        col_img, col_info = st.columns([1, 1.2])
        
        # Lazy Loading Image
        img = render_page_cached(file_bytes, selected_page)

        if img:
            with col_img:
                st.subheader("🖼 Manba Tasviri")
                zoom = st.slider("Kattalashtirish:", 1.0, 3.0, 1.5)
                st.image(img, width=int(zoom * 500))
                
                # WORD EXPORT
                if st.session_state.ai_results.get(state_key):
                    word_data = create_full_report(st.session_state.ai_results[state_key], st.session_state.chat_history[state_key])
                    st.download_button(
                        "📥 Hisobotni Wordda yuklash", 
                        word_data, 
                        f"Report_{state_key}_{int(time.time())}.docx",
                        use_container_width=True
                    )

            with col_info:
                tab_anal, tab_chat = st.tabs(["🖋 Akademik Tahlil", "💬 Ilmiy Muloqot"])
                
                with tab_anal:
                    if st.button("✨ Tahlilni boshlash"):
                        if fetch_current_credits(user_id) > 0:
                            with st.spinner("AI tahlil qilmoqda..."):
                                prompt = f"Siz matnshunos akademiksiz. {lang} va {style} uslubidagi manbani tahlil qiling: 1.Transliteratsiya 2.Tarjima 3.Izoh."
                                # Non-blocking call
                                result = asyncio.run(call_ai_async(prompt, img))
                                st.session_state.ai_results[state_key] = result
                                use_credit_realtime(user_id)
                                st.rerun()
                        else: st.error("Kreditlar tugagan.")

                    if st.session_state.ai_results.get(state_key):
                        st.markdown(f"<div class='result-box'>{st.session_state.ai_results[state_key]}</div>", unsafe_allow_html=True)

                with tab_chat:
                    chat_container = st.container(height=450)
                    for msg in st.session_state.chat_history[state_key]:
                        chat_container.chat_message(msg["role"]).write(msg["content"])

                    if user_q := st.chat_input("Savol bering..."):
                        if fetch_current_credits(user_id) > 0:
                            st.session_state.chat_history[state_key].append({"role": "user", "content": user_q})
                            # Rerun qilmasdan UI ga chiqarish
                            chat_container.chat_message("user").write(user_q)
                            
                            with st.spinner("AI o'ylanmoqda..."):
                                context = st.session_state.ai_results.get(state_key, "")
                                chat_prompt = f"Matn tahlili: {context}\nSavol: {user_q}"
                                response = asyncio.run(call_ai_async(chat_prompt, img))
                                
                                st.session_state.chat_history[state_key].append({"role": "assistant", "content": response})
                                chat_container.chat_message("assistant").write(response)
                                use_credit_realtime(user_id)
                                st.rerun() # Kreditni yangilash uchun oxirida rerun
                        else: st.error("Kredit yetarli emas.")

    gc.collect()

if __name__ == "__main__":
    main()
