"""Skeuomorphic and Minimalist Streamlit Theme (CSS Injection)."""

import streamlit as st

from app.config import APP_TITLE


def inject_claude_theme() -> None:
    st.markdown(
        f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">

<style>
    /* Design Tokens */
    :root {{
        --bg-primary: #f5f3ed;
        --bg-card: #ffffff;
        --text-primary: #1a1a1a;
        --text-muted: #5e5e5e;
        --accent-color: #d97757;
        --accent-glow: rgba(217, 119, 87, 0.15);
        --border-color: #e5e0d8;
        --border-light: rgba(255, 255, 255, 0.6);
        --shadow-soft: 0 4px 20px -2px rgba(0, 0, 0, 0.05), 0 0 0 1px rgba(0, 0, 0, 0.02);
        --shadow-skeuo-out: 6px 6px 12px #e6e2da, -6px -6px 12px #ffffff;
        --shadow-skeuo-in: inset 3px 3px 6px #e6e2da, inset -3px -3px 6px #ffffff;
        --shadow-glow: 0 0 12px rgba(16, 185, 129, 0.6);
    }}

    /* Global App Framework */
    .stApp {{
        background-color: var(--bg-primary);
        font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
        color: var(--text-primary);
    }}

    header[data-testid="stHeader"] {{
        background: transparent;
    }}

    .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 5rem;
        max-width: 1200px;
        margin: 0 auto;
    }}

    /* Hide Streamlit Default UI Elements */
    #MainMenu, .stDeployButton, footer, header {{
        visibility: hidden;
        height: 0;
        position: fixed;
    }}

    /* Sidebar Customization */
    [data-testid="stSidebar"] {{
        background-color: var(--bg-primary) !important;
        border-right: 1px solid var(--border-color);
        box-shadow: 3px 0 15px rgba(0,0,0,0.02);
    }}

    [data-testid="stSidebar"] .block-container {{
        padding: 1.5rem 1rem;
    }}

    /* Tactile Cards & Containers */
    .skeuo-card {{
        background-color: var(--bg-card);
        border: 1px solid var(--border-color);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: var(--shadow-skeuo-out);
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    
    .skeuo-card:hover {{
        transform: translateY(-2px);
        box-shadow: 8px 8px 16px #e0dcd2, -8px -8px 16px #ffffff;
    }}

    .glass-panel {{
        background: rgba(255, 255, 255, 0.7);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--border-light);
        border-radius: 16px;
        padding: 1.25rem;
        margin-bottom: 1.25rem;
        box-shadow: var(--shadow-soft);
    }}

    /* Typography */
    h1, h2, h3, h4 {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 700;
        letter-spacing: -0.02em;
        color: var(--text-primary);
    }}

    .brand-title {{
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2.2rem;
        font-weight: 600;
        color: var(--text-primary);
        letter-spacing: -0.03em;
        margin-bottom: 0.25rem;
    }}

    .brand-subtitle {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 0.9rem;
        color: var(--text-muted);
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 1.5rem;
    }}

    /* Tactile / Skeuomorphic Buttons */
    .stButton > button {{
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        color: var(--text-primary) !important;
        background: #fbfaf8 !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        box-shadow: 3px 3px 6px #e6e2da, -3px -3px 6px #ffffff !important;
        transition: all 0.2s ease !important;
        padding: 0.5rem 1rem !important;
    }}

    .stButton > button:hover {{
        border-color: var(--accent-color) !important;
        background: #ffffff !important;
        color: var(--accent-color) !important;
        box-shadow: 4px 4px 8px #e2ded5, -4px -4px 8px #ffffff !important;
        transform: translateY(-1px);
    }}

    .stButton > button:active {{
        box-shadow: var(--shadow-skeuo-in) !important;
        transform: translateY(1px);
    }}

    /* Primary Accent Button */
    .stButton > button[kind="primary"] {{
        background: var(--accent-color) !important;
        border-color: var(--accent-color) !important;
        color: white !important;
        box-shadow: 3px 3px 6px #e6e2da, 0 0 12px rgba(217, 119, 87, 0.2) !important;
    }}

    .stButton > button[kind="primary"]:hover {{
        background: #e28566 !important;
        color: white !important;
        box-shadow: 4px 4px 8px #e2ded5, 0 0 16px rgba(217, 119, 87, 0.35) !important;
    }}

    /* Glowing LED Indicator */
    .led-indicator {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        box-shadow: var(--shadow-glow);
        margin-right: 6px;
        animation: pulse-glow 2s infinite alternate;
    }}

    @keyframes pulse-glow {{
        0% {{
            box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
            opacity: 0.7;
        }}
        100% {{
            box-shadow: 0 0 14px rgba(16, 185, 129, 0.9);
            opacity: 1;
        }}
    }}

    .led-offline {{
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #ef4444;
        margin-right: 6px;
    }}

    /* Status Badges */
    .badge {{
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.75rem;
        font-weight: 600;
        border-radius: 30px;
        text-transform: uppercase;
    }}

    .badge-allowed {{
        background-color: rgba(16, 185, 129, 0.1);
        color: #047857;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }}

    .badge-blocked {{
        background-color: rgba(239, 68, 68, 0.1);
        color: #b91c1c;
        border: 1px solid rgba(239, 68, 68, 0.2);
    }}

    .badge-pending {{
        background-color: rgba(245, 158, 11, 0.1);
        color: #b45309;
        border: 1px solid rgba(245, 158, 11, 0.2);
    }}

    /* Code Blocks */
    code, pre {{
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
    }}

    /* Streamlit Chat Feed Adjustments */
    div[data-testid="stChatMessage"] {{
        background-color: transparent !important;
        border: none !important;
        padding: 1rem 0 !important;
        border-bottom: 1px solid rgba(0, 0, 0, 0.03) !important;
    }}

    div[data-testid="stChatMessage"] .stMarkdown {{
        font-size: 0.98rem;
        line-height: 1.7;
    }}

    /* Chat Input Styling */
    div[data-testid="stChatInput"] {{
        background: var(--bg-primary) !important;
        border-top: 1px solid var(--border-color) !important;
        padding-top: 1.25rem !important;
    }}

    div[data-testid="stChatInput"] textarea {{
        border: 1px solid var(--border-color) !important;
        border-radius: 14px !important;
        background-color: var(--bg-card) !important;
        box-shadow: var(--shadow-skeuo-in) !important;
        transition: all 0.2s ease !important;
    }}

    div[data-testid="stChatInput"] textarea:focus {{
        border-color: var(--accent-color) !important;
        box-shadow: 0 0 0 3px var(--accent-glow) !important;
    }}

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background-color: rgba(0,0,0,0.02);
        padding: 6px;
        border-radius: 12px;
        border: 1px solid var(--border-color);
        box-shadow: var(--shadow-skeuo-in);
    }}

    .stTabs [data-baseweb="tab"] {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-weight: 500;
        color: var(--text-muted);
        background-color: transparent;
        border-radius: 8px;
        padding: 8px 16px;
        transition: all 0.2s ease;
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        color: var(--text-primary);
        background-color: rgba(255, 255, 255, 0.4);
    }}

    .stTabs [aria-selected="true"] {{
        color: var(--accent-color) !important;
        background-color: var(--bg-card) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.03), 0 0 0 1px var(--border-color);
        font-weight: 600;
    }}
    
    /* Scrollbars */
    ::-webkit-scrollbar {{
        width: 8px;
        height: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: transparent;
    }}
    ::-webkit-scrollbar-thumb {{
        background: var(--border-color);
        border-radius: 4px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: #c5beb4;
    }}

    /* --- Accessibility & Contrast Overrides --- */

    /* Force dark text for standard elements on light background, excluding code blocks */
    .stApp p, 
    .stApp label, 
    .stApp h1, 
    .stApp h2, 
    .stApp h3, 
    .stApp h4, 
    .stApp h5, 
    .stApp h6,
    .stApp li {{
        color: var(--text-primary) !important;
    }}

    /* Force text color for generic spans, except syntax highlighter tokens */
    .stApp span:not([class*="token"]):not(pre span):not(code span) {{
        color: var(--text-primary) !important;
    }}

    /* Ensure chat message items have dark text */
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span:not([class*="token"]) {{
        color: var(--text-primary) !important;
    }}

    /* Text input boundaries and text colors */
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    div[data-testid="stTextArea"] div[data-baseweb="textarea"],
    div[data-testid="stNumberInput"] div[data-baseweb="input"] {{
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        background-color: var(--bg-card) !important;
        box-shadow: var(--shadow-skeuo-in) !important;
    }}

    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stNumberInput"] input {{
        color: var(--text-primary) !important;
    }}

    /* Selectbox boundaries and text colors */
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {{
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
        background-color: var(--bg-card) !important;
        box-shadow: var(--shadow-skeuo-in) !important;
    }}

    div[data-testid="stSelectbox"] [role="button"],
    div[data-testid="stSelectbox"] select {{
        color: var(--text-primary) !important;
    }}

    /* Dropdown popover list styling (portals outside .stApp) */
    div[data-baseweb="popover"] ul,
    div[data-baseweb="menu"] ul,
    div[role="listbox"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 10px !important;
    }}
    
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li,
    div[role="option"] {{
        color: var(--text-primary) !important;
        background-color: var(--bg-card) !important;
    }}
    
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="menu"] li:hover,
    div[role="option"]:hover {{
        background-color: var(--bg-primary) !important;
        color: var(--accent-color) !important;
    }}

    /* File Uploader styling */
    div[data-testid="stFileUploader"] {{
        border: 2px dashed var(--border-color) !important;
        background-color: rgba(255, 255, 255, 0.4) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }}
    
    div[data-testid="stFileUploader"] section {{
        background-color: transparent !important;
    }}

    /* Alert / Notification banners text colors */
    div[data-testid="stNotification"] {{
        border-radius: 12px !important;
        border: 1px solid rgba(0,0,0,0.05) !important;
        box-shadow: var(--shadow-soft) !important;
    }}
    
    div[data-testid="stNotification"] p,
    div[data-testid="stNotification"] span {{
        color: #1a1a1a !important; /* Force highly legible dark text */
    }}

    /* Custom styled containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: var(--bg-card) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 16px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        box-shadow: var(--shadow-skeuo-out) !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }}

    div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 8px 8px 16px #e0dcd2, -8px -8px 16px #ffffff !important;
    }}

    /* Sidebar Glass Panels Override */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"] {{
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 16px !important;
        padding: 1.25rem !important;
        box-shadow: var(--shadow-soft) !important;
        margin-bottom: 1.25rem !important;
        transform: none !important;
    }}
    [data-testid="stSidebar"] div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
        transform: none !important;
        box-shadow: var(--shadow-soft) !important;
    }}
</style>
""",
        unsafe_allow_html=True,
    )


def render_brand_header() -> None:
    st.markdown(
        f'<div class="brand-title">{APP_TITLE}</div>'
        '<div class="brand-subtitle">✦ Agentverse Edge Client Node ✦</div>',
        unsafe_allow_html=True,
    )
