"""
XML metadata parser for Internet Archive files.

Parses *_meta.xml (artist, album, year, identifier) and 
*_files.xml (track titles with HTML entity decoding).
"""

import re
from pathlib import Path
from typing import Dict, Optional, List
import xml.etree.ElementTree as ET

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger

logger = get_logger("xml_parser")


class XmlParser:
    """Parse Internet Archive XML metadata files."""
    
    def __init__(self, concert_dir: Path):
        """
        Initialize XML parser.
        
        Args:
            concert_dir: Directory containing concert files
        """
        self.concert_dir = Path(concert_dir)
    
    @staticmethod
    def clean_track_title(title: str) -> str:
        """
        Remove track number prefix from title if present.
        
        Some Internet Archive metadata includes track numbers in titles like:
        - "01 - Intro"
        - "02 - Song Name"
        - "03. Another Song"
        
        Args:
            title: Raw title from XML
            
        Returns:
            Cleaned title without track number prefix
        """
        # Pattern: leading digits, optional period/dash/space, then title
        # Match: "01 - Title", "01- Title", "01 Title", "01. Title"
        cleaned = re.sub(r'^(\d{1,2})\s*[\-\.\s]+\s*', '', title)
        return cleaned.strip()
    
    def extract_meta_tag(self, tag_name: str) -> Optional[str]:
        """
        Extract a tag value from *_meta.xml file.
        
        Args:
            tag_name: XML tag name to extract
            
        Returns:
            Tag value or None if not found
        """
        for xml_file in self.concert_dir.glob("*_meta.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # Find the tag (case-insensitive search)
                for element in root.iter():
                    if element.tag.lower() == tag_name.lower():
                        text = element.text
                        if text:
                            # Decode HTML entities
                            return Config.decode_html_entities(text.strip())
                
            except ET.ParseError as e:
                logger.debug(f"Failed to parse {xml_file}: {e}")
                continue
        
        return None
    
    def get_artist(self) -> Optional[str]:
        """
        Get artist/creator from metadata.
        
        Returns:
            Artist name or None
        """
        return self.extract_meta_tag("creator")
    
    def get_album(self) -> Optional[str]:
        """
        Get album title from metadata.
        
        Returns:
            Album title or None
        """
        return self.extract_meta_tag("title")
    
    def get_year(self) -> Optional[str]:
        """
        Get year from metadata.
        
        Returns:
            Year string or None
        """
        return self.extract_meta_tag("year")
    
    def get_identifier(self) -> Optional[str]:
        """
        Get Internet Archive identifier from metadata.
        
        Returns:
            Identifier or None
        """
        return self.extract_meta_tag("identifier")
    
    def get_venue(self) -> Optional[str]:
        """
        Get venue from metadata.
        
        Returns:
            Venue name or None
        """
        return self.extract_meta_tag("venue")
    
    def get_coverage(self) -> Optional[str]:
        """
        Get coverage (location) from metadata.
        
        Returns:
            Coverage string (e.g., "Hollywood, CA") or None
        """
        return self.extract_meta_tag("coverage")
    
    def get_date(self) -> Optional[str]:
        """
        Get date from metadata.
        
        Returns:
            Date string (e.g., "1971-08-06") or None
        """
        return self.extract_meta_tag("date")
    
    def get_track_titles(self) -> Dict[str, str]:
        """
        Parse track titles from *_files.xml.
        
        For MP3 files that are derivatives of FLAC files, the title metadata
        is on the FLAC file, not the MP3. We need to:
        1. Build a map of FLAC filename -> title
        2. Find MP3 files and their corresponding FLAC originals
        3. Map the title from FLAC to MP3
        
        Returns:
            Dictionary mapping MP3 filename -> track title
        """
        track_titles = {}
        
        for xml_file in self.concert_dir.glob("*_files.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                # First pass: Build map of source filename -> title
                # (FLAC files have the title metadata)
                source_titles = {}
                for file_elem in root.findall('.//file'):
                    filename = file_elem.get('name', '')
                    title_elem = file_elem.find('title')
                    
                    if title_elem is not None and title_elem.text:
                        title = title_elem.text.strip()
                        title = Config.decode_html_entities(title)
                        title = XmlParser.clean_track_title(title)
                        source_titles[filename] = title
                
                # Second pass: Map MP3 files to their original source titles
                for file_elem in root.findall('.//file'):
                    filename = file_elem.get('name', '')
                    
                    if filename.endswith('.mp3'):
                        # Check if this MP3 has a title directly
                        title_elem = file_elem.find('title')
                        if title_elem is not None and title_elem.text:
                            title = title_elem.text.strip()
                            title = Config.decode_html_entities(title)
                            title = XmlParser.clean_track_title(title)
                            track_titles[filename] = title
                        else:
                            # Look for <original> tag pointing to source file
                            original_elem = file_elem.find('original')
                            if original_elem is not None and original_elem.text:
                                original_file = original_elem.text.strip()
                                if original_file in source_titles:
                                    track_titles[filename] = source_titles[original_file]
                
                logger.debug(f"Parsed {len(track_titles)} track titles from {xml_file.name}")
                
            except ET.ParseError as e:
                logger.debug(f"Failed to parse {xml_file}: {e}")
                continue
        
        return track_titles
    
    def get_all_metadata(self) -> Dict[str, Optional[str]]:
        """
        Get all available metadata from XML files.
        
        Returns:
            Dictionary with artist, album, year, identifier, venue, coverage, date
        """
        return {
            "artist": self.get_artist(),
            "album": self.get_album(),
            "year": self.get_year(),
            "identifier": self.get_identifier(),
            "venue": self.get_venue(),
            "coverage": self.get_coverage(),
            "date": self.get_date(),
        }
