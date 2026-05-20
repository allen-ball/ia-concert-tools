# Copilot Instructions for Internet Archive Concert Tools (Python)

**Last Updated:** 2026-04-20 (Python implementation complete)  
**Project Status:** Production-ready, Phases 1-5 complete (71% done)

## Project Overview

Python toolkit for downloading and tagging live concert recordings from the Internet Archive (archive.org). This is a complete rewrite of the original Bash scripts using the official `internetarchive` Python library.

**Key Features:**
1. Download concert MP3 files with automatic deduplication (best per date)
2. Parse and update ID3 tags from XML files, tracklists, and filenames
3. Multi-disc/set support with proper track numbering
4. Music.app compatible COMM frames
5. Idempotent operations (safe to re-run)

**Installation**: Installed via pip/pipx or as editable development package

## Architecture & Technologies

### Core Dependencies
- **`internetarchive >= 3.0.0`** - Official Internet Archive Python library
- **`mutagen >= 1.45.0`** - ID3 tag manipulation (replaces ffmpeg)
- **`pyyaml >= 6.0`** - YAML cache handling
- **`chardet >= 5.0.0`** - Character encoding detection
- **`click >= 8.0.0`** - CLI framework

### Project Structure

```
ia_concert_tools/
├── __init__.py              # Package initialization
├── __main__.py              # CLI entry point (Click framework)
├── config.py                # Configuration constants (~87 lines)
├── logging_config.py        # Colored logging setup
├── metadata.py              # Metadata builder (~262 lines)
├── downloader.py            # Download manager (~133 lines)
├── tagger.py                # ID3 tagging (~400 lines)
├── parsers/                 # Metadata parsers (~500 lines)
│   ├── xml_parser.py        # *_meta.xml and *_files.xml parsing
│   ├── tracklist_parser.py  # Text tracklist parsing
│   └── filename_parser.py   # Filename pattern matching
└── utils/                   # Utilities (~100 lines)
    ├── encoding.py          # Character encoding detection
    └── validation.py        # Input validation
```

**Total**: ~1,650 lines of Python code (excluding tests)

## CLI Commands

The `ia-concerts` command provides three subcommands:

### 1. build-cache
```bash
ia-concerts build-cache "Billy Strings" [--force]
```
- Fetches all recordings for creator from Internet Archive
- Scores based on quality metrics (track count, source, equipment)
- Outputs `.metadata.yaml` cache (7-day expiry)
- **Optimization**: Date filtering - only fetches needed dates when used with download

### 2. download
```bash
ia-concerts download "Grateful Dead" [dates...]
```
- Downloads concerts with automatic deduplication (best per date)
- Date filtering supports: `2023-10-15`, `2023-10`, `2023`
- Skips already-downloaded concerts
- Downloads: `*.mp3`, `*.xml`, `*.txt`, `*.md5`
- Directory structure: `{Creator}/{YYYY-MM-DD}/`

### 3. update-tags
```bash
ia-concerts update-tags "Billy Strings" [--genre GENRE] [--dry-run]
```
- Updates ID3 tags using mutagen library
- Priority: XML → txt → filename → existing tags
- Multi-disc support with disc/track tags
- Music.app COMM frame compatibility
- Idempotent (only updates changed files)

### Global Options
- `-v, --verbose`: Debug logging
- `-q, --quiet`: Warnings/errors only
- `--version`: Show version

## Code Patterns & Conventions

### Configuration (config.py)

All constants, regex patterns, and scoring weights centralized:

```python
class Config:
    # Scoring
    SCORE_MP3_COUNT_MULTIPLIER = 1000
    SCORE_SOUNDBOARD = 500
    SCORE_MATRIX = 300
    
    # Regex patterns
    DISC_TRACK_PATTERN = re.compile(r'[ds]([0-9]+)[tT]([0-9]{1,2})')
    TRACK_NUMBER_PATTERNS = [
        re.compile(r'^([0-9]{1,2})[\.:\)\-]\s*(.+)$'),
        re.compile(r'^([0-9]{1,2})\s+-\s*(.+)$'),
    ]
    
    # Music.app compatibility
    COMM_LANG_XXX = 'XXX'
    COMM_LANG_ENG = 'eng'
    COMM_ENCODING_XXX = 1  # UTF-16
    COMM_ENCODING_ENG = 0  # LATIN1
```

### Metadata Builder (metadata.py)

**Key Features:**
- Internet Archive search: `ia.search_items()` with date filtering
- Parallel fetching: `ThreadPoolExecutor` (20 workers)
- Quality scoring algorithm
- YAML cache with 7-day expiry

**Date Filtering Optimization:**
- Grateful Dead has 18,040 recordings on Internet Archive
- Without optimization: ~3 hours to fetch all metadata
- With date filtering: Seconds to fetch only needed dates
- Example: 54 recordings fetched in ~2 min (4 date filters)

