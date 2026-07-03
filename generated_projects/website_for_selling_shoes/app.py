import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.app_logic import normalize_item


st.set_page_config(page_title="Create a website for selling shoes online", layout="wide")
st.title("Create a website for selling shoes online")
st.write("This generated app is ready for you to extend.")

with st.form("demo_form"):
    item = st.text_input("Item")
    submitted = st.form_submit_button("Save")

if submitted and item:
    st.success(f"Saved: {normalize_item(item)}")
