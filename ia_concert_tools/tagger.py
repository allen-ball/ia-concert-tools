"""
ID3 tag management for MP3 files.

Updates tags based on metadata from XML files and tracklists.
"""

from pathlib import Path
from typing import Dict, Optional

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger

logger = get_logger("tagger")


class Tagger:
    """Update ID3 tags on concert recordings."""
    
    def __init__(self, creator: str, genre: Optional[str] = None):
        """
        Initialize tagger.
        
        Args:
            creator: Artist/creator name
            genre: Override default genre
        """
        self.creator = creator
        self.genre = genre or Config.DEFAULT_GENRE
        self.base_dir = Path(creator)
    
    def update_tags(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Update ID3 tags on all MP3 files.
        
        Args:
            dry_run: Show what would change without modifying
            
        Returns:
            Dictionary with update statistics
        """
        # TODO: Implement in next phase
        raise NotImplementedError("Tagger not yet implemented")