**Quality Scoring:**
```python
score = (
    mp3_count * 1000 +
    (500 if 'soundboard' in source else 0) +
    (300 if 'matrix' in source else 0) +
    (200 if quality_mic in lineage else 0) +
    (100 if '24' in lineage else 0) +
    (avg_rating * 50) +
    (total_size_mb / 10)
)
```

### Downloader (downloader.py)

**Key Features:**
- Uses `internetarchive.get_item()` (not CLI)
- Deduplication from metadata cache
- Date prefix matching (`2023-10` matches all October)
- Skip existing concerts
- Downloads with `item.download(glob_pattern=...)`

**Directory Naming:** `{YYYY-MM-DD}/` (simplified from Bash `{date}_{identifier}`)

### Parsers

**XML Parser (xml_parser.py):**
- `*_meta.xml`: Extracts artist, album, year, identifier
- `*_files.xml`: Extracts track titles with HTML entity decoding
- HTML entities: `&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&`
- Preserves jam band notation: `>` (segue), `#` (tease), `@` (quote)

**Tracklist Parser (tracklist_parser.py):**
- Character encoding detection (prevents double-encoding UTF-8)
- Multiple numbering patterns: `01.`, `01:`, `01)`, `01-`, `01 - `
- Disc/set markers: "Disc N", "Set N:" (case-insensitive)
- Track name normalization

**Filename Parser (filename_parser.py):**
- Disc-track notation: `d2t01`, `s1t05` (case-insensitive: `[tT]`)
- Set notation: `set101`, `set209` (set/disc + 2-digit track, e.g., set 1 track 01)
- Track extraction: space, underscore, PascalCase
- Example: `01TurmoilAndTinfoil.mp3` → "Turmoil And Tinfoil"
- Example: `GD791027set201.wav_vbr.mp3` → disc 2, track 01

### Tagger (tagger.py)

**Key Features:**
- Replaces ffmpeg with mutagen library
- ID3v2.3 format for Music.app compatibility
- Idempotent tag checking with `needs_update()`
- Malformed frame cleanup (handles bad LINK frames)
- Multi-disc support

**Tag Mapping:**
- `artist`/`album_artist`: From XML `<creator>` or creator name
- `album`: From XML `<title>` or `Live at {venue} ({date})`
- `date`: From XML `<year>` or directory year
- `title`: XML track titles → txt → filename (priority order)
- `track`: `{track_num}/{total_tracks}`
- `disc`: `{disc_num}/{total_discs}` (only if multi-disc)
- `genre`: Configurable (default: Bluegrass)
- `comment`: `https://archive.org/details/{identifier}`

**Music.app COMM Frames:**
```python
def set_music_app_comments(self, audio: MP3, comment_text: str):
    audio.tags.delall('COMM')
    
    # Required frame 1: XXX with UTF-16
    audio.tags.add(COMM(
        encoding=1,  # UTF-16
        lang='XXX',
        desc='',
        text=comment_text
    ))
    
    # Required frame 2: eng with LATIN1
    audio.tags.add(COMM(
        encoding=0,  # LATIN1
        lang='eng',
        desc='',
        text=comment_text
    ))
```

**Idempotent Tag Checking:**
```python
def needs_update(self, mp3_file: Path, new_tags: Dict[str, str]) -> bool:
    audio = MP3(mp3_file, ID3=ID3)
    
    # Compare all tags
    checks = [
        (audio.tags.get('TIT2'), new_tags.get('title')),
        (audio.tags.get('TPE1'), new_tags.get('artist')),
        # ... all other tags
    ]
    
    for current, new_value in checks:
        if str(current) != new_value:
            return True
    
    # Check COMM frames
    comm_frames = audio.tags.getall('COMM')
    has_xxx = any(f.lang == 'XXX' for f in comm_frames)
    if not has_xxx and new_tags.get('comment'):
        return True
    
    return False
```

### Character Encoding Handling

**Critical Pattern** (prevents double-encoding):
```python
from ia_concert_tools.utils.encoding import detect_encoding

encoding = detect_encoding(file_path)
if encoding in ['UTF-8', 'utf-8', 'ascii']:
    # Already UTF-8, read directly
    content = file_path.read_text()
else:
    # Convert from windows-1252, iso-8859, etc.
    content = file_path.read_text(encoding='windows-1252')
```

**Why this matters:** Blindly converting UTF-8 files causes `'` (U+2019) → `â€™`

## Testing & Validation

### Validation Results (2026-04-20)

Tested against reference Bash implementation:

**Billy Strings 2019-09-28** (23 tracks, 2 discs):
- ✅ All ID3 tags match perfectly
- ✅ Multi-disc track/disc numbering correct
- ✅ COMM frames verified (both XXX and eng)
- ✅ Archive.org URLs in comments
- ✅ Files 0.01% smaller (cleaner tag structure)

**Idempotency Tests:**
- ✅ Download: Skips existing (0 downloaded, 2 skipped)
- ✅ Tagging: Skips unchanged (0 updated, 45 skipped)
- ✅ Change detection: Updates only changed files (1 updated, 44 skipped)
- ✅ Performance: ~3 seconds for 45 files (read-only checks)

