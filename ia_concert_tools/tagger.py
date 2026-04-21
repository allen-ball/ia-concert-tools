"""
ID3 tag management for MP3 files.

Updates tags based on metadata from XML files and tracklists using mutagen.
Supports multi-disc concerts and Music.app compatibility.
"""

from pathlib import Path
from typing import Dict, Optional, List, Tuple
import re

from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TPE2, TALB, TDRC, TRCK, TPOS, TCON, COMM

from ia_concert_tools.config import Config
from ia_concert_tools.logging_config import get_logger
from ia_concert_tools.parsers.xml_parser import XmlParser
from ia_concert_tools.parsers.tracklist_parser import TracklistParser
from ia_concert_tools.parsers.filename_parser import FilenameParser

logger = get_logger("tagger")


class Tagger:
    """Update ID3 tags on concert recordings."""
    
    def __init__(self, creator: str, genre: Optional[str] = None):
        """
        Initialize tagger.
        
        Args:
            creator: Artist/creator name
            genre: Override default genre
        """
        self.creator = creator
        self.genre = genre or Config.DEFAULT_GENRE
        self.base_dir = Path(creator)
    
    def get_concert_dirs(self) -> List[Path]:
        """
        Get list of concert directories.
        
        Returns:
            List of concert directory paths
        """
        if not self.base_dir.exists():
            logger.error(f"Directory not found: {self.base_dir}")
            return []
        
        # Find directories matching YYYY-MM-DD pattern
        concert_dirs = []
        for item in self.base_dir.iterdir():
            if item.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", item.name):
                concert_dirs.append(item)
        
        return sorted(concert_dirs)
    
    def detect_total_discs(self, concert_dir: Path) -> int:
        """
        Detect total number of discs from filenames and text files.
        
        Args:
            concert_dir: Concert directory
            
        Returns:
            Total disc count (1 if single disc)
        """
        max_disc = 0
        
        # Check MP3 filenames for disc notation
        for mp3_file in concert_dir.glob("*.mp3"):
            disc_track = FilenameParser.parse_disc_track(mp3_file.name)
            if disc_track:
                disc_num = disc_track[0]
                if disc_num > max_disc:
                    max_disc = disc_num
        
        # Check text files for disc markers
        for txt_file in concert_dir.glob("*.txt"):
            if Config.is_excluded_txt_file(txt_file.name):
                continue
            
            parser = TracklistParser(txt_file)
            _, total_discs = parser.parse_with_disc_info()
            if total_discs > max_disc:
                max_disc = total_discs
        
        return max(max_disc, 1)
    
    def get_track_title_sources(self, concert_dir: Path) -> Tuple[Dict[str, str], Dict[int, str]]:
        """
        Get track titles from all sources (XML, txt).
        
        Priority: XML > txt file
        
        Args:
            concert_dir: Concert directory
            
        Returns:
            Tuple of (xml_titles_by_filename, txt_titles_by_track_num)
        """
        xml_titles = {}
        txt_titles = {}
        
        # Get XML titles (highest priority)
        xml_parser = XmlParser(concert_dir)
        xml_titles = xml_parser.get_track_titles()
        
        if xml_titles:
            logger.debug(f"Found {len(xml_titles)} titles in XML")
        
        # Get txt titles (fallback)
        for txt_file in concert_dir.glob("*.txt"):
            if Config.is_excluded_txt_file(txt_file.name):
                continue
            
            parser = TracklistParser(txt_file)
            txt_titles = parser.parse()
            if txt_titles:
                logger.debug(f"Found {len(txt_titles)} titles in {txt_file.name}")
                break
        
        return xml_titles, txt_titles
    
    def needs_update(self, mp3_file: Path, new_tags: Dict[str, str]) -> bool:
        """
        Check if MP3 file needs tag updates.
        
        Args:
            mp3_file: Path to MP3 file
            new_tags: Dictionary of new tag values
            
        Returns:
            True if tags need updating
        """
        try:
            audio = MP3(mp3_file, ID3=ID3)
            
            # Check each tag
            checks = [
                (audio.tags.get('TIT2'), new_tags.get('title')),
                (audio.tags.get('TPE1'), new_tags.get('artist')),
                (audio.tags.get('TPE2'), new_tags.get('album_artist')),
                (audio.tags.get('TALB'), new_tags.get('album')),
                (audio.tags.get('TDRC'), new_tags.get('date')),
                (audio.tags.get('TRCK'), new_tags.get('track')),
                (audio.tags.get('TCON'), new_tags.get('genre')),
            ]
            
            # Check disc tag only if present in new_tags
            if 'disc' in new_tags:
                checks.append((audio.tags.get('TPOS'), new_tags.get('disc')))
            
            for current, new_value in checks:
                if new_value is None:
                    continue
                    
                current_text = str(current) if current else None
                if current_text != new_value:
                    return True
            
            # Check COMM frames
            comm_frames = audio.tags.getall('COMM')
            has_xxx_comment = any(
                frame.lang == Config.COMM_LANG_XXX 
                for frame in comm_frames
            )
            if not has_xxx_comment and new_tags.get('comment'):
                return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Error checking {mp3_file.name}: {e}")
            return True  # Update on error
    
    def set_music_app_comments(self, audio: MP3, comment_text: str) -> None:
        """
        Set Music.app compatible COMM frames.
        
        Args:
            audio: MP3 audio object
            comment_text: Comment text
        """
        # Remove existing COMM frames
        audio.tags.delall('COMM')
        
        # Add COMM::XXX frame (UTF-16, required by Music.app)
        audio.tags.add(COMM(
            encoding=Config.COMM_ENCODING_XXX,
            lang=Config.COMM_LANG_XXX,
            desc='',
            text=comment_text
        ))
        
        # Add COMM::eng frame (LATIN1, fallback)
        audio.tags.add(COMM(
            encoding=Config.COMM_ENCODING_ENG,
            lang=Config.COMM_LANG_ENG,
            desc='',
            text=comment_text
        ))
    
    def update_mp3_tags(
        self,
        mp3_file: Path,
        metadata: Dict[str, str],
        dry_run: bool = False
    ) -> bool:
        """
        Update tags on a single MP3 file.
        
        Args:
            mp3_file: Path to MP3 file
            metadata: Dictionary of tag values
            dry_run: Don't actually modify file
            
        Returns:
            True if updated (or would update in dry run)
        """
        if not self.needs_update(mp3_file, metadata):
            return False
        
        if dry_run:
            logger.info(f"  Would update: {mp3_file.name}")
            return True
        
        try:
            audio = MP3(mp3_file, ID3=ID3)
            
            # Ensure tags exist
            if audio.tags is None:
                audio.add_tags()
            
            # Clean up malformed frames (like bad LINK frames from archive.org)
            for key in list(audio.tags.keys()):
                if key.startswith('LINK') or '\x00' in key:
                    logger.debug(f"  Removing malformed frame: {key}")
                    try:
                        del audio.tags[key]
                    except:
                        pass
            
            # Set basic tags (delall first to avoid duplicates)
            if metadata.get('title'):
                audio.tags.delall('TIT2')
                audio.tags.add(TIT2(encoding=3, text=metadata['title']))
            
            if metadata.get('artist'):
                audio.tags.delall('TPE1')
                audio.tags.delall('TPE2')
                audio.tags.add(TPE1(encoding=3, text=metadata['artist']))
                audio.tags.add(TPE2(encoding=3, text=metadata['artist']))  # album_artist
            
            if metadata.get('album'):
                audio.tags.delall('TALB')
                audio.tags.add(TALB(encoding=3, text=metadata['album']))
            
            if metadata.get('date'):
                audio.tags.delall('TDRC')
                audio.tags.add(TDRC(encoding=3, text=metadata['date']))
            
            if metadata.get('track'):
                audio.tags.delall('TRCK')
                audio.tags.add(TRCK(encoding=3, text=metadata['track']))
            
            if metadata.get('genre'):
                audio.tags.delall('TCON')
                audio.tags.add(TCON(encoding=3, text=metadata['genre']))
            
            # Set disc tag only if multi-disc
            if metadata.get('disc'):
                audio.tags.delall('TPOS')
                audio.tags.add(TPOS(encoding=3, text=metadata['disc']))
            
            # Set comment with Music.app compatibility
            if metadata.get('comment'):
                self.set_music_app_comments(audio, metadata['comment'])
            
            # Save with ID3v2.3 for Music.app compatibility
            audio.save(v2_version=3)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update {mp3_file.name}: {e}")
            return False
    
    def process_concert(self, concert_dir: Path, dry_run: bool = False) -> Dict[str, int]:
        """
        Process all MP3 files in a concert directory.
        
        Args:
            concert_dir: Concert directory
            dry_run: Don't actually modify files
            
        Returns:
            Statistics dict
        """
        stats = {"updated": 0, "skipped": 0, "failed": 0}
        
        logger.info(f"Processing: {concert_dir.name}")
        
        # Get metadata from XML
        xml_parser = XmlParser(concert_dir)
        xml_metadata = xml_parser.get_all_metadata()
        
        artist = xml_metadata.get('artist') or self.creator
        album = xml_metadata.get('album') or f"Live at {concert_dir.name}"
        date = xml_metadata.get('year') or concert_dir.name[:4]
        
        # Get identifier for comment
        identifier = xml_metadata.get('identifier')
        comment = f"https://archive.org/details/{identifier}" if identifier else f"Live concert recording - {concert_dir.name}"
        
        # Get track titles
        xml_titles, txt_titles = self.get_track_title_sources(concert_dir)
        
        # Detect total discs
        total_discs = self.detect_total_discs(concert_dir)
        
        # Get all MP3 files
        mp3_files = sorted(concert_dir.glob("*.mp3"))
        total_tracks = len(mp3_files)
        
        logger.info(f"  Found {total_tracks} MP3 files")
        if total_discs > 1:
            logger.info(f"  Multi-disc concert: {total_discs} discs")
        
        # Calculate disc offsets for global track numbering (not currently used but ready)
        disc_offsets = {}
        if total_discs > 1:
            current_offset = 0
            for disc_num in range(1, total_discs + 1):
                disc_offsets[disc_num] = current_offset
                # Count files for this disc
                disc_files = [
                    f for f in mp3_files
                    if FilenameParser.parse_disc_track(f.name) and 
                    FilenameParser.parse_disc_track(f.name)[0] == disc_num
                ]
                current_offset += len(disc_files)
        
        # Process each MP3
        for mp3_file in mp3_files:
            # Parse filename
            disc_num, track_num, filename_title = FilenameParser.parse(mp3_file.name)
            
            if track_num is None:
                logger.warning(f"  Could not parse track number: {mp3_file.name}")
                stats["skipped"] += 1
                continue
            
            # Get track title (priority: XML > txt > filename)
            title = None
            
            # Try XML (by filename)
            if mp3_file.name in xml_titles:
                title = xml_titles[mp3_file.name]
            
            # Try txt (by track number)
            elif track_num in txt_titles:
                title = txt_titles[track_num]
            
            # Fallback to filename
            elif filename_title:
                title = filename_title
            else:
                title = mp3_file.stem
            
            # Build track string (track/total)
            track_str = f"{track_num}/{total_tracks}"
            
            # Build disc string (only if multi-disc)
            disc_str = None
            if total_discs > 1 and disc_num:
                disc_str = f"{disc_num}/{total_discs}"
            
            # Build metadata dict
            metadata = {
                "title": title,
                "artist": artist,
                "album": album,
                "date": date,
                "track": track_str,
                "genre": self.genre,
                "comment": comment,
            }
            
            if disc_str:
                metadata["disc"] = disc_str
            
            # Update tags
            if self.update_mp3_tags(mp3_file, metadata, dry_run):
                stats["updated"] += 1
                logger.debug(f"  Updated: {mp3_file.name} - {title}")
            else:
                stats["skipped"] += 1
        
        return stats
    
    def update_tags(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Update ID3 tags on all MP3 files.
        
        Args:
            dry_run: Show what would change without modifying
            
        Returns:
            Dictionary with update statistics
        """
        stats = {"updated": 0, "skipped": 0, "concerts": 0, "failed": 0}
        
        concert_dirs = self.get_concert_dirs()
        
        if not concert_dirs:
            logger.warning(f"No concert directories found in {self.base_dir}")
            return stats
        
        logger.info(f"Found {len(concert_dirs)} concert directories")
        
        for concert_dir in concert_dirs:
            concert_stats = self.process_concert(concert_dir, dry_run)
            stats["updated"] += concert_stats["updated"]
            stats["skipped"] += concert_stats["skipped"]
            stats["failed"] += concert_stats["failed"]
            stats["concerts"] += 1
        
        return stats
