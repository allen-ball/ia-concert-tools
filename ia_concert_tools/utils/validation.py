"""
Input validation utilities.

Validates user inputs like creator names, date filters, etc.
"""

import re
from pathlib import Path
from typing import List, Optional

from ia_concert_tools.logging_config import get_logger

logger = get_logger("validation")


def validate_creator(creator: str) -> bool:
    """
    Validate creator/artist name.
    
    Args:
        creator: Creator name
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If creator name is invalid
    """
    if not creator or not creator.strip():
        raise ValueError("Creator name cannot be empty")
    
    if len(creator) > 200:
        raise ValueError("Creator name too long (max 200 characters)")
    
    return True


def validate_date_filter(date_filter: str) -> bool:
    """
    Validate date filter format.
    
    Accepts:
    - Full date: YYYY-MM-DD
    - Month: YYYY-MM
    - Year: YYYY
    
    Args:
        date_filter: Date filter string
        
    Returns:
        True if valid
        
    Raises:
        ValueError: If date filter is invalid
    """
    if not date_filter:
        raise ValueError("Date filter cannot be empty")
    
    # Match YYYY, YYYY-MM, or YYYY-MM-DD
    pattern = r"^\d{4}(-\d{2}(-\d{2})?)?$"
    
    if not re.match(pattern, date_filter):
        raise ValueError(
            f"Invalid date filter: {date_filter}. "
            "Expected format: YYYY, YYYY-MM, or YYYY-MM-DD"
        )
    
    return True


def validate_directory(dir_path: Path) -> bool:
    """
    Validate that a directory exists and is readable.
    
    Args:
        dir_path: Directory path
        
    Returns:
        True if valid
        
    Raises:
        FileNotFoundError: If directory does not exist
        PermissionError: If directory is not readable
    """
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")
    
    if not dir_path.is_dir():
        raise ValueError(f"Not a directory: {dir_path}")
    
    if not dir_path.is_readable():
        raise PermissionError(f"Directory not readable: {dir_path}")
    
    return True


def normalize_creator_name(creator: str) -> str:
    """
    Normalize creator name for directory/file usage.
    
    Args:
        creator: Creator name
        
    Returns:
        Normalized creator name (safe for filesystem)
    """
    # Validate first
    validate_creator(creator)
    
    # Remove leading/trailing whitespace
    normalized = creator.strip()
    
    return normalized


def match_date_filter(date: str, filters: List[str]) -> bool:
    """
    Check if a date matches any of the provided filters.
    
    Uses prefix matching, so:
    - "2023" matches "2023-10-15"
    - "2023-10" matches "2023-10-15"
    - "2023-10-15" matches "2023-10-15" exactly
    
    Args:
        date: Date string (YYYY-MM-DD format)
        filters: List of date filter strings
        
    Returns:
        True if date matches any filter
    """
    if not filters:
        return True  # No filters means match all
    
    for filter_date in filters:
        if date.startswith(filter_date):
            return True
    
    return False