See `.github/VALIDATION.md` and `.github/IDEMPOTENCY.md` for detailed reports.

## Common Maintenance Tasks

### Adding New Genre Support

Modify CLI default or use `--genre` flag:
```python
# config.py
DEFAULT_GENRE = "Bluegrass"

# Or at runtime:
ia-concerts update-tags "Artist" --genre "Rock"
```

### Supporting Additional Filename Formats

Add pattern to `filename_parser.py`:
```python
# In parse() method, add new regex pattern
if match := re.match(r'^new_pattern_here$', filename):
    # Extract track number and name
    return disc, track_num, track_name
```

### Supporting Additional Text File Formats

Add pattern to `config.py`:
```python
TRACK_NUMBER_PATTERNS = [
    re.compile(r'^([0-9]{1,2})[\.:\)\-]\s*(.+)$'),
    re.compile(r'^([0-9]{1,2})\s+-\s*(.+)$'),
    # Add new pattern here
]
```

### Adjusting Quality Scoring

Modify scoring weights in `config.py`:
```python
SCORE_MP3_COUNT_MULTIPLIER = 1000  # Increase for more weight on completeness
SCORE_SOUNDBOARD = 500             # Increase for more weight on SBD sources
```

## Performance Notes

### Optimization Wins
- **Date filtering**: 20x faster metadata fetching (seconds vs hours)
- **Parallel fetching**: 20 workers for concurrent API calls
- **Idempotent tagging**: Only updates changed files (~3s for 45 files)
- **Cache expiry**: 7-day cache avoids repeated API calls

### Test Dataset (Grateful Dead)
- 18,040 total recordings on Internet Archive
- 4 concerts downloaded (96 MP3 files, ~666 MB)
- Metadata: 54 recordings fetched in ~2 minutes (with date filtering)
- Download: 3 concerts in ~3 minutes
- Tagging: 96 files in ~10 seconds

## Known Issues

None currently - all core functionality working as expected.

## Migration Status

**Original Bash Scripts** (REMOVED 2026-04-20):
- ❌ `ia-build-metadata.sh` (200 lines) → ✅ `ia-concerts build-cache`
- ❌ `ia-download-concerts.sh` (180 lines) → ✅ `ia-concerts download`
- ❌ `ia-update-concert-tags.sh` (742 lines) → ✅ `ia-concerts update-tags`
- ❌ `ia-set-comment.py` (42 lines) → ✅ Integrated into tagger module

**Total Removed**: ~1,164 lines of Bash/Python  
**Total Added**: ~1,650 lines of Python  
**Net Gain**: +486 lines, but much better:
- Structure and modularity
- Error handling
- Testability
- Type hints ready
- Maintainability

## Development Workflow

### Running Tests
```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (when Phase 6 complete)
pytest
pytest --cov=ia_concert_tools --cov-report=html

# Type checking
mypy ia_concert_tools

# Code formatting
black ia_concert_tools tests
```

### Testing Locally
```bash
# Install in dev mode
pip install -e .

# Test commands
ia-concerts --version
ia-concerts download "Billy Strings" 2019-09-28 --verbose
ia-concerts update-tags "Billy Strings" --dry-run
```

### Debugging
```bash
# Enable verbose logging
ia-concerts download "Artist" --verbose

# Check metadata cache
cat "Artist/.metadata.yaml"

# Check logs in real-time
ia-concerts update-tags "Artist" -v 2>&1 | grep -i error
```

## Next Steps (Remaining Work)

**Phase 6: Testing & Documentation** (5 todos, 0% complete)
- Unit tests for parsers
- Integration tests
- End-to-end tests
- Type hints and docstrings
- README updates

**Phase 7: Deployment** (4 todos, 0% complete)
- pipx installation support
- Validation against Bash outputs (✅ mostly done)
- Migration guide
- Final documentation

## Important Files

### Core Modules
- `config.py` - All constants, patterns, scoring weights
- `metadata.py` - Internet Archive API integration, caching
- `downloader.py` - Download logic with deduplication
- `tagger.py` - ID3 tagging with mutagen
- `parsers/*_parser.py` - XML, tracklist, filename parsing

### Documentation
- `.github/README.md` - User-facing documentation
- `.github/DEVELOPMENT.md` - Development guide
- `.github/VALIDATION.md` - Tag comparison results
- `.github/IDEMPOTENCY.md` - Idempotency test results
- `STATUS.md` - Project progress tracking

### Configuration
- `pyproject.toml` - Package configuration, dependencies
- `__main__.py` - CLI definition (Click framework)

## Related Links

- [Internet Archive Python Library](https://archive.org/developers/internetarchive/)
- [Internet Archive etree Collection](https://archive.org/details/etree)
- [Mutagen Documentation](https://mutagen.readthedocs.io/)
- [Project Repository](https://github.com/allen-ball/ia-mp3-download-and-tag)
