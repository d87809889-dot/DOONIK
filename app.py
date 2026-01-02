import streamlit as st
import google.generativeai as genai
import pypdfium2 as pdfium
import io, gc, asyncio, base64, hashlib, logging
from datetime import datetime
from PIL import Image
from docx import Document
from supabase import create_client, Client

# --- 1. LOGGING SOZLAMALARI ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 2. TIZIM VA SEO SOZLAMALARI ---
st.set_page_config(
    page_title="Manuscript AI - Pro Master 2026",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 3. HELPER FUNCTIONS (DRY PRINCIPLE) ---

def get_file_hash(content: bytes) -> str:
    """Fayl uchun yagona identifikator yaratish (Caching uchun)"""
    return hashlib.md5(content).hexdigest()

@st.cache_data(show_spinner=False)
def render_page_cached(file_content: bytes, page_idx: int, scale: float = 2.5) -> Image.Image:
    """PDF sahifasini render qilish va keshga saqlash (Memory Optimized)"""
    try:
        pdf = pdfium.PdfDocument(file_content)
        page = pdf[page_idx]
        bitmap = page.render(scale=scale)
        img = bitmap.to_pil()
        pdf.close()
        return img
    except Exception as e:
        logger.error(f"Render error on page {page_idx}: {e}")
        st.error("Sahifani o'qishda xatolik yuz berdi.")
        return None

def image_to_base64_payload(img: Image.Image):
    """Rasmni Gemini API formatiga o'tkazish"""
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

# --- 4. DATABASE & AUTH (SUPABASE) ---

@st.cache_resource
def get_db_client() -> Client:
    """Supabase ulanishini keshlab saqlash"""
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        st.error("Ma'lumotlar bazasiga ulanib bo'lmadi.")
        st.stop()

db = get_db_client()

def fetch_user_credits(user_id: str):
    """Kreditlarni real vaqtda olish (Error handling bilan)"""
    try:
        res = db.table("profiles").select("credits, role").eq("id", user_id).single().execute()
        return res.data if res.data else {"credits": 0, "role": "free"}
    except Exception as e:
        logger.error(f"Credit fetch error: {e}")
        return {"credits": 0, "role": "free"}

# --- 5. AI ENGINE (ASYNC INTEGRATION) ---

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
ai_model = genai.GenerativeModel('gemini-1.5-flash')

async def analyze_manuscript_async(prompt: str, images: list):
    """Batch asinxron tahlil (UI bloklanmasligi uchun)"""
    contents = [prompt] + [image_to_base64_payload(img) for img in images]
    try:
        response = await ai_model.generate_content_async(contents)
        return response.text
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        return f"AI Tahlilida xatolik yuz berdi: {str(e)}"

# --- 6. SESSION STATE INITIALIZATION ---

def init_state():
    """State'larni defaultdict uslubida boshqarish"""
    if "auth" not in st.session_state: st.session_state.auth = False
    if "user" not in st.session_state: st.session_state.user = None
    st.session_state.setdefault("ai_results", {})
    st.session_state.setdefault("chats", {})
    st.session_state.setdefault("current_page_idx", 0)

init_state()

# --- 7. UI: CSS & ANTIK DIZAYN ---

st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; }
    .stApp { font-family: 'Times New Roman', serif; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        max-height: 500px; overflow-y: auto; color: #1a1a1a;
    }
    .chat-bubble-user { background-color: #e2e8f0; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border: 1px solid #d4af37; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# --- 8. AUTH FLOW ---

if not st.session_state.auth:
    _, col_mid, _ = st.columns([1, 1.5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align:center;'>🏛 Manuscript AI SaaS</h2>", unsafe_allow_html=True)
        tab_login, tab_reg = st.tabs(["Kirish", "Ro'yxatdan o'tish"])
        
        with tab_login:
            email = st.text_input("Email", key="l_email")
            pwd = st.text_input("Parol", type="password", key="l_pwd")
            if st.button("Kirish"):
                try:
                    res = db.auth.sign_in_with_password({"email": email, "password": pwd})
                    st.session_state.user = res.user
                    st.session_state.auth = True
                    st.rerun()
                except Exception as e:
                    st.error("Email yoki parol noto'g'ri")
        
        with tab_reg:
            re_email = st.text_input("Email", key="r_email")
            re_pwd = st.text_input("Parol", type="password", key="r_pwd")
            if st.button("Hisob yaratish"):
                try:
                    db.auth.sign_up({"email": re_email, "password": re_pwd})
                    st.success("Pochtangizga tasdiqlash linki yuborildi!")
                except Exception as e:
                    st.error(f"Xatolik: {e}")
    st.stop()

# --- 9. MAIN APP CONTENT ---

user_profile = fetch_user_credits(st.session_state.user.id)

# SIDEBAR
with st.sidebar:
    st.markdown(f"👤 **{st.session_state.user.email}**")
    st.metric("💳 Qolgan limit", f"{user_profile['credits']} sahifa")
    st.divider()
    lang = st.selectbox("Asl til:", ["Chig'atoy", "Forscha", "Arabcha", "Usmonli Turk"])
    era = st.selectbox("Xattotlik:", ["Nasta'liq", "Suls", "Riq'a", "Devoniy", "Noma'lum"])
    if st.button("🚪 Chiqish"):
        db.auth.sign_out()
        st.session_state.auth = False
        st.rerun()

st.title("📜 Akademik Qo'lyozmalar Ekspertiza Markazi")
uploaded_file = st.file_uploader("Faylni yuklang (PDF/Rasm)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

if uploaded_file:
    file_content = uploaded_file.getvalue()
    file_id = get_file_hash(file_content)
    
    # 📑 SAHIFA TANLASH
    if uploaded_file.type == "application/pdf":
        doc = pdfium.PdfDocument(file_content)
        total_pages = len(doc)
        st.info(f"Hujjatda {total_pages} ta sahifa aniqlandi.")
        selected_pages = st.multiselect("Tahlil uchun sahifalarni tanlang:", range(1, total_pages + 1), default=[1])
        doc.close()
    else:
        selected_pages = [1]

    # ⚡️ BATCH ANALYSIS (ASYNC)
    if st.button("✨ Akademik Tahlilni Boshlash"):
        if user_profile['credits'] < len(selected_pages):
            st.warning("Limit yetarli emas! Iltimos, balansni to'ldiring.")
        else:
            with st.status("AI Paleografik ekspertiza o'tkazmoqda...", expanded=True) as status:
                try:
                    # Sahifalarni lazy load qilib yig'ish
                    imgs = [render_page_cached(file_content, p-1) for p in selected_pages]
                    prompt = f"Siz matnshunos akademiksiz. {lang} va {era} uslubidagi qo'lyozmani tahlil qiling: 1.Paleografiya 2.Transliteratsiya 3.Tarjima 4.Izoh."
                    
                    # Async taskni bloklanmagan holda bajarish
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result_text = loop.run_until_complete(analyze_manuscript_async(prompt, imgs))
                    
                    # Natijani saqlash
                    st.session_state.ai_results[file_id] = result_text
                    
                    # Kreditni yangilash
                    new_credits = max(0, user_profile['credits'] - len(selected_pages))
                    db.table("profiles").update({"credits": new_credits}).eq("id", st.session_state.user.id).execute()
                    
                    status.update(label="✅ Tahlil yakunlandi!", state="complete")
                    st.rerun()
                except Exception as e:
                    logger.error(f"Analysis process failed: {e}")
                    st.error("Tahlil jarayonida kutilmagan xatolik.")

    # --- 10. NATIJALARNI KO'RSATISH VA CHAT ---
    if file_id in st.session_state.ai_results:
        st.divider()
        res_text = st.session_state.ai_results[file_id]
        
        col_img, col_res = st.columns([1, 1.1])
        
        with col_img:
            st.subheader("🖼 Asl Hujjat")
            view_page = st.selectbox("Sahifani ko'rish:", selected_pages, key="page_viewer")
            # Keshdan olingan rasm
            display_img = render_page_cached(file_content, view_page-1, scale=3.0)
            st.image(display_img, use_container_width=True)
            
            # Word Eksport
            doc_buffer = io.BytesIO()
            report = Document()
            report.add_heading('Academic Analysis Report', 0)
            report.add_paragraph(res_text)
            report.save(doc_buffer)
            st.download_button("📥 Hisobotni yuklab olish", doc_buffer.getvalue(), f"report_{file_id}.docx")

        with col_res:
            tab_anal, tab_chat = st.tabs(["🖋 Tahlil Natijasi", "💬 Ilmiy Muloqot"])
            
            with tab_anal:
                # Tahrirlash oynasi
                edited_res = st.text_area("AI Xulosasi (Tahrir qilish mumkin):", value=res_text, height=450)
                st.session_state.ai_results[file_id] = edited_res

            with tab_chat:
                chat_id = f"{file_id}_{view_page}"
                st.session_state.chats.setdefault(chat_id, [])
                
                chat_placeholder = st.container(height=400)
                
                # Chatni xotiradan yuklash
                for chat in st.session_state.chats[chat_id]:
                    with chat_placeholder.chat_message(chat["role"]):
                        st.markdown(chat["content"])

                # Chat input (Rerun'siz ishlashi uchun)
                if user_q := st.chat_input("Savol bering..."):
                    st.session_state.chats[chat_id].append({"role": "user", "content": user_q})
                    with chat_placeholder.chat_message("user"):
                        st.markdown(user_q)
                    
                    with st.spinner("AI o'ylanmoqda..."):
                        # Faqat matnli kontekst orqali so'rov yuborish (Token tejash)
                        chat_prompt = f"Matn: {edited_res}\n\nFoydalanuvchi savoli: {user_q}"
                        chat_response = ai_model.generate_content(chat_prompt)
                        ai_ans = chat_response.text
                        
                        st.session_state.chats[chat_id].append({"role": "assistant", "content": ai_ans})
                        with chat_placeholder.chat_message("assistant"):
                            st.markdown(ai_ans)

# 🧹 Xotirani tozalash
gc.collect()

