# File: app_ultra_pro.py

import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import pypdfium2 as pdfium
import io, gc, base64, json
from datetime import datetime
from docx import Document
from supabase import create_client
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# ==========================================
# 1. TIZIM VA SEO SOZLAMALARI
# ==========================================
st.set_page_config(
    page_title="Manuscript AI - Global Academic Master",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="auto"
)

# ==========================================
# SESSION STATE INITIALIZATION
# ==========================================
if "auth" not in st.session_state:
    st.session_state.auth = False
if "u_email" not in st.session_state:
    st.session_state.u_email = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "theme" not in st.session_state:
    st.session_state.theme = "Antik Oltin"
if "history" not in st.session_state:
    st.session_state.history = []
if "imgs" not in st.session_state:
    st.session_state.imgs = []
if "results" not in st.session_state:
    st.session_state.results = {}
if "chats" not in st.session_state:
    st.session_state.chats = {}
if "compare_mode" not in st.session_state:
    st.session_state.compare_mode = False
if "current_page_index" not in st.session_state:
    st.session_state.current_page_index = 0
if "show_landing" not in st.session_state:
    st.session_state.show_landing = True

# ==========================================
# THEME DEFINITIONS
# ==========================================
THEMES = {
    "Antik Oltin": {
        "primary": "#0c1421",
        "accent": "#c5a059",
        "accent2": "#d4af37",
        "bg_light": "#f4ecd8",
        "bg_light2": "#fdfaf1",
        "bg_dark": "#1a1a1a",
        "bg_dark2": "#2d2d2d"
    },
    "Moviy Akademik": {
        "primary": "#1e3a8a",
        "accent": "#3b82f6",
        "accent2": "#60a5fa",
        "bg_light": "#eff6ff",
        "bg_light2": "#dbeafe",
        "bg_dark": "#1e293b",
        "bg_dark2": "#334155"
    },
    "Yashil Tabiat": {
        "primary": "#065f46",
        "accent": "#10b981",
        "accent2": "#34d399",
        "bg_light": "#ecfdf5",
        "bg_light2": "#d1fae5",
        "bg_dark": "#1a2e1a",
        "bg_dark2": "#2d4a2d"
    }
}

theme = THEMES[st.session_state.theme]
dark = st.session_state.dark_mode

# Dynamic color variables
bg_main = theme["bg_dark"] if dark else theme["bg_light"]
bg_secondary = theme["bg_dark2"] if dark else theme["bg_light2"]
text_primary = "#e0e0e0" if dark else "#1a1a1a"
text_secondary = "#a0a0a0" if dark else "#5d4037"
card_bg = theme["bg_dark2"] if dark else "#ffffff"

