import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import pypdfium2 as pdfium
from PIL import Image
import io
import gc
import asyncio
import base64
import hashlib
import logging
from datetime import datetime
from docx import Document

# --- 1. KONFIGURATSIYA ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Manuscript AI - Enterprise Pro",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ANTIK AKADEMIK DIZAYN (CSS) ---
st.markdown("""
    <style>
    .main { background-color: #f4ecd8 !important; color: #1a1a1a !important; font-family: 'Times New Roman', serif; }
    h1, h2, h3 { color: #0c1421 !important; text-align: center; border-bottom: 2px solid #c5a059; padding-bottom: 10px; }
    .result-box { 
        background-color: #ffffff; padding: 25px; border-radius: 12px; 
        border-left: 10px solid #c5a059; box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        color: #1a1a1a; line-height: 1.7; font-size: 18px;
    }
    .stTextArea textarea { background-color: #fdfaf1 !important; color: #000 !important; border: 1px solid #c5a059 !important; font-size: 16px; }
    .chat-bubble-user { background-color: #e2e8f0; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border-left: 5px solid #1e3a8a; }
    .chat-bubble-ai { background-color: #ffffff; color: black; padding: 12px; border-radius: 10px; margin: 5px 0; border: 1px solid #d4af37; }
    .stButton>button { background: linear-gradient(135deg, #0c1421 0%, #1e3a8a 100%) !important; color: #c5a059 !important; font-weight: bold; border: none; }
    [data-testid="stSidebar"] { background-color: #0c1421 !important; border-right: 2px solid #c5a059; }
    </style>
""", unsafe_allow_html=True)

# --- 3. CORE SERVICES (SUPABASE & AI) ---

@st.cache_resource
def get_db() -> Client:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error("Ma'lumotlar bazasiga ulanishda xatolik!")
        st.stop()

db = get_db()

@st.cache_resource
def init_gemini():
    """404 XATOSINI YO'QOTUVCHI AVTOMATIK LOADER"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        
        # 1. Google serveridan ruxsat etilgan modellarni so'raymiz
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2. Ishlaydigan nomlarni tartib bilan tekshiramiz
        # Sizdagi 404 xatosini yengish uchun 'gemini-1.5-flash' (latest-siz) birinchi o'rinda
        targets = [
            'models/gemini-1.5-flash',
            'models/gemini-1.5-flash-latest',
            'models/gemini-1.5-pro-latest',
            'models/gemini-pro-vision'
        ]
        
        chosen = None
        for target in targets:
            if target in available_models:
                chosen = target
                break
        
        if not chosen:
            # Agar birortasi ham mos kelmasa, birinchi mavjud modelni olamiz
            chosen = available_models[0] if available_models else 'gemini-1.5-flash'
            
        logger.info(f"Muvaffaqiyatli tanlangan model: {chosen}")
        return genai.GenerativeModel(model_name=chosen)
    except Exception as e:
        st.error(f"AI Model sozlashda xatolik: {e}")
        return None

ai_model = init_gemini()

# --- 4. YORDAMCHI FUNKSIYALAR ---

def get_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()

@st.cache_data(show_spinner=False)
def render_page_optimized(file_content: bytes, page_idx: int, scale: float, is_pdf: bool) -> Image.Image:
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            page = pdf[page_idx]
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            pdf.close()
            gc.collect()
            return img
        else:
            return Image.open(io.BytesIO(file_content))
    except Exception as e:
        logger.error(f"Render xatosi: {e}")
        return None

def img_to_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

# --- 5. KREDIT TIZIMI ---

def fetch_live_credits(user_id: str):
    try:
        res = db.table("profiles").select("credits").eq("id", user_id).single().execute()
        return res.data["credits"] if res.data else 0
    except:
        return 0

def use_credit_atomic(user_id: str):
    current = fetch_live_credits(user_id)
    if current > 0:
        db.table("profiles").update({"credits": current - 1}).eq("id", user_id).execute()
        return True
    return False

# --- 6. ASYNC AI LOGIC ---

async def call_ai_async(prompt: str, img: Image.Image):
    """Asinxron AI so'rovi (Non-blocking)"""
    try:
        payload = img_to_payload(img)
        response = await asyncio.to_thread(ai_model.generate_content, [prompt, payload])
        return response.text
    except Exception as e:
        return f"🚨 AI Xatosi: {str(e)}"

# --- 7. EXPORT ---

def create_report(analysis, chat_history):
    doc = Document()
    doc.add_heading('Manuscript AI: Akademik Hisobot', 0)
    doc.add_paragraph(analysis)
    if chat_history:
        doc.add_heading('Suhbat Tarixi', 1)
        for msg in chat_history:
            doc.add_paragraph(f"{msg['role'].upper()}: {msg['content']}")
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

# --- 8. ASOSIY ILOVA ---

