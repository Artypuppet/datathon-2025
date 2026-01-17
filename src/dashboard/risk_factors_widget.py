"""
Risk Factors Widget for Streamlit Dashboard.

Displays regulatory risk factors for companies based on legislation similarity.
"""

import streamlit as st
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from .data_models import CompanyRiskProfile, LegislationContribution, SentenceContribution
from .data_transformer import RiskDataTransformer

logger = logging.getLogger(__name__)


class RiskFactorsWidget:
    """
    Streamlit widget for displaying company risk factors from legislation.
    
    Features:
    - Interactive filtering by legislation and risk score
    - Company search
    - Color-coded risk scores
    - Detailed sentence contributions
    - Export functionality
    """
    
    def __init__(self, data_path: Optional[Path] = None):
        """
        Initialize widget.
        
        Args:
            data_path: Path to risk data JSON file
        """
        self.data_path = data_path
        self.transformer = RiskDataTransformer()
        self.profiles: List[CompanyRiskProfile] = []
    
    def load_data(self, data_path: Optional[Path] = None) -> bool:
        """
        Load risk data from JSON file or test results.
        
        Args:
            data_path: Path to data file (overrides self.data_path)
            
        Returns:
            True if successful, False otherwise
        """
        path = data_path or self.data_path
        if not path:
            logger.warning("[WARN] No data path provided")
            return False
        
        path = Path(path)
        if not path.exists():
            logger.error(f"[ERROR] Data file not found: {path}")
            return False
        
        try:
            # Try to load as transformed format first
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # If it's test results format, transform it
            if isinstance(data, dict) and 'legislation_id' in data:
                self.profiles = self.transformer.transform_from_test_results(path)
            elif isinstance(data, list) and len(data) > 0 and 'legislation_id' in data[0]:
                self.profiles = self.transformer.transform_from_test_results(path)
            else:
                # Assume it's already in CompanyRiskProfile format
                self.profiles = self._load_profiles_from_dict(data)
            
            logger.info(f"[OK] Loaded {len(self.profiles)} company profiles")
            return True
            
        except Exception as e:
            logger.error(f"[ERROR] Failed to load data: {e}")
            st.error(f"Failed to load data: {e}")
            return False
    
    def _load_profiles_from_dict(self, data: List[Dict[str, Any]]) -> List[CompanyRiskProfile]:
        """Load profiles from dict format."""
        profiles = []
        for item in data:
            legislations = [
                LegislationContribution(
                    legislation_name=leg.get('legislation_name', 'Unknown'),
                    contribution_percent=leg.get('contribution_percent', 0.0),
                    top_sentences=[
                        SentenceContribution(
                            sentence=sent.get('sentence', ''),
                            similarity_score=sent.get('similarity_score', 0.0),
                            section_title=sent.get('section_title'),
                            section_type=sent.get('section_type'),
                            filing_date=sent.get('filing_date')
                        )
                        for sent in leg.get('top_sentences', [])
                    ],
                    impact_score=leg.get('impact_score'),
                    risk_level=leg.get('risk_level')
                )
                for leg in item.get('legislations', [])
            ]
            
            profile = CompanyRiskProfile(
                company_name=item.get('company_name', 'Unknown'),
                ticker=item.get('ticker', 'UNKNOWN'),
                risk_score=item.get('risk_score', 0.0),
                risk_level=item.get('risk_level'),
                legislations=legislations
            )
            profiles.append(profile)
        
        return profiles
    
    def render(self) -> None:
        """Render the complete risk factors dashboard."""
        st.title("Regulatory Risk Dashboard")
        st.markdown("Analyze the impact of proposed or existing legislation on company filings.")
        
        if not self.profiles:
            st.warning("No risk data loaded. Please provide a data file.")
            return
        
        # Sidebar filters
        with st.sidebar:
            st.header("Filters")
            
            # Legislation filter
            all_legislations = set()
            for profile in self.profiles:
                for leg in profile.legislations:
                    all_legislations.add(leg.legislation_name)
            
            legislation_options = ["All"] + sorted(all_legislations)
            selected_legislation = st.selectbox(
                "Select Legislation",
                legislation_options
            )
            
            # Risk score filter
            min_score = st.slider(
                "Minimum Risk Score",
                0.0,
                100.0,
                0.0,
                5.0
            )
            
            # Company search
            company_search = st.text_input(
                "Search Company",
                placeholder="Enter company name or ticker..."
            )
            
            # Sort options
            sort_by = st.selectbox(
                "Sort By",
                ["Risk Score (High to Low)", "Risk Score (Low to High)", "Company Name"]
            )
        
        # Filter and sort profiles
        filtered_profiles = self._filter_profiles(
            selected_legislation,
            min_score,
            company_search
        )
        
        sorted_profiles = self._sort_profiles(filtered_profiles, sort_by)
        
        # Display stats
        self._render_stats(sorted_profiles)
        
        st.divider()
        
        # Display each company
        for profile in sorted_profiles:
            self._render_company_profile(profile, selected_legislation)
        
        # Export button
        st.divider()
        self._render_export_button(sorted_profiles)
    
    def _filter_profiles(
        self,
        selected_legislation: str,
        min_score: float,
        company_search: str
    ) -> List[CompanyRiskProfile]:
        """Filter profiles based on sidebar criteria."""
        filtered = []
        
        for profile in self.profiles:
            # Risk score filter
            if profile.risk_score < min_score:
                continue
            
            # Company search filter
            if company_search:
                search_lower = company_search.lower()
                if (search_lower not in profile.company_name.lower() and
                    search_lower not in profile.ticker.lower()):
                    continue
            
            # Legislation filter
            if selected_legislation != "All":
                has_legislation = any(
                    leg.legislation_name == selected_legislation
                    for leg in profile.legislations
                )
                if not has_legislation:
                    continue
            
            filtered.append(profile)
        
        return filtered
    
    def _sort_profiles(
        self,
        profiles: List[CompanyRiskProfile],
        sort_by: str
    ) -> List[CompanyRiskProfile]:
        """Sort profiles according to sort option."""
        if sort_by == "Risk Score (High to Low)":
            return sorted(profiles, key=lambda x: x.risk_score, reverse=True)
        elif sort_by == "Risk Score (Low to High)":
            return sorted(profiles, key=lambda x: x.risk_score)
        else:  # Company Name
            return sorted(profiles, key=lambda x: x.company_name)
    
    def _render_stats(self, profiles: List[CompanyRiskProfile]) -> None:
        """Render statistics cards."""
        if not profiles:
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Companies", len(profiles))
        
        with col2:
            avg_risk = sum(p.risk_score for p in profiles) / len(profiles)
            st.metric("Average Risk Score", f"{avg_risk:.1f}")
        
        with col3:
            high_risk = len([p for p in profiles if p.risk_score >= 70])
            st.metric("High Risk Companies", high_risk)
        
        with col4:
            total_legislations = sum(len(p.legislations) for p in profiles)
            st.metric("Active Legislations", total_legislations)
    
    def _render_company_profile(
        self,
        profile: CompanyRiskProfile,
        selected_legislation: str
    ) -> None:
        """Render a single company's risk profile."""
        # Color code risk level
        if profile.risk_score >= 70:
            color = "🔴"
            risk_color = "#ff4444"
        elif profile.risk_score >= 40:
            color = "🟡"
            risk_color = "#ffaa00"
        else:
            color = "🟢"
            risk_color = "#44aa44"
        
        # Expandable company section
        with st.expander(
            f"**{profile.company_name}** ({profile.ticker}) — "
            f"Risk Score: {profile.risk_score:.1f}",
            expanded=False
        ):
            # Risk score visualization
            st.markdown(
                f"""
                <div style="background-color: {risk_color}20; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem;">
                    <h3 style="color: {risk_color}; margin: 0;">
                        {color} Risk Level: {profile.risk_level.upper()}
                    </h3>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Display each legislation contribution
            for legislation in profile.legislations:
                # Skip if filtering by specific legislation
                if selected_legislation != "All" and legislation.legislation_name != selected_legislation:
                    continue
                
                st.markdown(f"### {legislation.legislation_name}")
                st.markdown(
                    f"**Contribution:** {legislation.contribution_percent:.1f}% of risk | "
                    f"Impact Score: {legislation.impact_score:.3f} | "
                    f"Risk Level: {legislation.risk_level}"
                )
                
                # Display top sentences
                st.markdown("**Top Contributing Sentences:**")
                for i, sentence in enumerate(legislation.top_sentences[:10], 1):
                    # Color code similarity score
                    similarity_color = self._get_similarity_color(sentence.similarity_score)
                    
                    st.markdown(
                        f"""
                        <div style="margin: 0.5rem 0; padding: 0.75rem; background-color: #f5f5f5; border-left: 3px solid {similarity_color};">
                            <strong style="color: {similarity_color};">{sentence.similarity_score:.3f}</strong> → 
                            {sentence.sentence[:300]}
                            {('...' if len(sentence.sentence) > 300 else '')}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    
                    # Show metadata if available
                    if sentence.section_title:
                        st.caption(f"Section: {sentence.section_title}")
                    
                    if i < len(legislation.top_sentences[:10]):
                        st.markdown("---")
                
                if legislation != profile.legislations[-1]:
                    st.divider()
    
    def _get_similarity_color(self, score: float) -> str:
        """Get color based on similarity score."""
        if score >= 0.8:
            return "#ff4444"  # Red - high similarity
        elif score >= 0.6:
            return "#ffaa00"  # Orange - medium-high
        elif score >= 0.4:
            return "#ffdd00"  # Yellow - medium
        else:
            return "#44aa44"  # Green - low
    
    def _render_export_button(self, profiles: List[CompanyRiskProfile]) -> None:
        """Render export to CSV/JSON buttons."""
        col1, col2 = st.columns(2)
        
        with col1:
            # Export as JSON
            json_data = []
            for profile in profiles:
                json_data.append({
                    'company_name': profile.company_name,
                    'ticker': profile.ticker,
                    'risk_score': profile.risk_score,
                    'risk_level': profile.risk_level,
                    'legislations': [
                        {
                            'legislation_name': leg.legislation_name,
                            'contribution_percent': leg.contribution_percent,
                            'impact_score': leg.impact_score,
                            'risk_level': leg.risk_level,
                            'top_sentences_count': len(leg.top_sentences)
                        }
                        for leg in profile.legislations
                    ]
                })
            
            json_str = json.dumps(json_data, indent=2)
            st.download_button(
                label="Download as JSON",
                data=json_str,
                file_name="risk_data.json",
                mime="application/json"
            )
        
        with col2:
            # Export as CSV (simplified)
            import pandas as pd
            
            csv_data = []
            for profile in profiles:
                for leg in profile.legislations:
                    csv_data.append({
                        'Company': profile.company_name,
                        'Ticker': profile.ticker,
                        'Risk Score': profile.risk_score,
                        'Risk Level': profile.risk_level,
                        'Legislation': leg.legislation_name,
                        'Contribution %': leg.contribution_percent,
                        'Impact Score': leg.impact_score
                    })
            
            if csv_data:
                df = pd.DataFrame(csv_data)
                csv_str = df.to_csv(index=False)
                st.download_button(
                    label="Download as CSV",
                    data=csv_str,
                    file_name="risk_data.csv",
                    mime="text/csv"
                )