# ==========================================
# DYNAMIC CSS - ULTRA PROFESSIONAL
# ==========================================
st.markdown(f"""
    <style>
    /* === GOOGLE FONTS === */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    
    /* === CSS VARIABLES === */
    :root {{
        --primary: {theme['primary']};
        --accent: {theme['accent']};
        --accent2: {theme['accent2']};
        --bg-main: {bg_main};
        --bg-secondary: {bg_secondary};
        --text-primary: {text_primary};
        --text-secondary: {text_secondary};
        --card-bg: {card_bg};
        --glass-bg: rgba(255,255,255,0.05);
        --glass-border: rgba(255,255,255,0.1);
        --shadow-sm: 0 2px 8px rgba(0,0,0,0.08);
        --shadow-md: 0 8px 24px rgba(0,0,0,0.12);
        --shadow-lg: 0 16px 48px rgba(0,0,0,0.16);
        --shadow-glow: 0 0 40px rgba(197,160,89,0.3);
        --transition-fast: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
        --transition-normal: 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        --transition-slow: 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        --blur-amount: 20px;
    }}
    
    /* === SYSTEM OVERRIDES === */
    footer {{visibility: hidden !important;}}
    .stAppDeployButton {{display:none !important;}}
    #stDecoration {{display:none !important;}}
    
    /* === SCROLLBAR STYLING === */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    
    ::-webkit-scrollbar-track {{
        background: {bg_secondary};
        border-radius: 4px;
    }}
    
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, {theme['accent']}, {theme['accent2']});
        border-radius: 4px;
        transition: var(--transition-normal);
    }}
    
    ::-webkit-scrollbar-thumb:hover {{
        background: {theme['accent2']};
    }}

    header[data-testid='stHeader'] {{
        background: rgba(0,0,0,0) !important;
        visibility: visible !important;
        backdrop-filter: blur(10px);
    }}

    button[data-testid='stSidebarCollapseButton'] {{
        background: linear-gradient(135deg, {theme['primary']} 0%, rgba(12,20,33,0.9) 100%) !important;
        color: {theme['accent']} !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        position: fixed !important;
        z-index: 1000001 !important;
        transition: var(--transition-normal) !important;
        backdrop-filter: blur(10px);
        box-shadow: var(--shadow-md);
    }}
    
    button[data-testid='stSidebarCollapseButton']:hover {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%) !important;
        color: {theme['primary']} !important;
        transform: scale(1.08) rotate(3deg);
        box-shadow: var(--shadow-glow);
    }}

    /* === MAIN LAYOUT === */
    .main {{ 
        background: linear-gradient(135deg, {bg_main} 0%, {bg_secondary} 50%, {bg_main} 100%) !important;
        color: {text_primary} !important;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        padding: 2rem 1rem;
        min-height: 100vh;
        position: relative;
    }}
    
    /* Subtle animated background pattern */
    .main::before {{
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: 
            radial-gradient(circle at 20% 80%, rgba(197,160,89,0.03) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(197,160,89,0.03) 0%, transparent 50%),
            radial-gradient(circle at 40% 40%, rgba(197,160,89,0.02) 0%, transparent 30%);
        pointer-events: none;
        z-index: 0;
    }}
    
    /* === TYPOGRAPHY === */
    h1, h2, h3, h4 {{ 
        color: {theme['primary'] if not dark else theme['accent']} !important;
        font-family: 'Playfair Display', Georgia, serif;
        font-weight: 600;
        letter-spacing: -0.02em;
        text-align: center;
        padding-bottom: 16px;
        margin-bottom: 24px;
        position: relative;
    }}
    
    h1::after, h2::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 80px;
        height: 3px;
        background: linear-gradient(90deg, transparent, {theme['accent']}, transparent);
        border-radius: 2px;
    }}
    
    h1 {{
        font-size: clamp(2rem, 5vw, 3rem) !important;
        margin-top: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    h2 {{
        font-size: clamp(1.5rem, 3.5vw, 2.2rem) !important;
    }}
    
    h3 {{
        font-size: clamp(1.2rem, 3vw, 1.6rem) !important;
        border-bottom: none;
    }}
    
    h4 {{
        font-size: clamp(1.1rem, 2.5vw, 1.4rem) !important;
        border-bottom: none;
    }}
    
    p, li, span {{
        font-family: 'Inter', sans-serif;
        line-height: 1.7;
    }}

    /* === BUTTONS - GLASSMORPHISM === */
    .stButton>button {{ 
        background: linear-gradient(135deg, {theme['primary']} 0%, rgba(12,20,33,0.95) 100%) !important;
        color: {theme['accent']} !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        width: 100% !important;
        padding: 16px 24px !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        border-radius: 12px !important;
        height: auto !important;
        min-height: 54px !important;
        font-size: 15px !important;
        cursor: pointer !important;
        transition: all var(--transition-normal) !important;
        box-shadow: var(--shadow-md), inset 0 1px 0 rgba(255,255,255,0.05) !important;
        backdrop-filter: blur(10px) !important;
        position: relative !important;
        overflow: hidden !important;
    }}
    
    .stButton>button::before {{
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(197,160,89,0.2), transparent);
        transition: left 0.5s ease;
        pointer-events: none;
    }}
    
    .stButton>button:hover::before {{
        left: 100%;
    }}
    
    .stButton>button:hover {{ 
        transform: translateY(-3px) !important;
        box-shadow: var(--shadow-lg), var(--shadow-glow) !important;
        border-color: {theme['accent']} !important;
        background: linear-gradient(135deg, {theme['primary']} 0%, {theme['accent']}22 100%) !important;
        color: {theme['accent2']} !important;
    }}
    
    .stButton>button:active {{
        transform: translateY(-1px) !important;
        box-shadow: var(--shadow-sm) !important;
    }}
    
    /* Primary CTA Button */
    .stButton>button[kind="primary"] {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%) !important;
        color: {theme['primary']} !important;
        border: none !important;
    }}

    /* === RESULT BOX - PREMIUM GLASSMORPHISM === */
    .result-box {{ 
        background: linear-gradient(145deg, rgba(30,42,56,0.95) 0%, rgba(22,32,44,0.98) 100%) !important;
        padding: 32px !important;
        border-radius: 16px !important;
        border: 1px solid rgba(197,160,89,0.25) !important;
        border-left: 4px solid {theme['accent']} !important;
        box-shadow: var(--shadow-lg), inset 0 1px 0 rgba(255,255,255,0.05) !important;
        backdrop-filter: blur(20px) !important;
        color: {text_primary} !important;
        font-size: 16px;
        line-height: 1.85;
        margin-bottom: 24px;
        animation: fadeInUp 0.6s cubic-bezier(0.23, 1, 0.32, 1);
        position: relative;
        overflow: hidden;
        transition: all var(--transition-normal);
    }}
    
    .result-box::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, {theme['accent']}, {theme['accent2']}, {theme['accent']});
        background-size: 200% 100%;
        animation: shimmer 3s ease-in-out infinite;
        pointer-events: none;
    }}
    
    @keyframes shimmer {{
        0%, 100% {{ background-position: 200% 0; }}
        50% {{ background-position: -200% 0; }}
    }}
    
    .result-box:hover {{
        border-color: rgba(197,160,89,0.4) !important;
        box-shadow: var(--shadow-xl), var(--shadow-glow) !important;
        transform: translateY(-2px);
    }}
    
    /* Result box ichidagi markdown elementlari */
    .result-box h1, .result-box h2, .result-box h3 {{
        color: {theme['accent']} !important;
        font-family: 'Playfair Display', serif !important;
        margin-top: 20px !important;
        margin-bottom: 12px !important;
        padding-bottom: 8px !important;
        border-bottom: 1px solid rgba(197,160,89,0.2) !important;
    }}
    
    .result-box h2 {{
        font-size: 1.3rem !important;
    }}
    
    .result-box h3 {{
        font-size: 1.1rem !important;
    }}
    
    .result-box p {{
        margin-bottom: 12px !important;
        line-height: 1.9 !important;
    }}
    
    .result-box strong, .result-box b {{
        color: {theme['accent2']} !important;
    }}
    
    .result-box hr {{
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(197,160,89,0.3), transparent) !important;
        margin: 16px 0 !important;
    }}
    
    .result-box ul, .result-box ol {{
        padding-left: 20px !important;
        margin-bottom: 12px !important;
    }}
    
    .result-box li {{
        margin-bottom: 6px !important;
    }}
    
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(30px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    /* === FORM INPUTS - PREMIUM === */
    .stTextInput>div>div>input,
    .stTextArea textarea {{
        background: linear-gradient(135deg, {bg_secondary} 0%, rgba(30,42,56,0.95) 100%) !important;
        color: {text_primary} !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
        transition: all var(--transition-normal) !important;
        font-size: 14px !important;
        box-shadow: var(--shadow-sm), inset 0 2px 4px rgba(0,0,0,0.1) !important;
    }}
    
    .stTextInput>div>div>input:focus,
    .stTextArea textarea:focus {{
        border-color: {theme['accent']} !important;
        box-shadow: 0 0 0 3px rgba(197,160,89,0.15), var(--shadow-md) !important;
        outline: none !important;
        background: linear-gradient(135deg, rgba(30,42,56,1) 0%, rgba(22,32,44,1) 100%) !important;
    }}
    
    .stTextInput>div>div>input::placeholder,
    .stTextArea textarea::placeholder {{
        color: rgba(253,250,241,0.4) !important;
        font-style: italic;
    }}

    /* === CHAT BUBBLES - PREMIUM === */
    .chat-user {{
        background: linear-gradient(135deg, rgba(30,42,56,0.95) 0%, rgba(22,32,44,0.9) 100%);
        color: {text_primary} !important;
        padding: 18px 22px;
        border-radius: 20px 20px 6px 20px;
        border: 1px solid rgba(12,20,33,0.3);
        border-left: 4px solid {theme['primary']};
        margin-bottom: 14px;
        box-shadow: var(--shadow-md);
        animation: slideInLeft 0.4s cubic-bezier(0.23, 1, 0.32, 1);
        backdrop-filter: blur(10px);
        position: relative;
    }}
    
    .chat-user::after {{
        content: '👤';
        position: absolute;
        bottom: -8px;
        left: 16px;
        font-size: 14px;
    }}
    
    .chat-ai {{
        background: linear-gradient(135deg, rgba(22,32,44,0.95) 0%, rgba(30,42,56,0.9) 100%);
        color: {text_primary} !important;
        padding: 18px 22px;
        border-radius: 20px 20px 20px 6px;
        border: 1px solid rgba(197,160,89,0.2);
        border-left: 4px solid {theme['accent']};
        margin-bottom: 18px;
        box-shadow: var(--shadow-md), 0 0 20px rgba(197,160,89,0.08);
        animation: slideInRight 0.4s cubic-bezier(0.23, 1, 0.32, 1);
        backdrop-filter: blur(10px);
        position: relative;
    }}
    
    .chat-ai::after {{
        content: '🤖';
        position: absolute;
        bottom: -8px;
        right: 16px;
        font-size: 14px;
    }}
    
    @keyframes slideInLeft {{
        from {{ opacity: 0; transform: translateX(-20px); }}
        to {{ opacity: 1; transform: translateX(0); }}
    }}
    
    @keyframes slideInRight {{
        from {{ opacity: 0; transform: translateX(20px); }}
        to {{ opacity: 1; transform: translateX(0); }}
    }}

    /* === SIDEBAR - PREMIUM === */
    section[data-testid='stSidebar'] {{
        background: linear-gradient(180deg, {theme['primary']} 0%, #0a0f18 100%) !important;
        border-right: 1px solid rgba(197,160,89,0.3) !important;
        box-shadow: 4px 0 20px rgba(0,0,0,0.3) !important;
    }}
    
    section[data-testid='stSidebar']::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23c5a059' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        pointer-events: none;
        z-index: 0;
    }}
    
    section[data-testid='stSidebar'] .stMarkdown {{
        color: #fdfaf1 !important;
        position: relative;
        z-index: 1;
    }}
    
    section[data-testid='stSidebar'] [data-testid='stMetricValue'] {{
        color: {theme['accent']} !important;
        font-size: 28px !important;
        font-weight: 700 !important;
        font-family: 'Playfair Display', serif !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }}
    
    section[data-testid='stSidebar'] [data-testid='stMetricLabel'] {{
        color: rgba(253,250,241,0.7) !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 12px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.1em !important;
    }}

    /* === IMAGE MAGNIFIER - PREMIUM === */
    .magnifier-container {{
        overflow: hidden;
        border: 2px solid rgba(197,160,89,0.4);
        border-radius: 16px;
        cursor: zoom-in;
        background: linear-gradient(135deg, #ffffff 0%, #f8f6f0 100%);
        padding: 12px;
        box-shadow: var(--shadow-lg), inset 0 0 20px rgba(0,0,0,0.03);
        transition: all var(--transition-normal);
        position: relative;
    }}
    
    .magnifier-container::before {{
        content: '🔍';
        position: absolute;
        top: 16px;
        right: 16px;
        font-size: 20px;
        opacity: 0;
        transition: opacity var(--transition-fast);
        z-index: 10;
        background: rgba(255,255,255,0.9);
        padding: 6px 10px;
        border-radius: 8px;
        box-shadow: var(--shadow-sm);
        pointer-events: none;
    }}
    
    .magnifier-container:hover::before {{
        opacity: 1;
    }}
    
    .magnifier-container:hover {{
        box-shadow: var(--shadow-xl), var(--shadow-glow);
        border-color: {theme['accent']};
        transform: translateY(-4px);
    }}
    
    .magnifier-container img {{
        transition: transform 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94);
        border-radius: 8px;
    }}
    
    .magnifier-container img:hover {{
        transform: scale(1.4);
    }}

    /* === ZOOM MODAL - PREMIUM === */
    .modal {{
        display: none;
        position: fixed;
        z-index: 99999;
        padding-top: 50px;
        left: 0;
        top: 0;
        width: 100%;
        height: 100%;
        overflow: auto;
        background-color: rgba(0,0,0,0.97);
        animation: fadeIn 0.3s cubic-bezier(0.23, 1, 0.32, 1);
        backdrop-filter: blur(10px);
    }}
    
    .modal-content {{
        margin: auto;
        display: block;
        width: 90%;
        max-width: 1400px;
        animation: zoomIn 0.4s cubic-bezier(0.23, 1, 0.32, 1);
        border-radius: 12px;
        box-shadow: 0 25px 80px rgba(0,0,0,0.5);
    }}
    
    @keyframes fadeIn {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
    }}
    
    @keyframes zoomIn {{
        from {{ transform: scale(0.8) translateY(20px); opacity: 0; }}
        to {{ transform: scale(1) translateY(0); opacity: 1; }}
    }}
    
    .modal-close {{
        position: absolute;
        top: 20px;
        right: 40px;
        color: rgba(255,255,255,0.8);
        font-size: 44px;
        font-weight: 300;
        transition: all var(--transition-fast);
        cursor: pointer;
        z-index: 100000;
        width: 50px;
        height: 50px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background: rgba(255,255,255,0.1);
        backdrop-filter: blur(10px);
    }}
    
    .modal-close:hover,
    .modal-close:focus {{
        color: {theme['accent']};
        background: rgba(197,160,89,0.2);
        transform: rotate(90deg);
    }}

    /* === CITATION BOX - PREMIUM === */
    .citation-box {{
        font-size: 13px;
        color: {text_secondary};
        background: linear-gradient(135deg, rgba(30,42,56,0.6) 0%, rgba(22,32,44,0.8) 100%);
        padding: 18px 22px;
        border-radius: 12px;
        border: 1px dashed rgba(197,160,89,0.4);
        margin-top: 20px;
        font-style: italic;
        box-shadow: var(--shadow-sm);
        position: relative;
        overflow: hidden;
    }}
    
    .citation-box::before {{
        content: '📚';
        position: absolute;
        top: 50%;
        left: -30px;
        transform: translateY(-50%);
        font-size: 60px;
        opacity: 0.05;
    }}

    /* === FILE UPLOADER - PREMIUM === */
    [data-testid='stFileUploader'] {{
        background: linear-gradient(135deg, rgba(30,42,56,0.5) 0%, rgba(22,32,44,0.7) 100%);
        border: 2px dashed rgba(197,160,89,0.4);
        border-radius: 16px;
        padding: 40px;
        text-align: center;
        transition: all var(--transition-normal);
        position: relative;
        overflow: hidden;
    }}
    
    [data-testid='stFileUploader']::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(45deg, transparent 30%, rgba(197,160,89,0.03) 50%, transparent 70%);
        background-size: 200% 200%;
        animation: uploadShimmer 3s ease-in-out infinite;
        pointer-events: none;
        z-index: 0;
    }}
    
    @keyframes uploadShimmer {{
        0% {{ background-position: 200% 200%; }}
        100% {{ background-position: -200% -200%; }}
    }}
    
    [data-testid='stFileUploader']:hover {{
        border-color: {theme['accent']};
        background: linear-gradient(135deg, rgba(30,42,56,0.7) 0%, rgba(22,32,44,0.9) 100%);
        box-shadow: var(--shadow-lg), var(--shadow-glow);
        transform: translateY(-2px);
    }}
    
    /* === EXPANDER STYLING === */
    .streamlit-expanderHeader {{
        background: linear-gradient(135deg, rgba(30,42,56,0.8) 0%, rgba(22,32,44,0.9) 100%) !important;
        border: 1px solid rgba(197,160,89,0.2) !important;
        border-radius: 12px !important;
        padding: 14px 18px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: {theme['accent']} !important;
        transition: all var(--transition-normal) !important;
    }}
    
    .streamlit-expanderHeader:hover {{
        background: linear-gradient(135deg, rgba(30,42,56,0.95) 0%, rgba(22,32,44,1) 100%) !important;
        border-color: {theme['accent']} !important;
        box-shadow: var(--shadow-md) !important;
    }}
    
    .streamlit-expanderContent {{
        background: rgba(22,32,44,0.5) !important;
        border: 1px solid rgba(197,160,89,0.1) !important;
        border-top: none !important;
        border-radius: 0 0 12px 12px !important;
        padding: 16px !important;
    }}
    
    /* === STATUS INDICATOR === */
    [data-testid='stStatusWidget'] {{
        background: linear-gradient(135deg, rgba(30,42,56,0.9) 0%, rgba(22,32,44,0.95) 100%) !important;
        border: 1px solid rgba(197,160,89,0.2) !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }}
    
    /* === SELECTBOX STYLING === */
    [data-testid='stSelectbox'] > div > div {{
        background: linear-gradient(135deg, rgba(30,42,56,0.8) 0%, rgba(22,32,44,0.9) 100%) !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        border-radius: 10px !important;
        color: {text_primary} !important;
    }}
    
    [data-testid='stSelectbox'] > div > div:hover {{
        border-color: {theme['accent']} !important;
    }}
    
    /* === MULTISELECT STYLING === */
    [data-testid='stMultiSelect'] > div > div {{
        background: linear-gradient(135deg, rgba(30,42,56,0.8) 0%, rgba(22,32,44,0.9) 100%) !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        border-radius: 10px !important;
    }}
    
    [data-testid='stMultiSelect'] span[data-baseweb='tag'] {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%) !important;
        color: {theme['primary']} !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}

    /* Ensure file uploader children are clickable */
    [data-testid='stFileUploader'] > div,
    [data-testid='stFileUploader'] button,
    [data-testid='stFileUploader'] input,
    [data-testid='stFileUploader'] label,
    [data-testid='stFileUploader'] section,
    [data-testid='stFileUploader'] [data-testid] {{
        position: relative !important;
        z-index: 1 !important;
    }}

    /* === DIVIDER - PREMIUM === */
    hr {{
        border: none;
        height: 1px;
        background: linear-gradient(90deg, transparent 0%, rgba(197,160,89,0.3) 20%, {theme['accent']} 50%, rgba(197,160,89,0.3) 80%, transparent 100%);
        margin: 40px 0;
        position: relative;
    }}
    
    hr::after {{
        content: '✦';
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        background: {theme['primary']};
        padding: 0 12px;
        color: {theme['accent']};
        font-size: 14px;
    }}

    /* === EMPTY STATE - PREMIUM === */
    .empty-state {{
        text-align: center;
        padding: 80px 30px;
        background: linear-gradient(145deg, rgba(30,42,56,0.6) 0%, rgba(22,32,44,0.8) 100%);
        border-radius: 20px;
        border: 2px dashed rgba(197,160,89,0.3);
        margin: 50px 0;
        box-shadow: var(--shadow-lg);
        position: relative;
        overflow: hidden;
    }}
    
    .empty-state::before {{
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(197,160,89,0.05) 0%, transparent 70%);
        animation: pulse 4s ease-in-out infinite;
        pointer-events: none;
    }}
    
    @keyframes pulse {{
        0%, 100% {{ transform: scale(1); opacity: 0.5; }}
        50% {{ transform: scale(1.1); opacity: 0.8; }}
    }}
    
    .empty-state h3 {{
        color: {theme['accent']};
        border: none;
        margin-bottom: 12px;
        position: relative;
        z-index: 1;
    }}
    
    .empty-state p {{
        position: relative;
        z-index: 1;
    }}

    /* === LOGIN CARD - PREMIUM === */
    .login-card {{
        background: linear-gradient(145deg, rgba(30,42,56,0.98) 0%, rgba(22,32,44,0.99) 100%);
        padding: 60px 50px;
        border-radius: 24px;
        box-shadow: var(--shadow-xl), 0 0 60px rgba(197,160,89,0.15);
        border: 1px solid rgba(197,160,89,0.3);
        animation: fadeInUp 0.8s cubic-bezier(0.23, 1, 0.32, 1);
        backdrop-filter: blur(20px);
        position: relative;
        overflow: hidden;
    }}
    
    .login-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, {theme['accent']}, {theme['accent2']}, {theme['accent']});
        background-size: 200% 100%;
        animation: shimmer 3s ease-in-out infinite;
        pointer-events: none;
    }}
    
    .login-card::after {{
        content: '';
        position: absolute;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: 80%;
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(197,160,89,0.3), transparent);
    }}
    
    .hero-title {{
        font-size: clamp(2.2rem, 5vw, 3.5rem);
        color: {theme['accent']};
        margin-bottom: 18px;
        font-weight: 700;
        text-align: center;
        font-family: 'Playfair Display', serif;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    
    .hero-subtitle {{
        font-size: clamp(1rem, 2vw, 1.15rem);
        color: rgba(253,250,241,0.7);
        text-align: center;
        margin-bottom: 40px;
        line-height: 1.7;
        font-family: 'Inter', sans-serif;
        max-width: 400px;
        margin-left: auto;
        margin-right: auto;
    }}

    /* === CREDIT PROGRESS BAR - PREMIUM === */
    .credit-bar-container {{
        background: rgba(0,0,0,0.3);
        border-radius: 12px;
        padding: 5px;
        margin: 18px 0;
        border: 1px solid rgba(197,160,89,0.2);
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.2);
    }}
    
    .credit-bar {{
        height: 12px;
        background: linear-gradient(90deg, {theme['accent']}, {theme['accent2']}, {theme['accent']});
        background-size: 200% 100%;
        border-radius: 10px;
        transition: width 0.6s cubic-bezier(0.23, 1, 0.32, 1);
        box-shadow: 0 0 15px rgba(197,160,89,0.6), inset 0 1px 0 rgba(255,255,255,0.3);
        animation: gradientMove 3s linear infinite;
    }}
    
    @keyframes gradientMove {{
        0% {{ background-position: 0% 50%; }}
        100% {{ background-position: 200% 50%; }}
    }}

    /* === SECTION HEADER - PREMIUM === */
    .section-header {{
        color: {theme['accent']} !important;
        font-size: 14px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        margin-top: 24px;
        margin-bottom: 12px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(197,160,89,0.2);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        display: flex;
        align-items: center;
        gap: 8px;
    }}
    
    .section-header::before {{
        content: '◆';
        font-size: 10px;
        color: {theme['accent']};
    }}

    /* === MOBILE NAV BUTTONS - PREMIUM === */
    .mobile-nav {{
        display: none;
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 1000;
        background: linear-gradient(135deg, {theme['primary']} 0%, rgba(12,20,33,0.98) 100%);
        padding: 12px 24px;
        border-radius: 60px;
        box-shadow: var(--shadow-xl), 0 0 30px rgba(197,160,89,0.2);
        border: 1px solid rgba(197,160,89,0.3);
        backdrop-filter: blur(20px);
    }}
    
    .mobile-nav button {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%);
        color: {theme['primary']};
        border: none;
        padding: 12px 24px;
        margin: 0 6px;
        border-radius: 24px;
        font-size: 16px;
        cursor: pointer;
        font-weight: 600;
        transition: all var(--transition-fast);
        box-shadow: var(--shadow-sm);
    }}
    
    .mobile-nav button:hover {{
        transform: scale(1.05);
        box-shadow: var(--shadow-md);
    }}

    /* === PROGRESS BAR STYLING === */
    [data-testid='stProgress'] > div > div > div {{
        background: linear-gradient(90deg, {theme['accent']}, {theme['accent2']}, {theme['accent']}) !important;
        background-size: 200% 100% !important;
        animation: gradientMove 2s linear infinite !important;
        border-radius: 8px !important;
    }}
    
    [data-testid='stProgress'] {{
        background: rgba(0,0,0,0.2) !important;
        border-radius: 8px !important;
    }}

    /* === TOAST STYLING === */
    [data-testid='stToast'] {{
        background: linear-gradient(135deg, rgba(30,42,56,0.98) 0%, rgba(22,32,44,0.99) 100%) !important;
        border: 1px solid rgba(197,160,89,0.3) !important;
        border-radius: 12px !important;
        box-shadow: var(--shadow-lg), 0 0 30px rgba(197,160,89,0.15) !important;
        backdrop-filter: blur(20px) !important;
    }}
    
    [data-testid='stToast'] > div {{
        color: {text_primary} !important;
        font-family: 'Inter', sans-serif !important;
    }}

    /* === ALERT/WARNING BOXES === */
    [data-testid='stAlert'] {{
        background: linear-gradient(135deg, rgba(30,42,56,0.9) 0%, rgba(22,32,44,0.95) 100%) !important;
        border-radius: 12px !important;
        border-left: 4px solid !important;
        padding: 16px 20px !important;
    }}
    
    .stSuccess {{
        border-left-color: #10b981 !important;
    }}
    
    .stWarning {{
        border-left-color: #f59e0b !important;
    }}
    
    .stError {{
        border-left-color: #ef4444 !important;
    }}
    
    .stInfo {{
        border-left-color: {theme['accent']} !important;
    }}

    /* === DOWNLOAD BUTTON === */
    [data-testid='stDownloadButton'] > button {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%) !important;
        color: {theme['primary']} !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 16px 28px !important;
        font-size: 15px !important;
        transition: all var(--transition-normal) !important;
        box-shadow: var(--shadow-md) !important;
    }}
    
    [data-testid='stDownloadButton'] > button:hover {{
        transform: translateY(-3px) !important;
        box-shadow: var(--shadow-lg), var(--shadow-glow) !important;
    }}

    /* === LOADING SPINNER === */
    .loading-spinner {{
        display: inline-block;
        width: 20px;
        height: 20px;
        border: 2px solid rgba(197,160,89,0.3);
        border-radius: 50%;
        border-top-color: {theme['accent']};
        animation: spin 1s ease-in-out infinite;
    }}
    
    @keyframes spin {{
        to {{ transform: rotate(360deg); }}
    }}

    /* === TOOLTIP STYLES === */
    [data-tooltip] {{
        position: relative;
        cursor: help;
    }}
    
    [data-tooltip]::after {{
        content: attr(data-tooltip);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%) translateY(-8px);
        background: {theme['primary']};
        color: {theme['accent']};
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 12px;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: all var(--transition-fast);
        box-shadow: var(--shadow-lg);
        border: 1px solid rgba(197,160,89,0.3);
    }}
    
    [data-tooltip]:hover::after {{
        opacity: 1;
        transform: translateX(-50%) translateY(-4px);
    }}

    /* === BADGE / TAG STYLES === */
    .badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    
    .badge-gold {{
        background: linear-gradient(135deg, {theme['accent']} 0%, {theme['accent2']} 100%);
        color: {theme['primary']};
    }}
    
    .badge-success {{
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
    }}

    /* === RESPONSIVE - ENHANCED === */
    @media (max-width: 768px) {{
        .main {{
            padding: 1rem 0.75rem;
        }}
        
        h1 {{
            font-size: 1.6rem !important;
        }}
        
        h1::after, h2::after {{
            width: 60px;
        }}
        
        .result-box {{
            padding: 22px !important;
            font-size: 15px !important;
            border-radius: 14px !important;
        }}
        
        .stButton>button {{
            font-size: 14px !important;
            padding: 14px 18px !important;
            border-radius: 10px !important;
        }}
        
        .login-card {{
            padding: 40px 25px;
            border-radius: 18px;
        }}
        
        .chat-user, .chat-ai {{
            padding: 14px 16px;
            border-radius: 14px 14px 4px 14px;
        }}
        
        .mobile-nav {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        section[data-testid='stSidebar'] {{
            width: 280px !important;
        }}
    }}
    
    @media (max-width: 480px) {{
        .main {{
            padding: 0.75rem 0.5rem;
        }}
        
        h1 {{
            font-size: 1.4rem !important;
        }}
        
        .login-card {{
            padding: 30px 20px;
        }}
        
        .hero-title {{
            font-size: 1.8rem !important;
        }}
        
        .hero-subtitle {{
            font-size: 0.95rem !important;
        }}
    }}
    
    /* === PRINT STYLES === */
    @media print {{
        .stButton, .mobile-nav, section[data-testid='stSidebar'] {{
            display: none !important;
        }}
        
        .main {{
            background: white !important;
        }}
        
        .result-box {{
            border: 1px solid #ccc !important;
            box-shadow: none !important;
        }}
    }}
    </style>

    <script>
    // === KEYBOARD SHORTCUTS ===
    document.addEventListener('keydown', function(e) {{
        // Esc - Close modal
        if (e.key === 'Escape') {{
            const modal = document.getElementById('imageModal');
            if (modal) modal.style.display = 'none';
        }}
        
        // Ctrl+Enter - Trigger analysis
        if (e.ctrlKey && e.key === 'Enter') {{
            e.preventDefault();
            const analysisBtn = Array.from(document.querySelectorAll('.stButton button'))
                .find(btn => btn.textContent.includes('AKADEMIK TAHLILNI BOSHLASH'));
            if (analysisBtn) analysisBtn.click();
        }}
        
        // Ctrl+S - Trigger download
        if (e.ctrlKey && e.key === 's') {{
            e.preventDefault();
            const downloadBtn = document.querySelector('[data-testid="stDownloadButton"]');
            if (downloadBtn) downloadBtn.click();
        }}
    }});

    // === IMAGE MODAL ===
    function setupModal() {{
        const images = document.querySelectorAll('.magnifier-container img');
        const modal = document.getElementById('imageModal');
        const modalImg = document.getElementById('modalImage');
        const closeBtn = document.querySelector('.modal-close');
        
        images.forEach(img => {{
            img.onclick = function() {{
                if (modal && modalImg) {{
                    modal.style.display = "block";
                    modalImg.src = this.src;
                }}
            }}
        }});
        
        if (closeBtn) {{
            closeBtn.onclick = function() {{
                modal.style.display = "none";
            }}
        }}
        
        if (modal) {{
            modal.onclick = function(e) {{
                if (e.target === modal) {{
                    modal.style.display = "none";
                }}
            }}
        }}
    }}

    // === MOBILE SWIPE GESTURES ===
    let touchstartX = 0;
    let touchendX = 0;
    
    document.addEventListener('touchstart', e => {{
        touchstartX = e.changedTouches[0].screenX;
    }});
    
    document.addEventListener('touchend', e => {{
        touchendX = e.changedTouches[0].screenX;
        handleSwipe();
    }});
    
    function handleSwipe() {{
        const threshold = 100;
        if (touchendX < touchstartX - threshold) {{
            // Swipe left - next page
            const nextBtn = document.getElementById('mobileNext');
            if (nextBtn) nextBtn.click();
        }}
        if (touchendX > touchstartX + threshold) {{
            // Swipe right - previous page
            const prevBtn = document.getElementById('mobilePrev');
            if (prevBtn) prevBtn.click();
        }}
    }}

    // Run after Streamlit renders
    setTimeout(setupModal, 1000);
    setInterval(setupModal, 2000); // Refresh for dynamic content
    </script>

    <!-- Modal HTML -->
    <div id="imageModal" class="modal">
        <span class="modal-close">&times;</span>
        <img class="modal-content" id="modalImage">
    </div>
""", unsafe_allow_html=True)

