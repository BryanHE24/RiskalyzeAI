# File path: frontend/main.py
# frontend/main
import streamlit as st
from pathlib import Path

# App configuration
st.set_page_config(
    page_title="Ticket Resolution Assistant",
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        'About': "Ticket resolution system with AI assistance"
    }
)

# Load CSS (optional)
css_path = Path(__file__).parent / "assets/styles.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Main page content (optional)
st.title("Welcome to Ticket Resolution Assistant")
st.markdown("""
    Select a page from the sidebar to get started.
    - **Chat Assistant**: Get help with specific tickets
    - **Analytics Dashboard**: View system-wide insights
""")
