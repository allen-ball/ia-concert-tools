"""
Filename parser for extracting track information from MP3 filenames.

Handles various naming patterns including multi-disc notation,
PascalCase, underscores, and space-separated formats.
"""

import re
from pathlib import Path
from typing import Optional, Tuple

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger

logger = get_logger("filename_parser")


class FilenameParser:
    """Parse track information from MP3 filenames."""
    
    @staticmethod
    def parse_disc_track(filename: str) -> Optional[Tuple[int, int]]:
        """
        Parse disc and track numbers from filename (e.g., d2t01, s1t05).
        
        Args:
            filename: MP3 filename
            
        Returns:
            Tuple of (disc_num, track_num) or None if not found
        """
        for pattern in Config.DISC_TRACK_PATTERNS:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                disc_num = int(match.group(1))
                track_num = int(match.group(2))
                return (disc_num, track_num)
        
        return None
    
    @staticmethod
    def parse_track_number(filename: str) -> Optional[int]:
        """
        Parse track number from filename.
        
        Handles patterns like:
        - 01_Track_Name.mp3
        - 01 Track Name.mp3
        - 01TrackName.mp3
        - prefix_01.mp3
        
        Args:
            filename: MP3 filename
            
        Returns:
            Track number or None if not found
        """
        # Remove extension
        name = Path(filename).stem
        
        # Try disc-track pattern first
        disc_track = FilenameParser.parse_disc_track(name)
        if disc_track:
            return disc_track[1]  # Return track number
        
        # Pattern 1: Leading digits with separator
        match = re.match(r"^(\d{1,2})[\s_\-\.]+", name)
        if match:
            return int(match.group(1))
        
        # Pattern 2: PascalCase - digits followed immediately by capital letter
        match = re.match(r"^(\d{1,2})([A-Z])", name)
        if match:
            return int(match.group(1))
        
        # Pattern 3: Trailing digits (after underscore/hyphen)
        match = re.search(r"[\s_\-](\d{1,2})$", name)
        if match:
            return int(match.group(1))
        
        return None
    
    @staticmethod
    def parse_track_name(filename: str) -> Optional[str]:
        """
        Parse track name from filename.
        
        Args:
            filename: MP3 filename
            
        Returns:
            Track name or None if can't parse
        """
        # Remove extension
        name = Path(filename).stem
        
        # Try disc-track pattern first - if found, remove it
        disc_track = FilenameParser.parse_disc_track(name)
        if disc_track:
            # Remove disc-track pattern
            for pattern in Config.DISC_TRACK_PATTERNS:
                name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        
        # Pattern 1: Leading digits with separator
        match = re.match(r"^(\d{1,2})[\s_\-\.]+(.+)$", name)
        if match:
            track_name = match.group(2)
            # Convert underscores to spaces
            track_name = track_name.replace("_", " ")
            return track_name.strip()
        
        # Pattern 2: PascalCase - split on capital letters
        match = re.match(r"^(\d{1,2})([A-Z].+)$", name)
        if match:
            track_name = match.group(2)
            # Insert spaces before capital letters
            track_name = re.sub(r"([A-Z])", r" \1", track_name)
            return track_name.strip()
        
        # Pattern 3: Just remove leading digits
        name = re.sub(r"^(\d{1,2})[\s_\-\.]*", "", name)
        if name:
            # Convert underscores to spaces
            name = name.replace("_", " ")
            return name.strip()
        
        return None
    
    @staticmethod
    def parse(filename: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        """
        Parse all information from filename.
        
        Args:
            filename: MP3 filename
            
        Returns:
            Tuple of (disc_num or None, track_num or None, track_name or None)
        """
        disc_track = FilenameParser.parse_disc_track(filename)
        track_num = FilenameParser.parse_track_number(filename)
        track_name = FilenameParser.parse_track_name(filename)
        
        disc_num = disc_track[0] if disc_track else None
        
        return (disc_num, track_num, track_name)
