"""
Download concerts from Internet Archive.

Handles downloading MP3s, metadata, and tracklists with deduplication.
"""

from pathlib import Path
from typing import Dict, List, Optional

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger

logger = get_logger("downloader")


class Downloader:
    """Download and manage concert recordings."""
    
    def __init__(self, creator: str, use_cache: bool = True):
        """
        Initialize downloader.
        
        Args:
            creator: Artist/creator name
            use_cache: Use metadata cache for deduplication
        """
        self.creator = creator
        self.use_cache = use_cache
        self.base_dir = Path(creator)
    
    def download(self, date_filters: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Download concerts.
        
        Args:
            date_filters: Optional date filters
            
        Returns:
            Dictionary with download statistics
        """
        # TODO: Implement in next phase
        raise NotImplementedError("Downloader not yet implemented")
