"""
Tracklist parser for text files.

Parses track listings from various text formats, handling disc/set markers,
different numbering patterns, and character encoding.
"""

import re
from pathlib import Path
from typing import List, Dict, Tuple, Optional

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger
from ia_concert_tools.utils.encoding import read_lines_with_encoding

logger = get_logger("tracklist_parser")


class TracklistParser:
    """Parse tracklists from text files."""
    
    def __init__(self, txt_file: Path):
        """
        Initialize tracklist parser.
        
        Args:
            txt_file: Path to text file
        """
        self.txt_file = Path(txt_file)
        self.tracks: List[Tuple[int, str]] = []  # (track_num, track_name)
        self.disc_tracks: Dict[int, List[Tuple[int, str]]] = {}  # disc -> [(track, name)]
    
    @staticmethod
    def normalize_track_name(name: str) -> str:
        """
        Normalize track name.
        
        Removes duration prefixes, trims whitespace, removes special chars.
        
        Args:
            name: Raw track name
            
        Returns:
            Normalized track name
        """
        # Remove duration prefix like [09:23] or [1:23:45]
        name = re.sub(Config.DURATION_PREFIX_PATTERN, "", name)
        
        # Canonicalize whitespace
        name = re.sub(r"\s+", " ", name)
        
        # Trim leading/trailing whitespace and hyphens
        name = name.strip().strip("-").strip()
        
        # Remove trailing commas
        name = name.rstrip(",")
        
        return name
    
    @staticmethod
    def parse_track_line(line: str) -> Optional[Tuple[int, str]]:
        """
        Parse a single line for track number and name.
        
        Args:
            line: Line from text file
            
        Returns:
            Tuple of (track_num, track_name) or None
        """
        # Try each track number pattern
        for pattern in Config.TRACK_NUMBER_PATTERNS:
            match = re.match(pattern, line)
            if match:
                track_num = int(match.group(1))
                track_name = match.group(2)
                
                # Normalize track name
                track_name = TracklistParser.normalize_track_name(track_name)
                
                if track_name:  # Only return if we got a name
                    return (track_num, track_name)
        
        return None
    
    def parse(self) -> Dict[int, str]:
        """
        Parse the text file and extract track listings.
        
        Returns:
            Dictionary mapping track_num -> track_name
        """
        if not self.txt_file.exists():
            logger.warning(f"Text file not found: {self.txt_file}")
            return {}
        
        try:
            lines = read_lines_with_encoding(self.txt_file)
        except Exception as e:
            logger.error(f"Failed to read {self.txt_file}: {e}")
            return {}
        
        tracks = {}
        current_disc = 1
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
            
            # Check for disc/set markers
            disc_match = None
            for pattern in Config.DISC_MARKER_PATTERNS:
                disc_match = re.match(pattern, line)
                if disc_match:
                    current_disc = int(disc_match.group(1))
                    logger.debug(f"Found disc/set marker: disc {current_disc}")
                    break
            
            if disc_match:
                continue
            
            # Try to parse as track line
            parsed = self.parse_track_line(line)
            if parsed:
                track_num, track_name = parsed
                
                # Store with disc information
                if current_disc not in self.disc_tracks:
                    self.disc_tracks[current_disc] = []
                self.disc_tracks[current_disc].append((track_num, track_name))
                
                logger.debug(f"Disc {current_disc}, Track {track_num}: {track_name}")
        
        # Calculate global track numbers (cumulative across discs)
        global_track_num = 0
        for disc_num in sorted(self.disc_tracks.keys()):
            for track_num, track_name in self.disc_tracks[disc_num]:
                global_track_num += 1
                tracks[global_track_num] = track_name
        
        logger.info(f"Parsed {len(tracks)} tracks from {self.txt_file.name}")
        return tracks
    
    def parse_with_disc_info(self) -> Tuple[Dict[int, str], int]:
        """
        Parse and return track info with disc count.
        
        Returns:
            Tuple of (tracks_dict, total_discs)
        """
        tracks = self.parse()
        total_discs = len(self.disc_tracks) if self.disc_tracks else 1
        return tracks, total_discs
    
    @staticmethod
    def parse_comma_separated_setlist(txt_file: Path) -> List[str]:
        """
        Parse comma-separated setlists (e.g., "Set 1: Song1, Song2, Song3").
        
        Args:
            txt_file: Path to text file
            
        Returns:
            List of track names
        """
        if not txt_file.exists():
            return []
        
        try:
            lines = read_lines_with_encoding(txt_file)
        except Exception as e:
            logger.error(f"Failed to read {txt_file}: {e}")
            return []
        
        tracks = []
        
        for line in lines:
            line = line.strip()
            
            # Match "Set N:" or "Disc N:" or "CD N:" or "Encore:" followed by songs
            match = re.match(
                r"^\s*(Set|Disc|CD|Encore)\s*\d*:\s*(.+)$",
                line,
                re.IGNORECASE
            )
            if match:
                songs_str = match.group(2)
                
                # Split by comma
                songs = songs_str.split(",")
                for song in songs:
                    song = song.strip()
                    
                    # Remove duration and special chars
                    song = TracklistParser.normalize_track_name(song)
                    
                    if song:
                        tracks.append(song)
        
        return tracks