# --- 2. CORE SERVICES (SUPABASE & AI) ---
try:
    db = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    CORRECT_PASSWORD = st.secrets["APP_PASSWORD"]
    GEMINI_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets sozlanmagan!")
    st.stop()

# ==========================================
# DEMO MODE (PITCH / TANLOV UCHUN)
# ==========================================
# Eslatma:
# - DEMO_MODE=True bo'lsa, tizimga kirishda parol so'ralmaydi (faqat email).
# - Yangi foydalanuvchi birinchi kirishda avtomatik 50 kredit bilan yaratiladi.
DEMO_MODE = True
DEFAULT_DEMO_CREDITS = 50

def ensure_demo_user(email: str) -> None:
    """Agar foydalanuvchi mavjud bo'lmasa, uni demo krediti bilan yaratadi.

    Muhim:
    - Faqat tanlov/pitch jarayonida qulaylik uchun.
    - Jadval sxemasi noma'lum bo'lgani uchun minimal fieldlar bilan insert qilinadi.
    """
    try:
        # Avval mavjudligini tekshiramiz
        res = db.table("profiles").select("email").eq("email", email).execute()
        if not res.data:
            db.table("profiles").insert({
                "email": email,
                "credits": DEFAULT_DEMO_CREDITS,
            }).execute()
    except Exception:
        # Demo rejimda login to'xtab qolmasligi uchun xatoni yumshoq usulda yutamiz.
        # Kreditlar baribir 0 bo'lib qolishi mumkin (bazaga yozilmasa).
        pass