def main():
    # --- AUTH FLOW ---
    if "user" not in st.session_state:
        st.session_state.user = None

    try:
        user_res = db.auth.get_user()
        st.session_state.user = user_res.user if user_res else None
    except: pass

    if not st.session_state.user:
        _, col_mid, _ = st.columns([1, 1.5, 1])
        with col_mid:
            st.markdown("<br><br><h2>🏛 Manuscript AI Login</h2>", unsafe_allow_html=True)
            if st.button("🌐 Google orqali kirish", use_container_width=True):
                res = db.auth.sign_in_with_oauth({
                    "provider": "google", 
                    "options": {"redirect_to": st.secrets["REDIRECT_URL"]}
                })
                st.markdown(f'<meta http-equiv="refresh" content="0;url={res.url}">', unsafe_allow_html=True)
        return

    # --- STATE INIT ---
    user_id = st.session_state.user.id
    st.session_state.setdefault("ai_results", {})
    st.session_state.setdefault("chats", {})

    # --- SIDEBAR ---
    live_credits = fetch_live_credits(user_id)
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.user.email}**")
        st.metric("💳 Qolgan kredit", f"{live_credits} sahifa")
        st.divider()
        lang = st.selectbox("Asl matn tili:", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
        style = st.selectbox("Xat uslubi:", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
        if st.button("🚪 Chiqish"):
            db.auth.sign_out()
            st.session_state.clear()
            st.rerun()

    st.title("📜 Qo'lyozmalar Ekspertiza Markazi")
    uploaded_file = st.file_uploader("Faylni yuklang (PDF, PNG, JPG, JPEG)", type=['pdf', 'png', 'jpg', 'jpeg'], label_visibility="collapsed")

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        file_id = get_file_hash(file_bytes)
        is_pdf = uploaded_file.type == "application/pdf"
        
        if is_pdf:
            try:
                pdf_m = pdfium.PdfDocument(file_bytes)
                t_pages = len(pdf_m)
                pdf_m.close()
                col_p, col_z = st.columns(2)
                with col_p:
                    p_idx = st.number_input(f"Sahifa (1-{t_pages}):", 1, t_pages) - 1
                with col_z:
                    z_val = st.slider("Zoom:", 1.0, 4.0, 2.5)
            except: st.error("Fayl o'qib bo'lmadi."); return
        else:
            p_idx = 0
            z_val = st.slider("Zoom:", 1.0, 3.0, 1.5)

        state_key = f"{file_id}_{p_idx}"
        st.session_state.chats.setdefault(state_key, [])

        col_img, col_info = st.columns([1, 1.2])
        img = render_page_optimized(file_bytes, p_idx, z_val, is_pdf)

        if img:
            with col_img:
                st.image(img, use_container_width=True, caption=f"Varaq: {p_idx + 1}")
                if st.session_state.ai_results.get(state_key):
                    w_data = create_report(st.session_state.ai_results[state_key], st.session_state.chats[state_key])
                    st.download_button("📥 Wordda yuklash", w_data, f"report_{state_key}.docx", use_container_width=True)

            with col_info:
                t_anal, t_chat = st.tabs(["🖋 Tahlil", "💬 Chat"])
                
                with t_anal:
                    if st.button("✨ Tahlilni boshlash"):
                        if live_credits > 0:
                            with st.status("AI paleografik ekspertiza o'tkazmoqda...") as status:
                                prompt = f"Siz dunyo darajasidagi matnshunos akademiksiz. {lang} va {style} uslubidagi ushbu manbani tahlil qiling: 1.Transliteratsiya (Lotin) 2.Tarjima (O'zbek) 3.Izoh."
                                res = asyncio.run(call_ai_async(prompt, img))
                                if "🚨" not in res:
                                    st.session_state.ai_results[state_key] = res
                                    use_credit_atomic(user_id)
                                    status.update(label="✅ Tayyor!", state="complete")
                                    st.rerun()
                                else:
                                    st.error(res)
                        else: st.warning("Kredit yetarli emas.")

                    if st.session_state.ai_results.get(state_key):
                        res_val = st.text_area("Xulosani tahrirlash:", value=st.session_state.ai_results[state_key], height=450, key=f"ar_{state_key}")
                        st.session_state.ai_results[state_key] = res_val

                with t_chat:
                    chat_history = st.session_state.chats[state_key]
                    c_container = st.container(height=400)
                    for m in chat_history:
                        c_container.chat_message(m["role"]).write(m["content"])

                    if u_q := st.chat_input("Savol bering...", key=f"q_{state_key}"):
                        if fetch_live_credits(user_id) > 0:
                            chat_history.append({"role": "user", "content": u_q})
                            with st.spinner("AI o'ylanmoqda..."):
                                ctx = st.session_state.ai_results.get(state_key, "Tahlil yo'q.")
                                c_prompt = f"Kontekst: {ctx}\nSavol: {u_q}"
                                c_img = render_page_optimized(file_bytes, p_idx, 1.5, is_pdf)
                                ans = asyncio.run(call_ai_async(c_prompt, c_img))
                                chat_history.append({"role": "assistant", "content": ans})
                                use_credit_atomic(user_id)
                                st.rerun()
                        else: st.error("Kredit yetarli emas.")

    gc.collect()

if __name__ == "__main__":
    main()

