#!/usr/bin/env python
"""
PolyFinances Datathon 2025 - Risk Dashboard

Streamlit dashboard for uploading and viewing regulatory risk data.
"""

import streamlit as st
import logging
from pathlib import Path
from datetime import datetime

from src.dashboard import FileUploadWidget

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

# Page config
st.set_page_config(
    page_title="PolyFinances - Risk Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main > div {
        padding-top: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    
    # Header
    st.title("📊 Risk Dashboard")
    st.markdown("Upload regulatory documents to analyze risk factors")
    
    # Initialize upload widget
    upload_widget = FileUploadWidget()
    
    # Render upload interface
    result = upload_widget.render(
        accept_types=["csv", "html", "xml"],
        max_file_size=100  # 100 MB max
    )
    
    # Sidebar
    with st.sidebar:
        st.header("Dashboard Info")
        st.write("**Version:** 1.0.0 (MVP)")
        st.write("**Last Updated:**", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        st.divider()
        
        st.header("Instructions")
        st.markdown("""
        1. Upload a regulatory document
        2. Select processing options
        3. View results
        
        **Supported Formats:**
        - CSV (Financial data)
        - HTML (SEC filings, legislation)
        - XML (Legislation)
        """)
        
        st.divider()
        
        st.header("Status")
        if result.get('status') == 'success':
            st.success("✓ System Ready")
        elif result.get('status') == 'no_file':
            st.info("⊘ No file uploaded")
        else:
            st.warning("⚠ Check configuration")


if __name__ == "__main__":
    main()

