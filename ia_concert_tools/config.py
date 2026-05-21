"""
Configuration and constants for Internet Archive Concert Tools.

This module contains all configuration values, file patterns, scoring weights,
and other constants used throughout the application.
"""

from pathlib import Path
from typing import List, Dict


class Config:
    """Global configuration for Internet Archive concert tools."""
    
    # Version
    VERSION = "1.0.0"
    
    # Internet Archive search settings
    IA_MEDIATYPE = "etree"
    IA_FORMAT = "MP3"
    
    # Metadata cache settings
    METADATA_FILENAME = ".metadata.yaml"
    CACHE_EXPIRY_DAYS = 7
    
    # Download settings
    DOWNLOAD_GLOB_PATTERNS = ["*.mp3", "*.txt", "*.xml", "*.md5"]
    
    # File exclusion patterns for tracklist parsing
    EXCLUDED_TXT_FILES = [
        "md5.txt",
        "info.txt",
        "etree.txt",
        "shntool.txt",
        "fingerprint.ffp.txt",
    ]
    EXCLUDED_TXT_PREFIXES = ["md5", "ffp", "fingerprint", "checksum"]
    
    # Scoring weights for recording quality
    SCORE_MP3_COUNT_MULTIPLIER = 1000      # Points per MP3 track
    SCORE_SOUNDBOARD = 500                  # Soundboard source
    SCORE_MATRIX = 300                      # Matrix source
    SCORE_QUALITY_MICS = 200                # Premium microphones
    SCORE_HIGH_RES = 100                    # 24-bit/96kHz indicators
    SCORE_RATING_MULTIPLIER = 50            # Points per star rating
    SCORE_SIZE_DIVISOR = 10                 # 1 point per N megabytes
    
    # Quality indicator keywords
    SOUNDBOARD_KEYWORDS = ["sbd", "soundboard"]
    MATRIX_KEYWORDS = ["matrix"]
    QUALITY_MIC_KEYWORDS = ["schoeps", "dpa", "neumann", "akg", "earthworks"]
    HIGH_RES_KEYWORDS = ["24bit", "24/", "96k", "24-bit"]
    
    # ID3 tagging settings
    ID3_VERSION = 3                         # ID3v2.3 for Music.app compatibility
    DEFAULT_GENRE = "Bluegrass"             # Can be overridden
    
    # Music.app COMM frame settings
    COMM_LANG_XXX = "XXX"                   # Language code for primary COMM frame
    COMM_LANG_ENG = "eng"                   # Language code for fallback COMM frame
    COMM_ENCODING_XXX = 1                   # UTF-16 encoding
    COMM_ENCODING_ENG = 0                   # LATIN1 encoding
    
    # Filename patterns for track parsing
    DISC_TRACK_PATTERNS = [
        r"[ds](\d+)[tT](\d{1,2})",          # d2t01, d2T01, s2t01, s2T01
        r"[tT](\d{1,2})",                   # t01, T01 (single disc, track only)
        r"^(\d{2})(\d{2})\s",               # 0101 (4 digits: disc+track with space)
    ]
    
    # Track number patterns (in order of precedence)
    TRACK_NUMBER_PATTERNS = [
        r"^(\d{1,2})[\.:\)\-]\s*(.+)$",     # 01. / 01: / 01) / 01-
        r"^(\d{1,2})\s+-\s*(.+)$",          # 01 -
        r"^(\d{1,2})\s{2,}(.+)$",           # 01  (2+ spaces)
        r"^(\d{1,2})([A-Z].+)$",            # 01TrackName (PascalCase)
    ]
    
    # Disc/Set marker patterns in text files
    DISC_MARKER_PATTERNS = [
        r"^\s*[Dd][Ii][Ss][CcKk]\s+(\d+)",  # Disc/Disk N
        r"^\s*[Ss][Ee][Tt]\s+(\d+)",        # Set N
    ]
    
    # HTML entities for decoding
    HTML_ENTITIES = {
        "&gt;": ">",
        "&lt;": "<",
        "&quot;": '"',
        "&apos;": "'",
        "&amp;": "&",  # Must be last
    }
    
    # Track name normalization patterns
    DURATION_PREFIX_PATTERN = r"^\[?\d{1,2}:\d{2}(:\d{2})?\]\s*"
    
    # Logging settings
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    
    # Directory naming
    CONCERT_DIR_FORMAT = "{date}"           # YYYY-MM-DD
    
    # Character encodings to detect
    LEGACY_ENCODINGS = ["iso-8859", "windows-1252", "us-ascii"]
    TARGET_ENCODING = "utf-8"
    
    # Parallel processing settings
    MAX_WORKERS = 4                         # For concurrent downloads/processing
    
    @classmethod
    def get_ia_search_query(cls, creator: str) -> str:
        """
        Build Internet Archive search query for a creator.
        
        Args:
            creator: Artist/creator name
            
        Returns:
            Search query string
        """
        return f'creator:"{creator}" AND mediatype:{cls.IA_MEDIATYPE} AND format:{cls.IA_FORMAT}'
    
    @classmethod
    def get_metadata_path(cls, base_dir: Path) -> Path:
        """
        Get path to metadata cache file.
        
        Args:
            base_dir: Base directory for creator
            
        Returns:
            Path to .metadata.yaml file
        """
        return base_dir / cls.METADATA_FILENAME
    
    @classmethod
    def is_excluded_txt_file(cls, filename: str) -> bool:
        """
        Check if a text file should be excluded from tracklist parsing.
        
        Args:
            filename: Name of the text file
            
        Returns:
            True if file should be excluded
        """
        filename_lower = filename.lower()
        
        # Check exact matches
        if filename in cls.EXCLUDED_TXT_FILES:
            return True
        
        # Check prefixes
        for prefix in cls.EXCLUDED_TXT_PREFIXES:
            if filename_lower.startswith(prefix):
                return True
        
        return False
    
    @classmethod
    def decode_html_entities(cls, text: str) -> str:
        r"""
        Decode HTML entities in text and remove erroneous backslash escapes.
        
        Internet Archive XML files sometimes contain incorrectly escaped
        characters like \&gt; and \' that should just be &gt; and '.
        ElementTree automatically decodes the HTML entities, so we need to
        remove backslashes before the resulting characters (>, <, ", ', &).
        
        Args:
            text: Text with HTML entities
            
        Returns:
            Decoded text
        """
        import re
        
        result = text
        
        # First decode any remaining HTML entities that ElementTree didn't handle
        for entity, char in cls.HTML_ENTITIES.items():
            result = result.replace(entity, char)
        
        # Remove backslashes before common characters that were HTML entities
        # ElementTree auto-decodes &gt; &lt; &quot; &apos; &amp; before we see them
        # So we need to remove backslashes before >, <, ", ', &
        result = result.replace('\\>', '>')
        result = result.replace('\\<', '<')
        result = result.replace('\\"', '"')
        result = result.replace("\\'", "'")
        result = result.replace('\\&', '&')
        
        return result
    
    @classmethod
    def get_genre_for_artist(cls, artist: str) -> str:
        """
        Get genre for an artist (can be extended for artist-specific genres).
        
        Args:
            artist: Artist name
            
        Returns:
            Genre string
        """
        # For now, return default. Can be extended with a mapping dict later
        return cls.DEFAULT_GENRE


# Singleton instance
config = Config()
