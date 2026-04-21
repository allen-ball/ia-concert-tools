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
    
    def get_track_titles(self) -> Dict[str, str]:
        """
        Parse track titles from *_files.xml.
        
        Returns:
            Dictionary mapping filename -> track title
        """
        track_titles = {}
        
        for xml_file in self.concert_dir.glob("*_files.xml"):
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                current_file = None
                current_title = None
                
                # Iterate through all elements
                for element in root.iter():
                    # Check for file element with MP3 name attribute
                    if element.tag == "file":
                        name = element.get("name", "")
                        if name.endswith(".mp3"):
                            current_file = name
                            current_title = None
                    
                    # Check for title element
                    elif element.tag == "title" and current_file:
                        if element.text:
                            current_title = element.text.strip()
                            # Decode HTML entities
                            current_title = Config.decode_html_entities(current_title)
                            track_titles[current_file] = current_title
                            current_file = None
                            current_title = None
                
                logger.debug(f"Parsed {len(track_titles)} track titles from {xml_file.name}")
                
            except ET.ParseError as e:
                logger.debug(f"Failed to parse {xml_file}: {e}")
                continue
        
        return track_titles
    
    def get_all_metadata(self) -> Dict[str, Optional[str]]:
        """
        Get all available metadata from XML files.
        
        Returns:
            Dictionary with artist, album, year, identifier
        """
        return {
            "artist": self.get_artist(),
            "album": self.get_album(),
            "year": self.get_year(),
            "identifier": self.get_identifier(),
        }