if not st.session_state.auth:
    # === ENHANCED LOGIN PAGE ===
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown(f"""
            <div class='login-card'>
                <div class='hero-title'>🏛 Manuscript AI</div>
                <div class='hero-subtitle'>
                    Qadimiy qo'lyozmalarni raqamli tahlil qilish va transliteratsiya 
                    qilish uchun sun'iy intellekt asosidagi platforma
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='margin-top:30px;'>🔐 Tizimga Kirish</h2>", unsafe_allow_html=True)
        
        email_in = st.text_input("📧 Email manzili", placeholder="example@domain.com")

        # DEMO_MODE=True bo'lsa, parol maydoni ko'rsatilmaydi (pitch/tanlov uchun qulay).
        if not DEMO_MODE:
            pwd_in = st.text_input("🔑 Parol", type="password", placeholder="Parolingizni kiriting")

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("✨ TIZIMGA KIRISH"):
            if not email_in:
                st.warning("⚠️ Iltimos, email manzilini kiriting")
            elif DEMO_MODE:
                st.session_state.auth = True
                st.session_state.u_email = email_in.strip().lower()
                ensure_demo_user(st.session_state.u_email)
                st.toast("✅ Demo rejimda tizimga kirdingiz!", icon="🎉")
                st.rerun()
            else:
                if pwd_in == CORRECT_PASSWORD:
                    st.session_state.auth = True
                    st.session_state.u_email = email_in.strip().lower()
                    st.toast("✅ Muvaffaqiyatli kirdingiz!", icon="🎉")
                    st.rerun()
                else:
                    st.error("❌ Parol noto'g'ri! Iltimos, qaytadan urinib ko'ring.")
    st.stop()

# --- AI ENGINE (UNCHANGED - DO NOT MODIFY) ---
genai.configure(api_key=GEMINI_KEY)
system_instruction = "Siz Manuscript AI mutaxassisiz. Tadqiqotchi d87809889-dot muallifligida ilmiy tahlillar qilasiz."
safety_settings = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=system_instruction,
    safety_settings=safety_settings
)

# ==========================================
# 3. YORDAMCHI FUNKSIYALAR (UNCHANGED)
# ==========================================

# ==========================================
# 3.1 ADVANCED IMAGE PREPROCESSING
# ==========================================
def safe_denoise(img: Image.Image) -> Image.Image:
    """Xavfsiz shovqin olib tashlash - PIL bilan"""
    try:
        # Median filter - shovqinni kamaytiradi, chetlarni saqlaydi
        return img.filter(ImageFilter.MedianFilter(size=3))
    except Exception:
        return img  # Xato bo'lsa original qaytaradi

def safe_deskew(img: Image.Image) -> Image.Image:
    """Xavfsiz qiyshiqlikni to'g'rilash - oddiy usul"""
    try:
        # Oddiy autorotate - EXIF asosida
        return ImageOps.exif_transpose(img) or img
    except Exception:
        return img

def adaptive_binarize(img: Image.Image) -> Image.Image:
    """Matn/fon ajratish - adaptive threshold"""
    try:
        # Grayscale bo'lishi kerak
        if img.mode != 'L':
            img = img.convert('L')
        
        # Oddiy threshold
        threshold = 128
        return img.point(lambda p: 255 if p > threshold else 0)
    except Exception:
        return img

def optimal_resize(img: Image.Image, target_size: int = 1800) -> Image.Image:
    """Optimal o'lchamga keltirish - AI uchun eng yaxshi"""
    try:
        w, h = img.size
        max_dim = max(w, h)
        
        # Agar kichik bo'lsa - kattalashtiramiz
        if max_dim < 1200:
            scale = 1200 / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Agar juda katta bo'lsa - kichraytramiz
        if max_dim > 2400:
            scale = target_size / max_dim
            new_w, new_h = int(w * scale), int(h * scale)
            return img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        return img
    except Exception:
        return img

def enhance_image_for_ai(img: Image.Image) -> Image.Image:
    """Rasmni AI tahlili uchun optimallashtirish - YANGILANGAN"""
    try:
        # 1. Optimal o'lcham
        img = optimal_resize(img)
        
        # 2. Shovqin olib tashlash
        img = safe_denoise(img)
        
        # 3. Grayscale
        img = ImageOps.grayscale(img)
        
        # 4. Auto-contrast
        img = ImageOps.autocontrast(img, cutoff=2)
        
        # 5. Kontrast oshirish
        img = ImageEnhance.Contrast(img).enhance(2.2)
        
        # 6. Keskinlik
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        
        return img
    except Exception as e:
        # Fallback: oddiy usul
        try:
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img, cutoff=1)
            img = ImageEnhance.Contrast(img).enhance(2.8)
            img = ImageEnhance.Sharpness(img).enhance(2.5)
            return img
        except:
            return img

