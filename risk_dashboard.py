#!/usr/bin/env python
"""
Regulatory Risk Dashboard - Streamlit Application

Main dashboard for visualizing regulatory risk factors for companies
based on similarity between SEC filings and legislation.
"""

import streamlit as st
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from src.dashboard.risk_factors_widget import RiskFactorsWidget

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)

logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Regulatory Risk Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
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
    .risk-high {
        color: #ff4444;
        font-weight: bold;
    }
    .risk-medium {
        color: #ffaa00;
        font-weight: bold;
    }
    .risk-low {
        color: #44aa44;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main dashboard application."""
    
    st.title("Regulatory Risk Dashboard")
    st.markdown("Analyze the impact of proposed or existing legislation on company filings.")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Data source selection
        data_source = st.radio(
            "Data Source",
            ["Test Results JSON", "Risk Data JSON"],
            help="Select the format of your input data"
        )
        
        # File upload or path input
        if data_source == "Test Results JSON":
            st.markdown("**Upload test results JSON file**")
            uploaded_file = st.file_uploader(
                "Choose a file",
                type=["json"],
                help="Upload a test results JSON file (e.g., AAPL_opensearch_test_results.json)"
            )
            
            if uploaded_file:
                # Save to temporary file
                temp_path = Path("temp_upload.json")
                with open(temp_path, 'wb') as f:
                    f.write(uploaded_file.getbuffer())
                
                data_path = temp_path
            else:
                # Try default path
                default_path = Path("output/AAPL_opensearch_test_results.json")
                if default_path.exists():
                    st.info(f"Using default: {default_path}")
                    data_path = default_path
                else:
                    data_path = None
        else:
            # Risk Data JSON
            data_path_input = st.text_input(
                "Path to risk data JSON",
                value="output/risk_data.json",
                help="Path to risk data JSON file (CompanyRiskProfile format)"
            )
            data_path = Path(data_path_input) if data_path_input else None
        
        st.divider()
        st.markdown("**Instructions:**")
        st.markdown("""
        1. Upload or specify path to risk data
        2. Use filters to narrow down results
        3. Click on companies to see detailed risk factors
        4. Export results as CSV or JSON
        """)
    
    # Initialize widget and load data
    if data_path and Path(data_path).exists():
        widget = RiskFactorsWidget(data_path=data_path)
        
        if widget.load_data():
            widget.render()
        else:
            st.error("Failed to load risk data. Please check the file format and path.")
    elif data_path:
        st.warning(f"Data file not found: {data_path}")
        st.info("Please upload a file or provide a valid path to risk data.")
    else:
        st.info("Please upload a risk data file or specify a path to get started.")


if __name__ == "__main__":
    main()

