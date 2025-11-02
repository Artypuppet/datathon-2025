"""
AWS Lambda handler for S3-triggered processing.
"""

import json
import logging
from typing import Any, Dict

from ..pipeline import PipelineOrchestrator, PipelineConfig

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda handler for S3 upload events.
    
    Event structure:
    {
        "Records": [
            {
                "s3": {
                    "bucket": {"name": "bucket-name"},
                    "object": {"key": "path/to/file.html"}
                }
            }
        ]
    }
    
    Returns:
        Response dictionary with status
    """
    logger.info("Lambda invoked")
    logger.info(f"Event: {json.dumps(event)}")
    
    try:
        # Handle S3 event
        if 'Records' in event and len(event['Records']) > 0:
            record = event['Records'][0]
            s3_info = record.get('s3', {})
            
            bucket_name = s3_info.get('bucket', {}).get('name')
            file_key = s3_info.get('object', {}).get('key')
            
            # URL decode the key (S3 keys are URL encoded)
            from urllib.parse import unquote
            file_key = unquote(file_key)
            
            logger.info(f"Processing: s3://{bucket_name}/{file_key}")
            
            # Create event for pipeline
            pipeline_event = {
                'file_key': file_key,
                'timestamp': record.get('eventTime'),
                'source_bucket': bucket_name
            }
            
        else:
            # Direct invocation (e.g., from Streamlit)
            pipeline_event = event
            
            if 'file_key' not in pipeline_event:
                return {
                    'statusCode': 400,
                    'body': json.dumps({
                        'status': 'error',
                        'error': 'file_key is required'
                    })
                }
        
        # Check for dry_run flag
        dry_run = pipeline_event.get('dry_run', False)
        
        # Create pipeline config
        config = PipelineConfig(
            dry_run=dry_run,
            skip_embeddings=True  # MVP: skip embeddings
        )
        
        # Execute pipeline
        orchestrator = PipelineOrchestrator(config=config)
        result = orchestrator.execute(pipeline_event)
        
        # Return Lambda response
        if result['status'] in ['success', 'dry_run']:
            return {
                'statusCode': 200,
                'body': json.dumps(result)
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps(result)
            }
    
    except Exception as e:
        logger.error(f"Lambda error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'error': str(e)
            })
        }