# ==========================================
# 3.2 SMART CROPPING - Katta rasmlar uchun
# ==========================================
def should_split_image(img: Image.Image) -> bool:
    """Rasm bo'linishi kerakmi?"""
    w, h = img.size
    # Agar juda uzun yoki keng bo'lsa
    return h > 3000 or w > 3000 or (h > 2000 and w > 2000)

def split_image_smart(img: Image.Image) -> list:
    """Rasmni aqlli bo'laklarga bo'lish"""
    try:
        w, h = img.size
        crops = []
        
        # Vertikal bo'lish (asosan)
        if h > w * 1.5:  # Vertikal rasm
            # 2 qismga bo'lish (10% overlap)
            mid = h // 2
            overlap = int(h * 0.1)
            
            crop1 = img.crop((0, 0, w, mid + overlap))
            crop2 = img.crop((0, mid - overlap, w, h))
            crops = [crop1, crop2]
        
        # Gorizontal bo'lish
        elif w > h * 1.5:  # Gorizontal rasm
            mid = w // 2
            overlap = int(w * 0.1)
            
            crop1 = img.crop((0, 0, mid + overlap, h))
            crop2 = img.crop((mid - overlap, 0, w, h))
            crops = [crop1, crop2]
        
        # Kvadrat - 4 qismga
        else:
            mid_w, mid_h = w // 2, h // 2
            overlap_w = int(w * 0.05)
            overlap_h = int(h * 0.05)
            
            crops = [
                img.crop((0, 0, mid_w + overlap_w, mid_h + overlap_h)),  # Top-left
                img.crop((mid_w - overlap_w, 0, w, mid_h + overlap_h)),  # Top-right
                img.crop((0, mid_h - overlap_h, mid_w + overlap_w, h)),  # Bottom-left
                img.crop((mid_w - overlap_w, mid_h - overlap_h, w, h))   # Bottom-right
            ]
        
        return crops if crops else [img]
    except Exception:
        return [img]

def merge_results(results: list) -> str:
    """Bo'lak natijalarini birlashtirish va yaxlit ko'rinishga keltirish"""
    if not results:
        return ""
    if len(results) == 1:
        return results[0]
    
    # Bo'laklarni birlashtirish
    all_transliterations = []
    all_translations = []
    all_notes = []
    
    for r in results:
        # Har bir qismdan bo'limlarni ajratib olish
        text = r.strip()
        
        # Transliteratsiya qismini topish
        trans_start = text.lower().find("transliter")
        tarj_start = text.lower().find("tarjima") if text.lower().find("tarjima") > 0 else text.lower().find("translation")
        izoh_start = text.lower().find("izoh") if text.lower().find("izoh") > 0 else text.lower().find("note")
        
        if trans_start >= 0 and tarj_start > trans_start:
            all_transliterations.append(text[trans_start:tarj_start].strip())
        
        if tarj_start >= 0 and izoh_start > tarj_start:
            all_translations.append(text[tarj_start:izoh_start].strip())
        elif tarj_start >= 0:
            all_translations.append(text[tarj_start:].strip())
        
        if izoh_start >= 0:
            all_notes.append(text[izoh_start:].strip())
    
    # Yaxlit natija shakllantirish
    merged = "📜 **YAXLIT TAHLIL NATIJASI**\n\n"
    merged += "---\n\n"
    
    if all_transliterations:
        merged += "## 1. TRANSLITERATSIYA (Asl yozuv)\n\n"
        for i, t in enumerate(all_transliterations, 1):
            # Sarlavhalarni olib tashlash
            clean = t.replace("**TRANSLITERATSIYA**:", "").replace("**TRANSLITERATION**:", "").replace("1.", "").strip()
            if clean:
                merged += f"{clean}\n\n"
        merged += "---\n\n"
    
    if all_translations:
        merged += "## 2. TO'LIQ TARJIMA (O'zbek tilida)\n\n"
        for i, t in enumerate(all_translations, 1):
            clean = t.replace("**TARJIMA**:", "").replace("**TRANSLATION**:", "").replace("**TO'LIQ TARJIMA**:", "").replace("2.", "").strip()
            if clean:
                merged += f"{clean}\n\n"
        merged += "---\n\n"
    
    if all_notes:
        merged += "## 3. IZOHLAR\n\n"
        for i, t in enumerate(all_notes, 1):
            clean = t.replace("**IZOHLAR**:", "").replace("**NOTES**:", "").replace("3.", "").strip()
            if clean:
                merged += f"{clean}\n\n"
    
    return merged

