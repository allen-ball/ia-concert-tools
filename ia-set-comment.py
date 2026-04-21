#!/usr/bin/env python3
"""
Set ID3v2.3 comment with language code 'XXX' for Music.app compatibility.

Music.app displays comments from COMM frames with lang='XXX' (uppercase)
and empty descriptor. This creates the 'Comment-xxx' frame visible in exiftool.

Usage: ia-set-comment.py <mp3_file> <comment_text>
"""
import sys
from mutagen.id3 import ID3, COMM

if len(sys.argv) != 3:
    print("Usage: ia-set-comment.py <mp3_file> <comment_text>", file=sys.stderr)
    sys.exit(1)

filename = sys.argv[1]
comment_text = sys.argv[2]

try:
    # Load the ID3 tag
    audio = ID3(filename)
    
    # Remove existing COMM frames (except ID3v1 Comment frame)
    for key in list(audio.keys()):
        if key.startswith('COMM') and 'ID3v1' not in key:
            del audio[key]
    
    # Add COMM frames to match working Jerry Garcia file format
    # Music.app requires BOTH of these frames:
    # 1. COMM::XXX with UTF-16 encoding
    audio.add(COMM(encoding=1, lang='XXX', desc='', text=comment_text))
    # 2. COMM::eng with LATIN1 encoding
    audio.add(COMM(encoding=0, lang='eng', desc='', text=comment_text))
    
    # Save changes (force v2.3)
    audio.save(filename, v2_version=3)
    
except Exception as e:
    print(f"Error setting comment: {e}", file=sys.stderr)
    sys.exit(1)
