from __future__ import annotations

import streamlit as st


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: #1a1b25; }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 6rem;
            max-width: 820px;
            margin-left: auto;
            margin-right: auto;
        }
        section[data-testid="stSidebar"] {
            background: #161720;
            border-right: 1px solid rgba(255,255,255,0.05);
        }
        section[data-testid="stSidebar"] * { color: #c5cde0; }
        section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
            background: transparent !important;
            border: 1px solid transparent !important;
            color: #b0b8ce !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 9px 14px !important;
            border-radius: 8px !important;
            font-size: 0.875rem !important;
            font-weight: 400 !important;
            width: 100% !important;
            box-shadow: none !important;
            transition: background 0.12s, color 0.12s !important;
        }
        section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
            background: rgba(255,255,255,0.07) !important;
            color: #fff !important;
        }
        section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
            background: rgba(255,255,255,0.08) !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            color: #ffffff !important;
            text-align: left !important;
            justify-content: flex-start !important;
            padding: 9px 14px !important;
            border-radius: 8px !important;
            font-size: 0.875rem !important;
            font-weight: 500 !important;
            width: 100% !important;
            box-shadow: none !important;
        }
        h1, h2, h3 { letter-spacing: -0.02em; color: #eef2ff; }
        h1 { font-weight: 800 !important; }
        h2 { font-weight: 700 !important; }
        p, li, span, div { color: #c5cde0; }
        [data-testid="stChatMessage"] { background: transparent !important; border: none !important; }
        .card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 12px;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.025);
            border: 1px solid rgba(255,255,255,0.07);
            padding: 14px 16px;
            border-radius: 14px;
        }
        .suggestion-btn button {
            background: rgba(255,255,255,0.04) !important;
            border: 1px solid rgba(255,255,255,0.09) !important;
            color: #b8c2d8 !important;
            border-radius: 12px !important;
            font-size: 0.85rem !important;
            font-weight: 400 !important;
            text-align: left !important;
            padding: 12px 16px !important;
            line-height: 1.4 !important;
            height: auto !important;
            min-height: 3.5rem !important;
        }
        .suggestion-btn button:hover {
            background: rgba(255,255,255,0.08) !important;
            border-color: rgba(255,255,255,0.18) !important;
            color: #eef2ff !important;
        }
        [data-testid="stChatInput"] {
            background: #22243a !important;
            border: 1px solid rgba(255,255,255,0.1) !important;
            border-radius: 14px !important;
        }
        [data-testid="stChatInput"] textarea { color: #eef2ff !important; background: transparent !important; }
        [data-testid="stChatInput"] button { color: #eef2ff !important; }
        .pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.1);
            margin-right: 6px;
            margin-bottom: 6px;
            background: rgba(255,255,255,0.03);
            font-size: 0.82rem;
        }
        .muted { color: #6b7694; font-size: 0.875rem; }
        .stButton button, .stDownloadButton button { border-radius: 10px !important; font-weight: 500 !important; }
        #MainMenu { visibility: hidden; }
        footer    { visibility: hidden; }
        .src-chip {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: 6px;
            padding: 4px 9px;
            font-size: 11px !important;
            color: #888891 !important;
            margin-right: 6px;
            margin-bottom: 5px;
        }
        .src-chips-label {
            font-size: 9.5px !important;
            color: #454550 !important;
            font-weight: 600;
            letter-spacing: 0.07em;
            margin-bottom: 6px;
            text-transform: uppercase;
        }
        small[data-testid="InputInstructions"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