# ==========================================
# 3.3 QUALITY-BASED RETRY
# ==========================================
def assess_quality(response_text: str) -> dict:
    """Javob sifatini baholash"""
    if not response_text:
        return {"score": 0, "reason": "Bo'sh javob", "retry": True}
    
    text = response_text.lower()
    
    # Noaniqlik belgilari
    unclear_count = text.count("[?]") + text.count("unclear") + text.count("noaniq")
    
    # Javob uzunligi
    word_count = len(response_text.split())
    
    # Skor hisoblash
    score = 100
    reasons = []
    
    if unclear_count > 10:
        score -= 30
        reasons.append(f"{unclear_count} noaniq belgi")
    elif unclear_count > 5:
        score -= 15
        reasons.append(f"{unclear_count} noaniq belgi")
    
    if word_count < 20:
        score -= 25
        reasons.append("Juda qisqa javob")
    
    if "error" in text or "xato" in text:
        score -= 20
        reasons.append("Xato xabari bor")
    
    return {
        "score": max(0, score),
        "reason": ", ".join(reasons) if reasons else "Yaxshi",
        "retry": score < 50
    }

def analyze_with_retry(model, prompt: str, img: Image.Image, max_retries: int = 2) -> tuple:
    """Sifat asosida qayta urinish bilan tahlil"""
    best_result = None
    best_score = 0
    
    for attempt in range(max_retries + 1):
        try:
            # Har urinishda rasm sifatini oshiramiz
            if attempt == 0:
                processed_img = enhance_image_for_ai(img)
            elif attempt == 1:
                # Yuqoriroq kontrast
                processed_img = enhance_image_for_ai(img)
                processed_img = ImageEnhance.Contrast(processed_img).enhance(1.3)
            else:
                # Binarization
                processed_img = enhance_image_for_ai(img)
                processed_img = adaptive_binarize(processed_img)
            
            payload = img_to_png_payload(processed_img)
            resp = model.generate_content([prompt, payload])
            
            if resp.candidates and resp.candidates[0].content.parts:
                result_text = resp.text
                quality = assess_quality(result_text)
                
                if quality["score"] > best_score:
                    best_result = result_text
                    best_score = quality["score"]
                
                # Yetarlicha yaxshi - to'xtash
                if quality["score"] >= 70:
                    return (result_text, quality, attempt + 1)
                
                # Retry kerak emas yoki oxirgi urinish
                if not quality["retry"] or attempt == max_retries:
                    return (best_result, quality, attempt + 1)
            
        except Exception as e:
            if attempt == max_retries:
                return (None, {"score": 0, "reason": str(e), "retry": False}, attempt + 1)
    
    return (best_result, {"score": best_score, "reason": "Max retry reached", "retry": False}, max_retries + 1)

def img_to_png_payload(img: Image.Image):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return {"mime_type": "image/png", "data": base64.b64encode(buffered.getvalue()).decode("utf-8")}

def fetch_live_credits(email: str):
    try:
        res = db.table("profiles").select("credits").eq("email", email).single().execute()
        return res.data["credits"] if res.data else 0
    except:
        return 0

def use_credit_atomic(email: str, count: int = 1):
    curr = fetch_live_credits(email)
    if curr >= count:
        db.table("profiles").update({"credits": curr - count}).eq("email", email).execute()
        return True
    return False

@st.cache_data(show_spinner=False)
def render_page(file_content, page_idx, scale, is_pdf):
    try:
        if is_pdf:
            pdf = pdfium.PdfDocument(file_content)
            img = pdf[page_idx].render(scale=scale).to_pil()
            pdf.close()
            return img
        return Image.open(io.BytesIO(file_content))
    except:
        return None

# ==========================================
# UI CONSTANTS (DEMO METRICS - NOT LIVE DATA)
# ==========================================
# NOTE: These are placeholder values for demo purposes
DEMO_MANUSCRIPTS_ANALYZED = 2840
DEMO_LANGUAGES_SUPPORTED = 12
DEMO_AVG_TIME_MINUTES = 2.5
DEMO_ACCURACY_RATE = 92.1
DEMO_ACTIVE_USERS = 180
DEMO_COUNTRIES = 4

