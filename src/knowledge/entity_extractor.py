"""
Entity extraction module (placeholder for future implementation).
"""

import logging

logger = logging.getLogger(__name__)


class EntityExtractor:
    """
    Extract entities and relationships from documents.
    
    Future implementation will use spaCy NER + custom financial entities.
    """
    
    def __init__(self):
        """Initialize entity extractor."""
        logger.info("[INFO] EntityExtractor initialized (placeholder)")
    
    def extract_entities(self, text: str) -> list:
        """
        Extract entities from text.
        
        Args:
            text: Input text
            
        Returns:
            List of entities (empty for now)
        """
        # Placeholder
        return []
    
    def extract_relationships(self, text: str) -> list:
        """
        Extract relationships between entities.
        
        Args:
            text: Input text
            
        Returns:
            List of relationships (empty for now)
        """
        # Placeholder
        return []

