"""
Download concerts from Internet Archive.

Handles downloading MP3s, metadata, and tracklists with deduplication.
"""

from pathlib import Path
from typing import Dict, List, Optional

import internetarchive as ia

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger
from ia_concert_tools.metadata import MetadataBuilder
from ia_concert_tools.utils.validation import match_date_filter

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
        self.metadata_builder = MetadataBuilder(creator)
    
    def download(self, date_filters: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Download concerts.
        
        Args:
            date_filters: Optional date filters (prefix matching)
            
        Returns:
            Dictionary with download statistics
        """
        stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        if self.use_cache:
            # Build/refresh cache if needed
            if not self.metadata_builder.is_cache_fresh():
                logger.info("Metadata cache is stale or missing, building...")
                # Pass date filters for optimization
                self.metadata_builder.build_cache(date_filters=date_filters)
            else:
                logger.info("Using existing metadata cache")
            
            # Load cache
            cache_data = self.metadata_builder.load_cache()
            if not cache_data:
                logger.error("Failed to load metadata cache")
                return stats
            
            recordings_by_date = cache_data.get("recordings", {})
        else:
            logger.warning("Cache disabled - downloading all recordings (no deduplication)")
            # Implement non-cached download if needed
            logger.error("Non-cached download not yet implemented")
            return stats
        
        # Filter dates if requested
        dates_to_download = list(recordings_by_date.keys())
        if date_filters:
            dates_to_download = [
                date for date in dates_to_download
                if match_date_filter(date, date_filters)
            ]
            logger.info(f"Filtering by dates: {', '.join(date_filters)}")
        
        total_dates = len(dates_to_download)
        
        if total_dates == 0:
            logger.warning("No recordings found matching filters")
            return stats
        
        logger.info(f"Found {total_dates} unique dates with recordings")
        
        # Download each date
        for idx, date in enumerate(dates_to_download, 1):
            logger.info(f"[{idx}/{total_dates}] Date: {date}")
            
            recordings = recordings_by_date[date]
            if not recordings:
                logger.warning(f"  No recordings found for {date}")
                continue
            
            # Select best recording (first in sorted list)
            best = recordings[0]
            identifier = best["identifier"]
            score = best["score"]
            mp3_count = best["mp3_count"]
            
            # Show selection info
            if len(recordings) > 1:
                logger.info(f"  ℹ Selected best of {len(recordings)} recordings "
                          f"(score: {score}, {mp3_count} tracks)")
            else:
                logger.info(f"  ℹ Only recording available ({mp3_count} tracks)")
            
            # Create directory
            concert_dir = self.base_dir / Config.CONCERT_DIR_FORMAT.format(date=date)
            
            # Check if already downloaded
            if concert_dir.exists() and any(concert_dir.glob("*.mp3")):
                logger.info(f"  ✓ Already downloaded: {concert_dir.name}")
                stats["skipped"] += 1
                continue
            
            # Download
            logger.info(f"  → Downloading: {identifier}")
            
            try:
                concert_dir.mkdir(parents=True, exist_ok=True)
                
                # Download using internetarchive library
                item = ia.get_item(identifier)
                
                # Download files matching our patterns
                download_count = 0
                for pattern in Config.DOWNLOAD_GLOB_PATTERNS:
                    files = item.get_files(glob_pattern=pattern)
                    for file in files:
                        file_path = concert_dir / file.name
                        if not file_path.exists():
                            logger.debug(f"    Downloading: {file.name}")
                            file.download(file_path=str(file_path))
                            download_count += 1
                
                logger.info(f"  ✓ Downloaded: {concert_dir.name} ({download_count} files)")
                stats["downloaded"] += 1
                
            except Exception as e:
                logger.error(f"  ✗ Failed to download {identifier}: {e}")
                stats["failed"] += 1
        
        return stats
