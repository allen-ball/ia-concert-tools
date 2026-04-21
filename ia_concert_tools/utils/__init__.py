"""Utility functions."""

from ia_concert_tools.utils.encoding import detect_encoding, read_with_encoding
from ia_concert_tools.utils.validation import validate_date_filter, validate_creator


def normalize_date(date_str: str) -> str:
    """
    Normalize date from ISO timestamp to YYYY-MM-DD format.
    
    Internet Archive returns dates as ISO timestamps like '1988-06-28T00:00:00Z',
    but we need just the date part '1988-06-28' for grouping.
    
    Args:
        date_str: Date string (may be ISO timestamp or just date)
        
    Returns:
        Date in YYYY-MM-DD format, or "unknown" if invalid
    """
    if not date_str or date_str == "unknown":
        return "unknown"
    
    # If it's already in YYYY-MM-DD format, return as-is
    if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
        return date_str
    
    # Extract date part from ISO timestamp (YYYY-MM-DDTHH:MM:SSZ -> YYYY-MM-DD)
    if 'T' in date_str:
        return date_str.split('T')[0]
    
    # Fallback: return first 10 characters if it looks like a date
    if len(date_str) >= 10:
        return date_str[:10]
    
    return "unknown"


__all__ = [
    "detect_encoding",
    "read_with_encoding",
    "validate_date_filter",
    "validate_creator",
    "normalize_date",
]
