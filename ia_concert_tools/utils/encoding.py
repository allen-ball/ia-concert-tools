"""
Character encoding detection and conversion utilities.

Handles UTF-8 vs legacy encodings (Windows-1252, ISO-8859) to prevent
double-encoding issues with special characters.
"""

from pathlib import Path
from typing import Union, List

import chardet

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger

logger = get_logger("encoding")


def detect_encoding(file_path: Union[str, Path]) -> str:
    """
    Detect character encoding of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        Detected encoding name (e.g., 'utf-8', 'windows-1252')
    """
    file_path = Path(file_path)
    
    # Read a sample of the file for detection
    with open(file_path, "rb") as f:
        raw_data = f.read(10000)  # Read first 10KB
    
    # Detect encoding
    result = chardet.detect(raw_data)
    encoding = result["encoding"]
    confidence = result["confidence"]
    
    logger.debug(f"Detected encoding: {encoding} (confidence: {confidence:.2%})")
    
    # Normalize encoding name
    if encoding:
        encoding = encoding.lower()
    else:
        # Default to UTF-8 if detection fails
        encoding = "utf-8"
        logger.warning(f"Could not detect encoding for {file_path}, assuming UTF-8")
    
    return encoding


def is_legacy_encoding(encoding: str) -> bool:
    """
    Check if encoding is a legacy encoding that needs conversion.
    
    Args:
        encoding: Encoding name
        
    Returns:
        True if encoding is legacy (non-UTF-8)
    """
    encoding_lower = encoding.lower()
    
    # Check against known legacy encodings
    for legacy in Config.LEGACY_ENCODINGS:
        if legacy.lower() in encoding_lower:
            return True
    
    # Also check for exact matches
    if encoding_lower in ["ascii", "latin1", "latin-1", "cp1252"]:
        return True
    
    return False


def read_with_encoding(file_path: Union[str, Path]) -> str:
    """
    Read a text file with proper encoding detection.
    
    Detects the file encoding and converts to UTF-8 if necessary.
    This prevents double-encoding issues with special characters.
    
    Args:
        file_path: Path to text file
        
    Returns:
        File contents as UTF-8 string
        
    Raises:
        UnicodeDecodeError: If file cannot be decoded
        FileNotFoundError: If file does not exist
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    # Detect encoding
    detected_encoding = detect_encoding(file_path)
    
    # Read file with detected encoding
    try:
        with open(file_path, "r", encoding=detected_encoding, errors="replace") as f:
            content = f.read()
        
        logger.debug(f"Read {file_path.name} with encoding: {detected_encoding}")
        return content
        
    except UnicodeDecodeError as e:
        logger.warning(f"Failed to decode {file_path} with {detected_encoding}, trying UTF-8")
        
        # Fallback to UTF-8
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        return content


def read_lines_with_encoding(file_path: Union[str, Path]) -> List[str]:
    """
    Read lines from a text file with proper encoding detection.
    
    Args:
        file_path: Path to text file
        
    Returns:
        List of lines (with newlines stripped)
    """
    content = read_with_encoding(file_path)
    
    # Split into lines and strip line endings
    lines = []
    for line in content.splitlines():
        # Remove carriage returns (Windows line endings)
        line = line.rstrip("\r\n")
        lines.append(line)
    
    return lines
