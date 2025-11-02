"""
Streamlit file upload widget with S3 integration.
"""

import streamlit as st
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from datetime import datetime

from ..utils import get_s3_client, S3Client
from ..pipeline import PipelineOrchestrator, PipelineConfig
from ..parsers.base import DocumentType

logger = logging.getLogger(__name__)


class FileUploadWidget:
    """Widget for uploading files to S3 and triggering pipeline."""
    
    def __init__(self, s3_client: Optional[S3Client] = None):
        """
        Initialize upload widget.
        
        Args:
            s3_client: S3 client instance (optional)
        """
        self.s3_client = s3_client or get_s3_client()
    
    def render(
        self,
        accept_types: list = ["csv", "html", "xml"],
        max_file_size: int = 100  # MB
    ) -> Dict[str, Any]:
        """
        Render the upload widget.
        
        Args:
            accept_types: Accepted file types
            max_file_size: Maximum file size in MB
            
        Returns:
            Dictionary with upload status and metadata
        """
        st.subheader("Upload Document")
        
        # Initialize session state
        if 'upload_success' not in st.session_state:
            st.session_state['upload_success'] = False
        if 'last_uploaded_file_id' not in st.session_state:
            st.session_state['last_uploaded_file_id'] = None
        if 'last_result' not in st.session_state:
            st.session_state['last_result'] = None
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a file to upload",
            type=accept_types,
            help=f"Supported formats: {', '.join(accept_types)}",
            key="file_uploader"
        )
        
        # Check if file changed
        if uploaded_file:
            current_file_id = uploaded_file.file_id
            # If this is a different file than what was last successfully uploaded, reset state
            if current_file_id != st.session_state.get('last_uploaded_file_id'):
                st.session_state['upload_success'] = False
                st.session_state['last_result'] = None
        
        if uploaded_file and not st.session_state['upload_success']:
            # Display file info
            file_bytes = uploaded_file.read()
            uploaded_file.seek(0)  # Reset file pointer
            file_size_mb = len(file_bytes) / (1024 * 1024)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("File Name", uploaded_file.name)
            with col2:
                st.metric("File Size", f"{file_size_mb:.2f} MB")
            with col3:
                st.metric("File Type", Path(uploaded_file.name).suffix[1:])
            
            # Check file size
            if file_size_mb > max_file_size:
                st.error(f"File size exceeds maximum of {max_file_size} MB")
                return {'status': 'error', 'error': 'file_too_large'}
            
            # Processing options
            st.divider()
            st.write("**Processing Options**")
            
            # Document type selector
            st.write("**Document Type**")
            document_type_selection = st.selectbox(
                "Select document type",
                options=[
                    "Auto-detect",
                    "Stock Data (CSV)",
                    "Company Filing (10-K/10-Q)",
                    "Legislation (Regulation/Law)"
                ],
                index=0,
                help="Select the type of document being uploaded. Auto-detect will try to infer from filename.",
                key="doc_type_selector"
            )
            
            col1, col2 = st.columns(2)
            with col1:
                dry_run = st.checkbox(
                    "Test Mode (Dry Run)",
                    help="Process file but don't update embeddings",
                    key="dry_run_checkbox"
                )
            
            with col2:
                auto_process = st.checkbox(
                    "Auto-process after upload",
                    value=True,
                    help="Automatically trigger pipeline after upload",
                    key="auto_process_checkbox"
                )
            
            # Upload button (only show if file is uploaded and not already successful)
            if st.button("Upload", type="primary", use_container_width=True, key="upload_btn", ):
                result = self._handle_upload(file_bytes, uploaded_file.name, dry_run, auto_process, document_type_selection)
                
                # Mark success if upload/processing worked
                if result.get('status') in ['success', 'uploaded', 'dry_run']:
                    st.session_state['upload_success'] = True
                    st.session_state['last_uploaded_file_id'] = uploaded_file.file_id
                    st.session_state['last_result'] = result
                    st.rerun()        
        
                return result
        
        elif uploaded_file and st.session_state['upload_success'] and st.session_state.get('last_result'):
            # Show success state with results
            result = st.session_state['last_result']
            
            # Display appropriate message based on status
            if result.get('status') == 'success':
                st.success(result.get('message', 'Processing complete!'))
            elif result.get('status') == 'dry_run':
                st.info(result.get('message', 'Dry run complete (no changes made)'))
            elif result.get('status') == 'uploaded':
                st.success(result.get('message', 'File uploaded!'))
            else:
                st.error(result.get('error_message', result.get('message', 'Processing completed with issues')))
            
            # Show result details
            self._display_result(result)
            st.info("Select a new file to upload another.")
        
        return {'status': 'no_file'}
    
    def _handle_upload(
        self,
        file_bytes: bytes,
        file_name: str,
        dry_run: bool = False,
        auto_process: bool = True,
        document_type_selection: str = "Auto-detect"
    ) -> Dict[str, Any]:
        """
        Handle file upload to S3.
        
        Args:
            file_bytes: File content as bytes
            file_name: Original filename
            dry_run: Whether to run in dry run mode
            auto_process: Whether to auto-trigger pipeline
            document_type_selection: User-selected document type
            
        Returns:
            Upload result dictionary
        """
        if not self.s3_client:
            st.error("S3 not configured. Please set up AWS credentials.")
            return {'status': 'error', 'error': 's3_not_configured'}
        
        # Generate S3 key with timestamp (always unique, handles duplicates)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        s3_key = f"input/user_uploads/{timestamp}_{file_name}"
        
        # Upload to S3 directly from memory (no temp file needed)
        with st.spinner("Uploading..."):
            success = self.s3_client.write_content(file_bytes, s3_key)
        
        if not success:
            return {'status': 'error', 'error': 'upload_failed', 'error_message': 'Failed to upload file to S3'}
        
        # Auto-process if requested
        if auto_process:
            return self._trigger_pipeline(s3_key, dry_run, document_type_selection)
        else:
            return {
                'status': 'uploaded',
                'file_key': s3_key,
                'processed': False,
                'message': 'File uploaded. Pipeline not triggered.'
            }
    
    def _trigger_pipeline(
        self,
        file_key: str,
        dry_run: bool = False,
        document_type_selection: str = "Auto-detect"
    ) -> Dict[str, Any]:
        """
        Trigger processing pipeline.
        
        Args:
            file_key: S3 key of uploaded file
            dry_run: Whether to run in dry run mode
            document_type_selection: User-selected document type
            
        Returns:
            Pipeline result dictionary
        """
        # Create pipeline config
        config = PipelineConfig(
            dry_run=dry_run,
            skip_embeddings=True  # MVP: skip embeddings
        )
        
        # Create orchestrator
        orchestrator = PipelineOrchestrator(config=config)
        
        # Map user selection to DocumentType if not auto-detect
        document_type_name = None
        if document_type_selection != "Auto-detect":
            # Map UI selection to DocumentType
            selection_map = {
                "Stock Data (CSV)": "CSV_FINANCIAL",
                "Company Filing (10-K/10-Q)": "HTML_FILING",
                "Legislation (Regulation/Law)": "HTML_LEGISLATION"
            }
            document_type_name = selection_map.get(document_type_selection)
        
        # Build event
        event = {
            'file_key': file_key,
            'timestamp': datetime.now().isoformat(),
            'dry_run': dry_run
        }
        
        # Add document_type if explicitly selected
        if document_type_name:
            event['document_type'] = document_type_name
        
        # Execute pipeline
        with st.spinner("Processing file..."):
            result = orchestrator.execute(event)
        
        # Add message to result based on status
        if result['status'] == 'success':
            result['message'] = 'Processing complete!'
        elif result['status'] == 'dry_run':
            result['message'] = 'Dry run complete (no changes made)'
        else:
            result['message'] = f"Processing failed: {result.get('error', 'Unknown error')}"
        
        return result
    
    def _display_result(self, result: Dict[str, Any]):
        """Display pipeline result details."""
        with st.expander("📊 Processing Details"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**File:**")
                st.code(result.get('file_key', 'N/A'))
                
                if 'parsed_key' in result:
                    st.write("**Output:**")
                    st.code(result['parsed_key'])
            
            with col2:
                st.write("**Document Type:**")
                doc_type = result.get('document_type', 'Unknown')
                st.write(f":blue[{doc_type}]")
                
                st.write("**Status:**")
                status = result['status']
                if status == 'success':
                    st.success("✓ Success")
                elif status == 'dry_run':
                    st.info("⊘ Dry Run")
                else:
                    st.error("✗ Failed")
            
            # Stage details
            if 'stages' in result:
                st.write("**Stage Status:**")
                for stage, status in result['stages'].items():
                    if status == 'success':
                        st.write(f"✓ {stage}: {status}")
                    elif status == 'skipped':
                        st.write(f"⊘ {stage}: {status}")
                    else:
                        st.write(f"- {stage}: {status}")

