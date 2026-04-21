"""
Metadata caching and scoring for Internet Archive recordings.

Fetches all recordings for a creator, scores them based on quality metrics,
and generates a YAML cache for fast deduplication.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import internetarchive as ia
import yaml

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger
from ia_concert_tools.utils import normalize_date

logger = get_logger("metadata")


class MetadataBuilder:
    """Build and manage metadata cache for a creator."""
    
    def __init__(self, creator: str):
        """
        Initialize metadata builder.
        
        Args:
            creator: Artist/creator name
        """
        self.creator = creator
        self.base_dir = Path(creator)
        self.cache_path = Config.get_metadata_path(self.base_dir)
        self.recordings_by_date: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    def is_cache_fresh(self) -> bool:
        """
        Check if cache exists and is fresh (< 7 days old).
        
        Returns:
            True if cache is fresh
        """
        if not self.cache_path.exists():
            return False
        
        # Check age
        cache_mtime = datetime.fromtimestamp(self.cache_path.stat().st_mtime)
        age = datetime.now() - cache_mtime
        
        return age < timedelta(days=Config.CACHE_EXPIRY_DAYS)
    
    def score_recording(self, metadata: Dict[str, Any]) -> int:
        """
        Score a recording based on quality metrics.
        
        Args:
            metadata: Recording metadata from Internet Archive
            
        Returns:
            Quality score (higher is better)
        """
        score = 0
        
        # Count MP3 files (highest priority - 1000 points each)
        files = metadata.get("files", [])
        mp3_count = sum(1 for f in files 
                       if f.get("format") in ["VBR MP3", "MP3", "mp3"])
        score += mp3_count * Config.SCORE_MP3_COUNT_MULTIPLIER
        
        # Source quality
        source = metadata.get("metadata", {}).get("source", "").lower()
        if any(kw in source for kw in Config.SOUNDBOARD_KEYWORDS):
            score += Config.SCORE_SOUNDBOARD
        elif any(kw in source for kw in Config.MATRIX_KEYWORDS):
            score += Config.SCORE_MATRIX
        
        # Quality microphones
        if any(kw in source for kw in Config.QUALITY_MIC_KEYWORDS):
            score += Config.SCORE_QUALITY_MICS
        
        # Lineage quality (high-res indicators)
        lineage = metadata.get("metadata", {}).get("lineage", "").lower()
        if any(kw in lineage for kw in Config.HIGH_RES_KEYWORDS):
            score += Config.SCORE_HIGH_RES
        
        # Community rating
        avg_rating = metadata.get("metadata", {}).get("avg_rating")
        if avg_rating:
            try:
                rating_score = int(float(avg_rating) * Config.SCORE_RATING_MULTIPLIER)
                score += rating_score
            except (ValueError, TypeError):
                pass
        
        # Total MP3 file size (minor contribution)
        total_size = sum(
            int(f.get("size", 0)) for f in files
            if f.get("format") in ["VBR MP3", "MP3", "mp3"]
        )
        size_mb = total_size // (1024 * 1024)
        score += size_mb // Config.SCORE_SIZE_DIVISOR
        
        return score
    
    def fetch_item_metadata(self, identifier: str) -> Optional[Dict[str, Any]]:
        """
        Fetch metadata for a single item.
        
        Args:
            identifier: Internet Archive identifier
            
        Returns:
            Metadata dictionary or None if error
        """
        try:
            item = ia.get_item(identifier)
            return item.item_metadata
        except Exception as e:
            logger.debug(f"Failed to fetch {identifier}: {e}")
            return None
    
    def build_cache(self, force: bool = False) -> Path:
        """
        Build metadata cache.
        
        Args:
            force: Force rebuild even if cache is fresh
            
        Returns:
            Path to cache file
        """
        # Check if cache is fresh
        if not force and self.is_cache_fresh():
            logger.info(f"Cache is fresh (< {Config.CACHE_EXPIRY_DAYS} days old)")
            return self.cache_path
        
        # Create base directory
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Building metadata cache for {self.creator}...")
        logger.info("This may take a few minutes for large catalogs...")
        
        # Search for all items (no date filtering)
        search_query = Config.get_ia_search_query(self.creator)
        logger.debug(f"Search query: {search_query}")
        
        # Get list of identifiers (fast, no metadata)
        search_results = ia.search_items(search_query, fields=["identifier", "date"])
        items_with_dates = [(result["identifier"], result.get("date", "unknown")) 
                           for result in search_results]
        
        total_items = len(items_with_dates)
        logger.info(f"Found {total_items} recordings")
        
        if total_items == 0:
            logger.warning("No recordings found")
            return self.cache_path
        
        # Fetch metadata in parallel with progress reporting
        logger.info("Fetching metadata in parallel...")
        processed = 0
        last_report_time = time.time()
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
            # Submit all tasks
            future_to_id = {
                executor.submit(self.fetch_item_metadata, identifier): (identifier, date)
                for identifier, date in items_with_dates
            }
            
            # Process results as they complete
            for future in as_completed(future_to_id):
                processed += 1
                
                # Progress reporting with rate info
                current_time = time.time()
                if processed % 100 == 0 or (current_time - last_report_time > 10):
                    elapsed = current_time - start_time
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (total_items - processed) / rate if rate > 0 else 0
                    logger.info(f"  Progress: [{processed}/{total_items}] "
                              f"({processed*100//total_items}%) "
                              f"- {rate:.1f} items/sec, ~{remaining/60:.1f}min remaining")
                    last_report_time = current_time
                
                metadata = future.result()
                if metadata:
                    self._process_recording(metadata)
        
        logger.info(f"Processed {processed} recordings")
        
        # Write cache
        self._write_cache()
        
        logger.info(f"✓ Cache built successfully: {self.cache_path}")
        logger.info(f"  Total recordings: {total_items}")
        logger.info(f"  Unique dates: {len(self.recordings_by_date)}")
        
        return self.cache_path
    
    def _process_recording(self, metadata: Dict[str, Any]) -> None:
        """
        Process a recording and add to date groups.
        
        Args:
            metadata: Recording metadata
        """
        identifier = metadata.get("metadata", {}).get("identifier", "")
        date_raw = metadata.get("metadata", {}).get("date", "unknown")
        
        # Normalize date from ISO timestamp to YYYY-MM-DD format
        date = normalize_date(date_raw)
        
        if not identifier or date == "unknown":
            return
        
        # Extract relevant fields
        files = metadata.get("files", [])
        mp3_count = sum(1 for f in files 
                       if f.get("format") in ["VBR MP3", "MP3", "mp3"])
        
        total_size = sum(
            int(f.get("size", 0)) for f in files
            if f.get("format") in ["VBR MP3", "MP3", "mp3"]
        )
        size_mb = total_size // (1024 * 1024)
        
        recording_data = {
            "identifier": identifier,
            "title": metadata.get("metadata", {}).get("title", ""),
            "mp3_count": mp3_count,
            "source": metadata.get("metadata", {}).get("source", ""),
            "lineage": metadata.get("metadata", {}).get("lineage", ""),
            "total_size_mb": size_mb,
            "avg_rating": metadata.get("metadata", {}).get("avg_rating"),
            "score": self.score_recording(metadata)
        }
        
        self.recordings_by_date[date].append(recording_data)
    
    def _write_cache(self) -> None:
        """Write cache to YAML file."""
        # Sort recordings within each date by score (descending)
        for date in self.recordings_by_date:
            self.recordings_by_date[date].sort(
                key=lambda x: x["score"], 
                reverse=True
            )
        
        # Build YAML structure
        cache_data = {
            "creator": self.creator,
            "last_updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "recordings": dict(sorted(self.recordings_by_date.items()))
        }
        
        # Write to file
        with open(self.cache_path, "w") as f:
            yaml.dump(cache_data, f, default_flow_style=False, sort_keys=False)
    
    def load_cache(self) -> Optional[Dict[str, Any]]:
        """
        Load cache from file.
        
        Returns:
            Cache data or None if not found
        """
        if not self.cache_path.exists():
            return None
        
        with open(self.cache_path, "r") as f:
            return yaml.safe_load(f)