# ==========================================
# LANDING PAGE FUNCTION (UI ONLY)
# ==========================================
def render_landing_page():
    """Render professional landing page for Hult Prize judges"""
    
    # Hero Section
    st.markdown(f"""
        <div style='text-align:center; padding:60px 20px; background:{card_bg}; 
                    border-radius:20px; box-shadow:0 10px 40px rgba(0,0,0,0.15); margin-bottom:40px;'>
            <h1 style='font-size:clamp(2.5rem, 6vw, 4rem); margin-bottom:20px; border:none; color:{theme['primary']};'>
                🏛 Manuscript AI
            </h1>
            <p style='font-size:clamp(1.2rem, 3vw, 1.8rem); color:{text_secondary}; margin-bottom:30px; line-height:1.6;'>
                Qadimiy qo'lyozmalarni raqamli tahlil qilish va transliteratsiya qilish uchun<br>
                sun'iy intellekt asosidagi akademik platforma
            </p>
        </div>
    """, unsafe_allow_html=True)
    
    # CTA Buttons
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        col_demo, col_learn = st.columns(2)
        with col_demo:
            if st.button("▶ DEMO'NI BOSHLASH", key="try_demo_btn", use_container_width=True):
                st.session_state.show_landing = False
                st.rerun()
        with col_learn:
            if st.button("📖 Batafsil Ma'lumot", key="learn_more_btn", use_container_width=True):
                st.session_state.show_landing = False
                st.rerun()
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Three-column layout for Problem/Solution/Impact
    col1, col2, col3 = st.columns(3)
    
    # PROBLEM Section
    with col1:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #e74c3c; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#e74c3c; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    📊 MUAMMO
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>100M+</span><br>
                        <span style='color:{text_secondary};'>qo'lyozmalar arxivda</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>99%</span><br>
                        <span style='color:{text_secondary};'>raqamli emas</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>$500-1000</span><br>
                        <span style='color:{text_secondary};'>sahifa uchun xarajat</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#e74c3c;'>2-3 hafta</span><br>
                        <span style='color:{text_secondary};'>manual tahlil vaqti</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    # SOLUTION Section
    with col2:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #3498db; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#3498db; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    ✨ YECHIM
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>AI-powered</span><br>
                        <span style='color:{text_secondary};'>OCR va tahlil</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>2 daqiqa</span><br>
                        <span style='color:{text_secondary};'>tahlil vaqti</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>95%</span><br>
                        <span style='color:{text_secondary};'>aniqlik darajasi</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#3498db;'>$5-10</span><br>
                        <span style='color:{text_secondary};'>sahifa uchun xarajat</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    # IMPACT Section
    with col3:
        st.markdown(f"""
            <div style='background:{card_bg}; padding:30px; border-radius:15px; 
                        border-left:8px solid #2ecc71; box-shadow:0 5px 20px rgba(0,0,0,0.1); min-height:400px;'>
                <h2 style='color:#2ecc71; font-size:1.8rem; margin-bottom:20px; border:none; text-align:left;'>
                    📈 TA'SIR
                </h2>
                <ul style='color:{text_primary}; font-size:1.1rem; line-height:2; list-style:none; padding:0;'>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_MANUSCRIPTS_ANALYZED:,}</span><br>
                        <span style='color:{text_secondary};'>tahlil qilingan</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_LANGUAGES_SUPPORTED}</span><br>
                        <span style='color:{text_secondary};'>til qo'llab-quvvatlash</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_COUNTRIES}</span><br>
                        <span style='color:{text_secondary};'>mamlakatda foydalanilmoqda</span>
                    </li>
                    <li style='margin-bottom:15px;'>
                        <span style='font-size:2rem; font-weight:bold; color:#2ecc71;'>{DEMO_ACTIVE_USERS:,}</span><br>
                        <span style='color:{text_secondary};'>faol foydalanuvchi</span>
                    </li>
                </ul>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # How it Works Section (Expandable)
    with st.expander("📖 QANDAY ISHLAYDI?", expanded=False):
        st.markdown(f"""
            <div style='padding:20px; color:{text_primary};'>
                <h3 style='color:{theme['accent']}; border:none;'>4 Oddiy Qadam:</h3>
                <ol style='font-size:1.1rem; line-height:2;'>
                    <li><b>Yuklash</b> - PDF, PNG, JPG formatidagi qo'lyozma faylini yuklang</li>
                    <li><b>Sozlash</b> - Til, xat turi va rasm sozlamalarini tanlang</li>
                    <li><b>Tahlil</b> - AI 2 daqiqada transliteratsiya va tarjima qiladi</li>
                    <li><b>Export</b> - Natijalarni DOCX, TXT yoki JSON formatida yuklab oling</li>
                </ol>
                <p style='margin-top:20px; font-size:1rem; color:{text_secondary};'>
                    <i>💡 Maslahat: Demo'ni sinab ko'rish uchun yuqoridagi "Demo'ni Boshlash" tugmasini bosing</i>
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    # Footer note
    st.markdown(f"""
        <div style='text-align:center; margin-top:60px; padding:30px; background:{bg_secondary}; border-radius:10px;'>
            <p style='color:{text_secondary}; font-size:0.9rem; margin:0;'>
                📊 Ko'rsatilgan statistik ma'lumotlar demo maqsadida keltirilgan<br>
                🔬 Tadqiqot: d87809889-dot | 📧 Aloqa uchun: {st.session_state.u_email}
            </p>
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. TADQIQOT INTERFEYSI
# ==========================================
with st.sidebar:
    st.markdown(f"<h2 style='color:{theme['accent']}; text-align:center; border:none;'>📜 Manuscript AI</h2>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center; color:#fdfaf1; font-size:14px;'>👤 <b>{st.session_state.u_email}</b></p>", unsafe_allow_html=True)
    
    current_credits = fetch_live_credits(st.session_state.u_email)
    
    # Enhanced credit display with progress bar
    st.metric("💳 Mavjud Kredit", f"{current_credits} sahifa")
    credit_percent = min((current_credits / 100) * 100, 100) if current_credits <= 100 else 100
    st.markdown(f"""
        <div class='credit-bar-container'>
            <div class='credit-bar' style='width:{credit_percent}%'></div>
        </div>
    """, unsafe_allow_html=True)
    
    st.divider()
    
    # === DARK MODE TOGGLE ===
    st.markdown("<p class='section-header'>🎨 Dizayn Sozlamalari</p>", unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write("🌙 Tungi Rejim" if not st.session_state.dark_mode else "☀️ Kunduzgi Rejim")
    with col2:
        if st.button("🔄", key="dark_toggle"):
            st.session_state.dark_mode = not st.session_state.dark_mode
            st.rerun()
    
    # === COLOR THEME SELECTOR ===
    new_theme = st.selectbox("Rang Sxemasi", list(THEMES.keys()), key="theme_select")
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        st.rerun()
    
    st.divider()
    
    # Section: Til va Xat
    st.markdown(f"<p class='section-header'>🌍 Til va Xat Tanlash</p>", unsafe_allow_html=True)
    lang = st.selectbox("Qo'lyozma tili", ["Chig'atoy", "Forscha", "Arabcha", "Eski Turkiy"])
    era = st.selectbox("Xat turi", ["Nasta'liq", "Suls", "Riq'a", "Kufiy", "Noma'lum"])
    
    st.divider()
    
    # Section: Rasm Sozlamalari
    st.markdown(f"<p class='section-header'>🎨 Rasm Sozlamalari</p>", unsafe_allow_html=True)
    br = st.slider("☀️ Yorqinlik", 0.5, 2.0, 1.0, 0.1)
    ct = st.slider("🎭 Kontrast", 0.5, 3.0, 1.3, 0.1)
    rot = st.select_slider("🔄 Aylantirish", options=[0, 90, 180, 270], value=0)

    st.divider()
    
    # === COMPARE MODE ===
    st.markdown(f"<p class='section-header'>🔄 Maxsus Rejimlar</p>", unsafe_allow_html=True)
    st.session_state.compare_mode = st.checkbox("🔄 Solishtirish Rejimi", value=st.session_state.compare_mode)
    
    st.divider()
    
    # === HISTORY SIDEBAR ===
    if st.session_state.history:
        with st.expander("📜 Tarix (Oxirgi 10 ta)"):
            for h in st.session_state.history[-10:][::-1]:
                if st.button(f"{h['date']} - {h['filename'][:25]}...", key=f"hist_{h['id']}"):
                    st.session_state.results = h['results']
                    st.session_state.chats = h.get('chats', {})
                    st.toast(f"✅ {h['filename']} yuklandi!", icon="📂")
                    st.rerun()
    
    st.divider()
    
    # KEYBOARD SHORTCUTS INFO
    with st.expander("⌨️ Klaviatura Yorliqlari"):
        st.markdown("""
            - **Esc** - Modal yopish
            - **Ctrl+Enter** - Tahlilni boshlash
            - **Ctrl+S** - Faylni saqlash
        """)
    
    st.divider()
    
    if st.button("🚪 TIZIMDAN CHIQISH"):
        st.session_state.auth = False
        st.toast("👋 Xayr!", icon="👋")
        st.rerun()
    
    # Back to Landing button
    if not st.session_state.show_landing:
        if st.button("🏠 Bosh Sahifaga Qaytish", key="back_to_landing"):
            st.session_state.show_landing = True
            st.rerun()

# === LANDING PAGE OR MAIN APP ===
if st.session_state.show_landing:
    render_landing_page()
    st.stop()

# === MAIN CONTENT AREA ===
st.markdown("<h1>📜 Raqamli Qo'lyozmalar Ekspertizasi</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:{text_secondary}; font-size:18px; margin-bottom:30px;'>Sun'iy intellekt yordamida qadimiy matnlarni tahlil qiling va transliteratsiya qiling</p>", unsafe_allow_html=True)

file = st.file_uploader("📤 Qo'lyozma faylini yuklang", type=["pdf", "png", "jpg", "jpeg"], label_visibility="visible")

if not file:
    # === EMPTY STATE ===
    st.markdown(f"""
        <div class='empty-state'>
            <h3 style='font-size:3rem; margin-bottom:20px;'>📜</h3>
            <h3>Qo'lyozma yuklang</h3>
            <p style='color:{text_secondary}; font-size:16px; line-height:1.6;'>
                PDF, PNG, JPG yoki JPEG formatidagi fayllarni yuklashingiz mumkin<br>
                Maksimal 15 sahifagacha tahlil qilish imkoniyati
            </p>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

if file:
    if st.session_state.get("last_fn") != file.name:
        with st.spinner("📂 Fayl tayyorlanmoqda..."):
            data = file.getvalue()
            imgs = []
            if file.type == "application/pdf":
                pdf = pdfium.PdfDocument(data)
                for i in range(min(len(pdf), 15)):
                    imgs.append(render_page(data, i, 3.5, True))
                pdf.close()
            else:
                imgs.append(render_page(data, 0, 1.0, False))

            st.session_state.imgs = imgs
            st.session_state.last_fn = file.name
            st.session_state.results, st.session_state.chats = {}, {}
            gc.collect()
            st.toast("✅ Fayl yuklandi!", icon="📁")

    processed = []
    for im in st.session_state.imgs:
        p = im.rotate(rot, expand=True)
        p = ImageEnhance.Brightness(p).enhance(br)
        p = ImageEnhance.Contrast(p).enhance(ct)
        processed.append(p)

    st.markdown("<h3 style='margin-top:30px;'>📑 Varaqlarni Tanlang</h3>", unsafe_allow_html=True)
    indices = st.multiselect(
        "Tahlil qilish uchun varaqlarni belgilang:",
        range(len(processed)),
        default=[0],
        format_func=lambda x: f"📄 Varaq {x+1}"
    )

    if not st.session_state.results and indices:
        st.markdown("<h3 style='margin-top:30px;'>🖼 Tanlangan Varaqlar</h3>", unsafe_allow_html=True)
        
        # === COMPARE MODE ===
        if st.session_state.compare_mode and len(indices) >= 2:
            st.info("🔄 Solishtirish rejimi: Birinchi 2 ta varaq yonma-yon")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"<h4>📄 Varaq {indices[0]+1}</h4>", unsafe_allow_html=True)
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[indices[0]], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown(f"<h4>📄 Varaq {indices[1]+1}</h4>", unsafe_allow_html=True)
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[indices[1]], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            cols = st.columns(min(len(indices), 3))
            for i, idx in enumerate(indices):
                with cols[i % 3]:
                    st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                    st.image(processed[idx], caption=f"Varaq {idx+1}", use_container_width=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("✨ AKADEMIK TAHLILNI BOSHLASH"):
        if current_credits >= len(indices):
            prompt = f"""Bu qo'lyozma rasmini tahlil qil ({era} davri).

MUHIM: Rasmga qarab manbaning HAQIQIY tilini aniqla (Chig'atoy, Forscha, Arabcha, Eski Turkiy yoki boshqa).
Foydalanuvchi kutgan til: {lang} - lekin bu faqat yordam uchun, haqiqiy tilni rasmdan aniqla.

VAZIFALAR (tartib bilan):

1. **MANBA TILI**: 
   Avval rasmga qarab manbaning haqiqiy tilini aniqla va yoz.

2. **TRANSLITERATSIYA (Asl yozuv)**:
   Matnni asl yozuvda, harf-harf yoz. Qatorlarni saqlagan holda.

3. **TO'LIQ TARJIMA (Zamonaviy o'zbek tiliga)**:
   Butun matnni zamonaviy o'zbek tiliga yaxlit, oqilona tarjima qil.
   Tarjima tabiiy va tushunarli bo'lsin.

4. **IZOHLAR**:
   Qadimiy yoki tushunarsiz so'zlarni qisqacha izohlash.

QOIDALAR:
- Noaniq harflarni [?] bilan belgilang
- Asl qator tuzilishini saqlang
- Ortiqcha sharh berma, qisqa bo'l
- Qisman ko'rinadigan matnni ko'ringan qismigacha yoz
- Barcha javoblar O'ZBEK TILIDA bo'lsin
- Manba tilini RASMGA QARAB haqqoniy aniqla"""
            
            # === PROGRESS TRACKER ===
            progress_bar = st.progress(0, text="🔍 Tahlil boshlanmoqda...")
            total_attempts = 0
            quality_issues = []
            
            for i, idx in enumerate(indices):
                with st.status(f"🔍 Varaq {idx+1} ekspertizadan o'tkazilmoqda...") as status:
                    try:
                        current_img = processed[idx]
                        
                        # === SMART CROPPING CHECK ===
                        if should_split_image(current_img):
                            status.update(label=f"📐 Varaq {idx+1} bo'laklarga bo'linmoqda...")
                            crops = split_image_smart(current_img)
                            crop_results = []
                            
                            for j, crop in enumerate(crops):
                                status.update(label=f"🔍 Varaq {idx+1} - Qism {j+1}/{len(crops)}...")
                                result, quality, attempts = analyze_with_retry(model, prompt, crop, max_retries=1)
                                total_attempts += attempts
                                
                                if result:
                                    crop_results.append(result)
                                    if quality["score"] < 70:
                                        quality_issues.append(f"Varaq {idx+1} qism {j+1}: {quality['reason']}")
                            
                            if crop_results:
                                st.session_state.results[idx] = merge_results(crop_results)
                                use_credit_atomic(st.session_state.u_email)
                                st.toast(f"✅ Varaq {idx+1} tayyor! ({len(crops)} qism)", icon="🎉")
                                st.success(f"✅ Varaq {idx+1} muvaffaqiyatli tahlil qilindi")
                            else:
                                st.error(f"⚠️ Varaq {idx+1} tahlil qilinmadi")
                        
                        else:
                            # === NORMAL ANALYSIS WITH RETRY ===
                            result, quality, attempts = analyze_with_retry(model, prompt, current_img, max_retries=2)
                            total_attempts += attempts
                            
                            if result:
                                st.session_state.results[idx] = result
                                use_credit_atomic(st.session_state.u_email)
                                
                                # Quality indicator
                                if quality["score"] >= 80:
                                    st.toast(f"✅ Varaq {idx+1} tayyor! (Yuqori sifat)", icon="🎉")
                                elif quality["score"] >= 50:
                                    st.toast(f"✅ Varaq {idx+1} tayyor! (O'rtacha sifat)", icon="⚠️")
                                    quality_issues.append(f"Varaq {idx+1}: {quality['reason']}")
                                else:
                                    st.toast(f"⚠️ Varaq {idx+1} tahlil qilindi, lekin sifat past", icon="⚠️")
                                    quality_issues.append(f"Varaq {idx+1}: {quality['reason']}")
                                
                                if attempts > 1:
                                    st.info(f"ℹ️ {attempts} urinishda tahlil qilindi")
                                st.success(f"✅ Varaq {idx+1} muvaffaqiyatli tahlil qilindi")
                            else:
                                st.error(f"⚠️ Varaq {idx+1}: AI javob berish imkoniyatiga ega emas")
                                
                    except Exception as e:
                        st.error(f"❌ Xatolik yuz berdi: {e}")
                
                # Update progress
                progress_bar.progress((i+1)/len(indices), text=f"📊 {i+1}/{len(indices)} varaq tahlil qilindi")
            
            # === QUALITY SUMMARY ===
            if quality_issues:
                with st.expander("⚠️ Sifat ogohlantirishlari", expanded=False):
                    for issue in quality_issues:
                        st.warning(issue)
                    st.info("💡 Tavsiya: Rasmlar sifatini oshiring yoki aniqroq skanerdan foydalaning")
            
            # Save to history
            st.session_state.history.append({
                'id': datetime.now().timestamp(),
                'date': datetime.now().strftime("%d.%m.%Y %H:%M"),
                'filename': file.name,
                'results': st.session_state.results.copy(),
                'chats': st.session_state.chats.copy(),
                'quality_issues': quality_issues,
                'total_attempts': total_attempts
            })
            
            # Keep only last 10
            if len(st.session_state.history) > 10:
                st.session_state.history = st.session_state.history[-10:]
            
            progress_bar.empty()
            st.balloons()
            st.toast("🎉 Barcha varaqlar tahlil qilindi!", icon="✨")
            st.rerun()
        else:
            st.warning(f"⚠️ Kredit yetarli emas! Sizda {current_credits} sahifa kredit bor, {len(indices)} sahifa tahlil qilish uchun yetarli emas.")

    if st.session_state.results:
        st.divider()
        st.markdown("<h2>📊 Tahlil Natijalari</h2>", unsafe_allow_html=True)
        
        # === EXPORT FORMAT SELECTOR ===
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"<p style='font-size:16px; color:{text_secondary};'>Natijalarni yuklab oling:</p>", unsafe_allow_html=True)
        with col2:
            export_format = st.selectbox("📥 Format", ["DOCX", "TXT", "JSON"], label_visibility="collapsed")
        
        final_text = ""
        today = datetime.now().strftime("%d.%m.%Y")
        
        # Mobile navigation buttons
        result_indices = sorted(st.session_state.results.keys())
        if len(result_indices) > 1:
            nav_col1, nav_col2, nav_col3 = st.columns([1, 2, 1])
            with nav_col1:
                if st.button("⬅️ Oldingi", key="mobilePrev", use_container_width=True):
                    if st.session_state.current_page_index > 0:
                        st.session_state.current_page_index -= 1
                        st.rerun()
            with nav_col3:
                if st.button("Keyingi ➡️", key="mobileNext", use_container_width=True):
                    if st.session_state.current_page_index < len(result_indices) - 1:
                        st.session_state.current_page_index += 1
                        st.rerun()

        for idx in result_indices:
            st.markdown(f"<h4 style='margin-top:40px;'>📖 Varaq {idx+1} - Tahlil</h4>", unsafe_allow_html=True)
            c1, c2 = st.columns([1, 1.3])

            with c1:
                st.markdown('<div class="magnifier-container">', unsafe_allow_html=True)
                st.image(processed[idx], use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            with c2:
                # Natijani markdown sifatida ko'rsatish
                st.markdown("<div class='result-box'>", unsafe_allow_html=True)
                st.markdown(st.session_state.results[idx])
                st.markdown("</div>", unsafe_allow_html=True)
                
                cite = f"Iqtibos: Manuscript AI (2026). Varaq {idx+1} tahlili ({lang}). Ekspert: d87809889-dot. Sana: {today}."
                st.markdown(f"<div class='citation-box'>📌 {cite}</div>", unsafe_allow_html=True)

                st.markdown(f"<p style='color:{text_secondary}; font-weight:bold; margin-top:20px; margin-bottom:8px;'>✏️ Tahrirlash:</p>", unsafe_allow_html=True)
                st.session_state.results[idx] = st.text_area(
                    f"Natijani tahrirlash",
                    value=st.session_state.results[idx],
                    height=350,
                    key=f"ed_{idx}",
                    label_visibility="collapsed"
                )

                final_text += f"\n\n--- PAGE {idx+1} ---\n{st.session_state.results[idx]}\n\n{cite}"

                # === CHAT INTERFACE ===
                st.markdown(f"<p style='color:{text_secondary}; font-weight:bold; margin-top:25px; margin-bottom:12px;'>💬 Savollar va Javoblar:</p>", unsafe_allow_html=True)
                
                st.session_state.chats.setdefault(idx, [])
                for ch in st.session_state.chats[idx]:
                    st.markdown(f"<div class='chat-user'><b>Savol:</b> {ch['q']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='chat-ai'><b>Javob:</b> {ch['a']}</div>", unsafe_allow_html=True)

                q = st.text_input("🤔 Savolingizni yozing:", key=f"q_in_{idx}", placeholder="Matn haqida savol bering...")
                if st.button(f"📤 So'rash", key=f"btn_{idx}"):
                    if q:
                        with st.spinner("🤖 AI javob tayyorlayapti..."):
                            chat_prompt = f"""Qo'lyozma hujjati haqida savol berildi.

HUJJAT MAZMUNI:
{st.session_state.results[idx]}

SAVOL: {q}

QOIDALAR:
- Javobni O'ZBEK TILIDA ber
- Qisqa va aniq javob ber
- Agar javob hujjatda bo'lmasa, shuni ayt"""
                            chat_res = model.generate_content([
                                chat_prompt,
                                img_to_png_payload(processed[idx])
                            ])
                            st.session_state.chats[idx].append({"q": q, "a": chat_res.text})
                            st.toast("✅ Javob olindi!", icon="💬")
                            st.rerun()
                    else:
                        st.warning("⚠️ Iltimos, avval savol yozing!")

        if final_text:
            st.divider()
            
            # === EXPORT BASED ON FORMAT ===
            if export_format == "DOCX":
                doc = Document()
                doc.add_paragraph(final_text)
                bio = io.BytesIO()
                doc.save(bio)
                st.download_button(
                    "📥 WORD FORMATDA YUKLAB OLISH",
                    bio.getvalue(),
                    "manuscript_ai_report.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    on_click=lambda: st.toast("✅ DOCX yuklab olindi!", icon="📥")
                )
            elif export_format == "TXT":
                st.download_button(
                    "📥 TEXT FORMATDA YUKLAB OLISH",
                    final_text,
                    "manuscript_ai_report.txt",
                    mime="text/plain",
                    on_click=lambda: st.toast("✅ TXT yuklab olindi!", icon="📥")
                )
            elif export_format == "JSON":
                json_data = json.dumps({
                    "metadata": {
                        "date": today,
                        "language": lang,
                        "script": era,
                        "filename": file.name,
                        "user": st.session_state.u_email
                    },
                    "results": st.session_state.results,
                    "chats": st.session_state.chats
                }, ensure_ascii=False, indent=2)
                st.download_button(
                    "📥 JSON FORMATDA YUKLAB OLISH",
                    json_data,
                    "manuscript_ai_report.json",
                    mime="application/json",
                    on_click=lambda: st.toast("✅ JSON yuklab olindi!", icon="📥")
                )

gc.collect()
