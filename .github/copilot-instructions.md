# Copilot Instructions for Internet Archive Concert Downloader

**Last Updated:** 2026-04-20 (Updated: ID3v2.3 for Music.app compatibility)

## Project Overview

This project contains Bash scripts for downloading and managing live concert recordings from the Internet Archive (archive.org). The scripts work together to:

1. Download concert MP3 files from Internet Archive's etree collection (with automatic deduplication)
2. Parse and update ID3 tags on downloaded MP3 files with metadata extracted from filenames and accompanying text files

**Installation**: Scripts are installed in `~/.local/bin/` for system-wide access.

## Architecture & Technologies

### Dependencies
- `ia` - Internet Archive CLI tool (https://archive.org/services/docs/api/internetarchive/cli.html)
- `jq` - JSON processor for parsing metadata
- `ffmpeg` / `ffprobe` - Audio file processing and tag reading/writing
- `iconv` - Character encoding conversion (handles Windows-1252 to UTF-8)
- **`mutagen`** - Python ID3 tagging library for proper Music.app COMM frame support ← **NEW: 2026-04-20**
  - Install: `pip3 install mutagen`
  - Required for setting ID3v2 COMM frames with content descriptors

### Script Installation

**Location**: `~/.local/bin/`

All scripts are installed in `~/.local/bin/` which should be in your PATH:
```bash
~/.local/bin/ia-build-metadata.sh
~/.local/bin/ia-download-concerts.sh
~/.local/bin/ia-update-concert-tags.sh
~/.local/bin/ia-set-comment.py         # Helper for Music.app compatibility
```

**Installation**:
```bash
# Install Python dependencies
pip3 install mutagen

# Install scripts
mkdir -p ~/.local/bin
cd /path/to/IA/scripts
cp ia-*.sh ~/.local/bin/
cp ia-set-comment.py ~/.local/bin/
chmod +x ~/.local/bin/ia-*.sh ~/.local/bin/ia-set-comment.py
```

**PATH Configuration**: Ensure `~/.local/bin` is in your PATH by adding to `~/.zshrc` or `~/.bash_profile`:
```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Core Scripts

#### `ia-build-metadata.sh` (NEW: 2026-04-19)
**Purpose**: Generate a cached metadata YAML file for a creator with scoring and deduplication

**Key Features**:
- Fetches all recordings from Internet Archive for a creator
- Scores each recording based on:
  - Completeness (MP3 track count) - 1000 points per track
  - Source quality (SBD > Matrix > Audience) - 200-500 points
  - Equipment quality (Schoeps, DPA, Neumann, etc.) - 200 points
  - Processing quality (24-bit indicators) - 100 points
  - Community ratings - 50 points per star
  - File size - minor contribution
- Groups recordings by date
- Outputs YAML file: `{Creator}/.metadata.yaml`
- Cache is valid for 7 days

**Usage**: `ia-build-metadata.sh "Billy Strings"`

**Output Structure** (`{Creator}/.metadata.yaml`):
```yaml
creator: "Billy Strings"
last_updated: "2026-04-19T22:00:00Z"
recordings:
  "2021-05-21":
    - identifier: "B.S2021-05-21.Flac"
      title: "Billy Strings Live at Waterfront Park..."
      mp3_count: 21
      source: "Schoeps MK41"
      lineage: "Audacity > Mac > Xact > Flac"
      total_size_mb: 385
      avg_rating: 4.5
      score: 21850
    - identifier: "bs2021-05-21-aud"
      mp3_count: 18
      source: "Audience"
      score: 18500
```

#### `ia-download-concerts.sh`
**Purpose**: Search and download concert recordings for a specific artist/creator from Internet Archive

**Key Features**:
- **Automatic deduplication**: Downloads only the best recording per date
- **Metadata caching**: Automatically builds/refreshes `.metadata.yaml` cache (7-day expiry)
- **Simple directory structure**: `{Creator}/{Date}/` (e.g., `Billy Strings/2021-05-21/`)
- Skips already-downloaded concerts
- Shows progress counter during batch downloads
- **Optional date filtering**: Limit downloads to specific concert dates
- **Selection transparency**: Shows how many recordings exist and why one was selected

**Usage**: 
- Download all concerts: `ia-download-concerts.sh "Billy Strings"`
- Download specific dates: `ia-download-concerts.sh "Billy Strings" 2023-10-15 2023-10-16`
- Download by month: `ia-download-concerts.sh "Phil Lesh and Friends" 2023-10`

**Important Details**:
- **Metadata Cache Workflow**:
  1. Checks if `{Creator}/.metadata.yaml` exists
  2. If missing or >7 days old, runs `ia-build-metadata.sh` automatically
  3. Parses YAML to select highest-scored recording per date
  4. Downloads only selected recordings
- **Deduplication**: When multiple recordings exist for same date:
  - Shows: `ℹ Selected best of 3 recordings (score: 21850, 21 tracks)`
  - Downloads only the highest-scored version
  - Skips lower-quality duplicates
- **Directory Naming**: `{YYYY-MM-DD}` (e.g., `2021-05-21/`) ← **UPDATED: 2026-04-20**
  - Simplified from `{date}_{identifier}` format
  - Since we deduplicate to one recording per date, identifier in path is redundant
  - Prevents duplicate downloads for the same date
- Uses `--no-directories` flag to flatten downloaded files into concert folder
- Uses pipe-separated glob patterns: `*.mp3|*.txt|*.xml|*.md5`
- **Date filtering**: Applied after deduplication selection
  - Supports full dates: `2023-10-15` matches concerts on that exact date
  - Supports partial dates: `2023-10` matches all concerts in October 2023
  - Prefix matching: Any filter date string matches start of actual date

#### `ia-update-concert-tags.sh`
**Purpose**: Update MP3 ID3 tags with concert metadata extracted from Internet Archive XML files and tracklists

**Key Features**:
- **Metadata Priority**: Extracts from `*_meta.xml` files first (artist, album, year), falls back to directory name parsing
- Parses track listings from multiple formats (see Pattern Matching section below)
- Handles multi-disc concerts with disc/track notation (e.g., `d2t01.mp3`)
- Only updates tags when changes are detected (idempotent)
- Handles Windows-1252 encoded text files with `iconv`

**Usage**: `ia-update-concert-tags.sh "Billy Strings"`

**Tag Mapping**:
- `artist` / `album_artist`: ← **UPDATED: 2026-04-20**
  - Extracted from `*_meta.xml` `<creator>` tag (priority)
  - Falls back to directory name parsing (text before "Live at")
- `album`: ← **UPDATED: 2026-04-20**
  - Extracted from `*_meta.xml` `<title>` tag (priority)
  - Falls back to constructed format: `Live at {Venue} (YYYY-MM-DD)`
- `date`: ← **UPDATED: 2026-04-20**
  - Extracted from `*_meta.xml` `<year>` tag (priority)
  - Falls back to year extracted from directory name
- `title`: Track name from XML file, txt file, or MP3 filename (see priority below)
- `track`: `{track_number}/{total_tracks}` format
- `disc`: `{disc_number}/{total_discs}` format (only for multi-disc sets) ← **NEW: Added 2026-04-19**
- `genre`: Hard-coded to "Bluegrass" (modify line 425 for other genres)
- `comment`: ← **UPDATED: 2026-04-20**
  - Extracts identifier from `*_meta.xml` and sets to: `https://archive.org/details/{identifier}`
  - Falls back to `Live concert recording - {YYYY-MM-DD}` if no identifier found
  - **Music.app Compatibility**: 
    - Uses ID3v2.3 format with `-id3v2_version 3` and `-write_id3v1 1` flags
    - After ffmpeg tagging, calls `ia-set-comment.py` to add TWO COMM frames:
      1. `COMM::XXX` - UTF-16 encoding, lang='XXX', empty descriptor
      2. `COMM::eng` - LATIN1 encoding, lang='eng', empty descriptor
    - Music.app requires BOTH frames to display comments in its UI
    - The lang='XXX' (uppercase) is critical - lowercase or missing this frame prevents display

**Track Title Priority** (NEW: 2026-04-19 Evening):
1. **XML files** (`*_files.xml`) - HIGHEST PRIORITY
   - Internet Archive metadata files with `<title>` tags for each MP3
   - Most accurate source, preserves taper's original notation
   - Includes jam band symbols: `>` (segue), `#` (tease), `@` (quote), `$` (signal)
2. **Text files** (`.txt` with tracklists) - MEDIUM PRIORITY
   - Manually created tracklists from tapers or uploaders
3. **Existing ID3 tags** / **Filenames** - FALLBACK
   - Used when no XML or text file available

#### `ia-set-comment.py` ← **NEW: 2026-04-20**
**Purpose**: Helper script to set ID3v2 COMM frames for Music.app compatibility

**Key Features**:
- Sets TWO COMM frames required by Music.app:
  1. `COMM::XXX` - UTF-16 encoding, lang='XXX' (uppercase), empty descriptor
  2. `COMM::eng` - LATIN1 encoding, lang='eng', empty descriptor
- Uses Python mutagen library for precise ID3v2 frame control
- Called automatically by `ia-update-concert-tags.sh` after ffmpeg processing
- Can be used standalone to fix existing files

**Usage**:
```bash
# Called automatically by ia-update-concert-tags.sh
# Or use manually:
ia-set-comment.py file.mp3 "https://archive.org/details/identifier"
```

**Why This Is Needed**:
- Music.app requires specific COMM frame structure to display comments
- ffmpeg cannot create the COMM::XXX frame with lang='XXX' (uppercase)
- Both COMM::XXX and COMM::eng frames are required for Music.app UI display
- This helper script uses mutagen to create the proper COMM frame structure
- Verified by comparing with working files that display comments in Music.app

**Multi-Disc/Set Handling**:
- For filenames with disc notation (`d2t01.mp3` or `d2T01.mp3`) or set notation (`s2t01.mp3`), calculates global track number
- Track 1 on disc/set 2 becomes track N+1 where N is total tracks on disc/set 1
- Supports disc markers in txt files: `DISC 2` or `Disc 2` (case-insensitive)
- **NEW (2026-04-19)**: Supports set markers in txt files: `Set 1:`, `Set 2:` (case-insensitive)
  - Treats sets the same as discs for track numbering purposes
  - Detects both "Disc N" and "Set N" markers, uses whichever count is higher
  - Example: "Set 1:" with 10 tracks, "Set 2:" with 13 tracks → 23 total tracks with disc tags 1/2 and 2/2
- **Important**: Regex and find commands are case-insensitive to handle both `dNtNN`/`sNtNN` and `dNTNN`/`sNTNN` filename patterns
  - Regex pattern: `[ds]([0-9]+)[tT]([0-9]{1,2})` matches both 'd' (disc) and 's' (set), uppercase and lowercase T
  - Find commands: Use `-iname` instead of `-name` for case-insensitive matching
- **Disc Tag** (added 2026-04-19): Automatically detects total disc/set count and adds `disc` tag
  - Detection: Counts from txt file markers ("Disc N" or "Set N") or MP3 filename patterns (`dNtNN` or `sNtNN`)
  - Format: `{disc_number}/{total_discs}` (e.g., "2/3" for disc 2 of 3)
  - Only applied when `total_discs > 1` (single-disc concerts have no disc tag)
  - Example: Phil Lesh 1998-08-08 with 3 discs → disc tags "1/3", "2/3", "3/3"
  - Example: Billy Strings 2019-09-28 with 2 sets → disc tags "1/2", "2/2"

**Internet Archive URL Extraction** ← **NEW: Added 2026-04-20**:
- Automatically extracts the Internet Archive identifier from `*_meta.xml` files
- Constructs the source URL: `https://archive.org/details/{identifier}`
- Adds to `comment` ID3v2 tag using ID3v2.3 format for Music.app compatibility
- Format: `https://archive.org/details/{identifier}` (simple URL, matching IA's format)
- Example: `https://archive.org/details/billystrings2019-09-28.dpa4022.flac16`

**Implementation (`extract_ia_identifier()` function)**:
```bash
extract_ia_identifier() {
    local concert_dir="$1"
    local identifier=""
    
    # Look for *_meta.xml file in the concert directory
    for xml_file in "$concert_dir"/*_meta.xml; do
        if [ -f "$xml_file" ]; then
            # Extract identifier from XML
            identifier=$(grep -m1 '<identifier>' "$xml_file" 2>/dev/null | \
                sed -E 's/.*<identifier>([^<]+)<\/identifier>.*/\1/')
            if [ -n "$identifier" ]; then
                echo "$identifier"
                return 0
            fi
        fi
    done
    return 1
}
```

**Usage in tagging**:
```bash
# Extract identifier and construct URL
IA_IDENTIFIER=$(extract_ia_identifier "$CONCERT_DIR")
if [ -n "$IA_IDENTIFIER" ]; then
    IA_URL="https://archive.org/details/${IA_IDENTIFIER}"
    COMMENT="$IA_URL"
else
    COMMENT="Live concert recording - ${DATE}"
fi

# Set comment using ID3v2.3 for Music.app compatibility
ffmpeg -i input.mp3 \
    -id3v2_version 3 \
    -metadata comment="$COMMENT" \
    -codec copy output.mp3
```

## Code Patterns & Conventions

### Bash Strict Mode
Both scripts use `set -euo pipefail`:
- `-e`: Exit on error
- `-u`: Exit on undefined variable
- `-o pipefail`: Pipeline fails if any command fails

### Character Encoding
**IMPORTANT:** Detect file encoding before conversion to prevent double-encoding UTF-8 files:
```bash
# Detect encoding first
FILE_ENCODING=$(file -I "$file" | grep -o 'charset=[^[:space:]]*' | cut -d= -f2)
READ_CMD="cat"
if [[ "$FILE_ENCODING" =~ (iso-8859|windows-1252|us-ascii) ]]; then
    # Only convert if file is NOT already UTF-8
    READ_CMD="iconv -f WINDOWS-1252 -t UTF-8//TRANSLIT"
fi

# Use READ_CMD to read the file
while IFS= read -r line; do
    # process line
done < <($READ_CMD "$file" 2>/dev/null || cat "$file")
```

**Why this matters:** Blindly converting UTF-8 files with iconv causes double-encoding where characters like `'` (U+2019) become corrupted to `â€™`.

### XML Parsing (Internet Archive Metadata) ← **NEW: Added 2026-04-19 Evening**

Internet Archive downloads include `*_files.xml` metadata files that contain accurate track titles. The script now prioritizes these over text files and filenames.

**XML Structure:**
```xml
<file name="jrad2018-11-11.cmc621.cmc64.sbd.matrix-s1t02.mp3" source="derivative">
    <creator>Joe Russo's Almost Dead</creator>
    <title>Lady with a Fan -&gt; Jam @ -&gt; Terrapin Station -&gt;</title>
    <track>02</track>
    <album>2018-11-11 Fox Theater, Oakland, CA</album>
    ...
</file>
```

**Parsing Strategy:**
1. Find `*_files.xml` in concert directory
2. Extract `<file name="*.mp3">` entries
3. Extract corresponding `<title>` tags
4. Decode HTML entities: `&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&`
5. Store filename → title mappings in associative array
6. Match MP3 filenames during processing

**Implementation (`parse_xml_track_titles()` function):**
```bash
parse_xml_track_titles() {
    local xml_file="$1"
    declare -g -A XML_TRACK_TITLES
    
    [ ! -f "$xml_file" ] && return 1
    
    local current_file=""
    local current_title=""
    
    while IFS= read -r line; do
        # Check for MP3 file entry
        if [[ "$line" =~ \<file\ name=\"([^\"]+\.mp3)\" ]]; then
            current_file="${BASH_REMATCH[1]}"
            current_title=""
        # Extract title (decode HTML entities)
        elif [[ "$line" =~ \<title\>([^\<]+)\</title\> ]] && [ -n "$current_file" ]; then
            current_title="${BASH_REMATCH[1]}"
            # Decode common HTML entities
            current_title="${current_title//&gt;/>}"
            current_title="${current_title//&lt;/<}"
            current_title="${current_title//&amp;/&}"
            # Store the mapping
            XML_TRACK_TITLES["$current_file"]="$current_title"
            current_file=""
        fi
    done < "$xml_file"
    
    [ ${#XML_TRACK_TITLES[@]} -gt 0 ] && return 0 || return 1
}
```

**Key Details:**
- **Global associative array**: `declare -g -A XML_TRACK_TITLES` makes the array accessible to calling scope
- **HTML entity decoding**: Preserves symbols critical to jam band notation
- **Filename matching**: Uses exact basename of MP3 file as key
- **Error handling**: Returns 1 if file not found or no titles extracted

**Jam Band Notation Symbols:**
- `>` (segue) - Song flows directly into next without stopping
- `#` (tease) - Brief musical quote or reference to another song
- `@` (quote) - Longer musical quote or jam within a song
- `$` (signal) - Band signal or cue
- `->` (arrow) - Common alternative notation for segue

**Example Results:**
- File: `jrad2018-11-11.cmc621.cmc64.sbd.matrix-s1t02.mp3`
- XML title: `Lady with a Fan -&gt; Jam @ -&gt; Terrapin Station -&gt;`
- Decoded title: `Lady with a Fan -> Jam @ -> Terrapin Station ->`

This preserves the original taper's notation exactly as documented in the Internet Archive metadata.

### Track Name Normalization
The `normalize_track_name()` function in update script:
1. Removes duration prefixes: `[09:23]` or `[1:23:45]`
2. Canonicalizes whitespace (multiple spaces → single space)
3. Trims leading/trailing whitespace and hyphens
4. Removes trailing commas

Apply this pattern when parsing track listings from any source.

### Pattern Matching for Track Numbers

#### When Parsing Track Numbers from Text Files

Support multiple formats with fallback precedence:

**Pattern 1: Punctuation separator** (most common, checked first)
- `01. Track Name` - period + space
- `01: Track Name` - colon + space
- `01) Track Name` - closing paren + space
- `01- Track Name` - hyphen + space ← **Added 2026-04-19 for Grateful Mondays**

Implementation:
```bash
if [[ "$line" =~ ^([0-9]{1,2})[\.:\)\-][[:space:]]*(.+)$ ]]; then
```

**Pattern 2: Spaced hyphen separator**
- `01 - Track Name` - digit, space, hyphen, space

Implementation:
```bash
elif [[ "$line" =~ ^([0-9]{1,2})[[:space:]]+-[[:space:]]*(.+)$ ]]; then
```

**Pattern 3: Multiple spaces**
- `01  Track Name` - 2+ spaces between number and name

Implementation:
```bash
elif [[ "$line" =~ ^([0-9]{1,2})[[:space:]]{2,}(.+)$ ]]; then
```

**Tested Formats by Artist:**
- **Billy Strings**: `01. Track Name` (period separator)
- **Grateful Mondays**: `01- Track Name` (hyphen separator)
- **Phil Lesh and Friends**: (format TBD - needs verification)

#### When Parsing Track Numbers from MP3 Filenames

The script supports these filename patterns:
1. Space separator: `01 Track Name.mp3`
2. Underscore separator: `01_Track_Name.mp3`
3. **PascalCase without separator**: `01TrackName.mp3` (converts to "Track Name")
4. Track at end: `Prefix_01.mp3`
5. **Disc-track format**: `d2t01.mp3` or `d2T01.mp3` (case-insensitive)

**Important for Multi-Disc**: The regex pattern uses `d([0-9]+)[tT]([0-9]{1,2})` to match both lowercase and uppercase T variants in filenames.

**PascalCase Handling**: For filenames like `01TurmoilAndTinfoil.mp3`, the script:
- Detects digits immediately followed by capital letter: `^([0-9]{1,2})([A-Z].+)$`
- Converts to Title Case by inserting spaces before capitals: "Turmoil And Tinfoil"
- Uses `sed -E 's/([A-Z])/ \1/g'` to split on capital letters

### ffmpeg Tag Updates
Always use:
- `-codec copy` to avoid re-encoding (preserves audio quality)
- `-y` to overwrite without prompting
- `-v error -hide_banner` to suppress verbose output
- Temporary file pattern: `${file%.mp3}_TEMP_$$.mp3` (PID ensures uniqueness)
- Conditional metadata: Build ffmpeg command with disc tag only when `TOTAL_DISCS > 1`

### Directory Name Parsing
Expected format: `{Artist} Live at {Venue} on YYYY-MM-DD`

Regex patterns:
- Year: `on[[:space:]]([0-9]{4})-[0-9]{2}-[0-9]{2}$`
- Date: `on[[:space:]]([0-9]{4}-[0-9]{2}-[0-9]{2})$`
- Venue: Remove prefix/suffix from directory name

## Common Maintenance Tasks

### Adding New Genre Support
Modify line 419 in `ia-update-concert-tags.sh`:
```bash
GENRE="Bluegrass"  # Change to "Rock", "Jazz", etc., or pass as parameter
```

Consider adding genre as a script parameter:
```bash
GENRE="${2:-Bluegrass}"  # Default to Bluegrass if not provided
```

### Supporting Additional Filename Formats
To support new MP3 filename patterns, modify `parse_filename_track()` function around lines 113-148.

Always:
1. Add regex pattern with track number capture group
2. Extract and clean track name (handle underscores, PascalCase, etc.)
3. Return format: `${track_num}|${track_name}`
4. Apply `normalize_track_name()` to parsed name before returning

For PascalCase conversion, use: `sed -E 's/([A-Z])/ \1/g' | sed 's/^ //'`

### Supporting Additional Text File Formats
Add new patterns to `parse_track_line()` function around line 66-108 in update script.

Always:
1. Add regex pattern with track number capture group
2. Return format: `${track_num}|${track_name}`
3. Apply `normalize_track_name()` to parsed name
4. Filter out non-track lines (technical info, notes)

**Example: Adding tab separator support**
```bash
# Pattern 4: Tab separator
elif [[ "$line" =~ ^([0-9]{1,2})[[:space:]]*$'\t'[[:space:]]*(.+)$ ]]; then
    track_num="${BASH_REMATCH[1]}"
    track_name="${BASH_REMATCH[2]}"
```

### Excluding Non-Tracklist Files
Update the exclusion list around line 275-282:
```bash
if [[ "$basename_file" != "md5.txt" && \
      "$basename_file" != "info.txt" && \
      "$basename_file" != "etree.txt" && \
      # Add new patterns here
```

### Debugging Tag Parsing
To see what tags would be applied without modifying files:
1. Comment out the `ffmpeg` command (lines 431-442)
2. Keep the echo statements to see extracted metadata
3. Run on a single concert directory

**Debug workflow:**
```bash
# 1. Check text file format
cat "Artist/Concert Dir/*.txt" | grep -E "^[0-9]{1,2}"

# 2. Test regex pattern manually
line="01- Track Name"
if [[ "$line" =~ ^([0-9]{1,2})[\.:\)\-][[:space:]]*(.+)$ ]]; then
    echo "Match: ${BASH_REMATCH[1]} | ${BASH_REMATCH[2]}"
fi

# 3. Check current tags
ffprobe -v quiet -print_format json -show_format "file.mp3" | jq .format.tags

# 4. Run update script
ia-update-concert-tags.sh "Artist"

# 5. Verify results
ffprobe -v quiet -print_format json -show_format "file.mp3" | jq .format.tags
```

## Testing Considerations

### Unit Testing Approaches
Key functions to test in isolation:
- `parse_track_line()`: Various line formats
- `parse_filename_track()`: Different filename patterns  
- `normalize_track_name()`: Whitespace and special char handling
- `extract_year()`, `extract_date()`, `extract_venue()`: Directory parsing

### Integration Testing
1. Test with minimal dataset (1-2 concerts)
2. Verify downloaded directory structure
3. Run update script and verify tags with: `ffprobe -v quiet -print_format json -show_format file.mp3 | jq .format.tags`
4. Re-run update script (should skip all files - idempotent check)

### Edge Cases to Handle
- Missing or malformed text files
- Non-standard directory naming
- Multi-disc concerts
- Special characters in track names (unicode, punctuation)
- Truncated/incomplete downloads
- Files already tagged by other tools
- **PascalCase filenames without separators** (e.g., `01TurmoilAndTinfoil.mp3`)
- camelCase filenames (currently not supported, would need lowercase detection)
- **Various track numbering formats** (`01.`, `01:`, `01)`, `01-`, `01 - `)

## Performance Notes

- Download script processes items sequentially (one API call per concert)
- Update script processes concerts/tracks sequentially but checks tags before updating
- Tag checking with `ffprobe` is fast; only files needing updates incur ffmpeg overhead
- Character encoding conversion (`iconv`) adds minimal overhead

## Troubleshooting

### Common Issues and Solutions

**Issue: Multiple recordings for the same date downloaded**
- **Cause**: Old version of script without deduplication
- **Solution**: Delete old downloads and re-run with new script (automatically selects best per date)
- **Check**: Metadata cache at `{Creator}/.metadata.yaml` shows all available recordings and scores

**Issue: Metadata cache is stale**
- **Symptom**: New recordings on Internet Archive not appearing in downloads
- **Solution**: Delete `{Creator}/.metadata.yaml` - will rebuild automatically on next download
- **Manual refresh**: `ia-build-metadata.sh "Artist Name"`
- **Auto-refresh**: Cache automatically refreshes after 7 days

**Issue: Want to manually select different recording for a date**
- **Solution**: Edit `{Creator}/.metadata.yaml` and swap the order (first recording listed is selected)
- **Alternative**: Delete the `.metadata.yaml` file and adjust scoring logic in `ia-build-metadata.sh`

**Issue: Download script selects lower-quality recording**
- **Cause**: Scoring algorithm may not match your preferences
- **Solution**: Adjust scoring in `ia-build-metadata.sh` (lines with `score=` calculations)
  - Increase points for specific qualities (e.g., +1000 for "Schoeps" instead of +200)
  - Delete `.metadata.yaml` and re-run to regenerate with new scoring

**Issue: Tracks have generic titles like "Track 01"**
- **Cause**: Text file format not recognized by `parse_track_line()` and no XML file available
- **Solution**: Check for `*_files.xml` file first (most accurate source), then check text file format
- **Priority**: XML > Text > Filename/Tags
- **Example**: Fixed 2026-04-19 for Grateful Mondays `01- ` format

**Issue: Song titles missing jam band notation (>, #, @, $)**
- **Cause**: Parsing from text files or filenames instead of XML metadata
- **Solution**: Ensure `*_files.xml` exists in concert directory (should be downloaded by `ia-download-concerts.sh`)
- **Example**: Added XML parsing 2026-04-19 Evening - "Lady with a Fan -> Jam @ -> Terrapin Station ->"

**Issue: No text file found**
- **Cause**: File might be in exclusion list or wrong extension
- **Solution**: Check exclusion list (lines 275-290), verify .txt file exists

**Issue: Wrong track numbers on multi-disc concerts**
- **Cause 1**: Disc markers not recognized in text file
- **Solution 1**: Add disc marker pattern to parsing logic
- **Cause 2**: Case sensitivity mismatch between regex/find patterns and actual filenames
- **Solution 2**: Use case-insensitive matching (`-iname` for find, `[tT]` for regex)
- **Example**: Fixed 2026-04-19 for Grateful Mondays files using uppercase T (`d2T01.mp3`)

**Issue: Character encoding errors (garbled UTF-8 characters)**
- **Symptom**: Special characters like apostrophes display as `â€™` instead of `'`
- **Cause**: Double-encoding - applying iconv to files already in UTF-8
- **Solution**: Detect file encoding before conversion (see Character Encoding section)
- **Verification**: Check file encoding with `file -I filename.txt`

**Issue: Wrong track names in set-based concerts**
- **Symptom**: Set 1 tracks have Set 2 song names (or vice versa)
- **Cause**: Text file uses "Set 1:", "Set 2:" markers but filenames use `s1t01`, `s2t01` pattern
- **Solution**: Script now detects Set markers alongside Disc markers (fixed 2026-04-19)
- **Example**: Billy Strings concerts with `sNtNN` filename pattern

**Issue: Comments not displaying in Music.app**
- **Symptom**: Archive.org URL is in the MP3 file metadata but doesn't appear in Music.app Comments field
- **Cause**: Music.app requires specific COMM frame structure with both `COMM::XXX` and `COMM::eng` frames
- **Solution**: Ensure using current version with `ia-set-comment.py` helper script (added 2026-04-20)
- **Manual fix**: Run `ia-set-comment.py file.mp3 "https://archive.org/details/identifier"`
- **Re-tag all**: Run `ia-update-concert-tags.sh "Artist Name"` to update all files in artist directory
- **Verification**: Check with `exiftool file.mp3 | grep Comment` - should see both "Comment-xxx" and "Comment" lines

## Future Enhancements

Potential improvements to suggest:
- [ ] Add parallel download support with `xargs -P`
- [ ] Support resuming interrupted downloads
- [ ] Extract genre from Internet Archive metadata instead of hard-coding
- [ ] Add dry-run mode for update script
- [ ] Support for FLAC files in addition to MP3
- [ ] Artist name normalization (handle "feat.", "with", etc.)
- [x] Disc number tag for multi-disc sets ← **COMPLETED 2026-04-19**
- [ ] Preserve original tags in backup before modifying
- [ ] Configuration file for genre mapping by artist
- [x] Support comma-separated setlists: `Set 1: Song1, Song2, Song3` ← **Already supported**
- [x] Parse track titles from Internet Archive XML metadata ← **COMPLETED 2026-04-19 Evening**

## Change Log

### 2026-04-19 Late Evening (Metadata Cache & Deduplication System) ← **NEW**
- **Added**: Complete metadata caching and deduplication system
- **New Script**: `ia-build-metadata.sh`
  - Fetches all recordings for a creator from Internet Archive
  - Scores recordings based on multiple quality factors
  - Groups by date and outputs structured YAML cache
  - Cache stored at: `{Creator}/.metadata.yaml`
  - Cache valid for 7 days, auto-refreshes when stale
- **Modified**: `ia-download-concerts.sh`
  - Now automatically uses metadata cache for deduplication
  - Checks cache age and rebuilds if >7 days old
  - Selects highest-scored recording per date
  - Shows selection rationale: "Selected best of 3 recordings (score: 21850, 21 tracks)"
  - New directory naming: `{YYYY-MM-DD}_{identifier}/` (e.g., `2021-05-21_B.S2021-05-21.Flac/`)
  - Backward compatible: detects old directory names to avoid re-downloads
- **Scoring Algorithm**:
  - MP3 count: 1000 points per track (completeness is highest priority)
  - Soundboard source: +500 points
  - Matrix source: +300 points
  - Quality mics (Schoeps, DPA, Neumann, AKG, Earthworks): +200 points
  - High-res processing (24-bit): +100 points
  - Community rating: 50 points per star
  - File size: +1 point per 10MB (minor tiebreaker)
- **Benefits**:
  - Avoids downloading duplicate recordings of same concert
  - Automatically selects best quality version
  - Faster subsequent runs (no repeated API calls)
  - Human-readable YAML can be manually edited
  - Transparent selection process
- **Files Created**: `ia-build-metadata.sh` (new)
- **Files Modified**: `ia-download-concerts.sh`
- **Renamed Scripts**: 
  - `download-ia-concerts.sh` → `ia-download-concerts.sh`
  - `update-concert-tags.sh` → `ia-update-concert-tags.sh`

### 2026-04-19 (XML Track Title Parsing) ← **NEW**
- **Added**: Internet Archive XML metadata parsing for track titles
- **Feature**: Script now prioritizes `*_files.xml` files as the most accurate source for track titles
- **Motivation**: 
  - Internet Archive downloads include XML metadata with original taper's track titles
  - Preserves jam band notation symbols: `>` (segue), `#` (tease), `@` (quote), `$` (signal)
  - More accurate than parsing text files or inferring from filenames
- **Implementation**:
  - New function: `parse_xml_track_titles()` (lines 206-240)
  - Searches for `*_files.xml` in each concert directory
  - Extracts `<file name="*.mp3">` and `<title>` tags
  - Decodes HTML entities: `&gt;` → `>`, `&lt;` → `<`, `&amp;` → `&`
  - Stores filename → title mappings in global associative array `XML_TRACK_TITLES`
- **Track Title Priority** (updated lines 498-514):
  1. XML files (`*_files.xml`) - HIGHEST PRIORITY
  2. Text files (`.txt` tracklists) - MEDIUM PRIORITY
  3. Existing ID3 tags / filenames - FALLBACK
- **Files Modified**: `ia-update-concert-tags.sh`
  - Lines 206-240: New `parse_xml_track_titles()` function
  - Lines 303-312: Check for XML files before processing txt files
  - Lines 498-514: Updated title selection logic with XML priority
- **Coverage**: All 8 concert directories in current collection have XML files
- **Examples**:
  - Joe Russo's Almost Dead: "Lady with a Fan -> Jam @ -> Terrapin Station ->"
  - Billy Strings: "I've Just Seen The Rock Of Ages"
  - Preserves all segue symbols and jam notation accurately
- **Backward Compatibility**: Script still works for concerts without XML files

### 2026-04-19 (Set Parsing and UTF-8 Encoding Fix)
- **Fixed**: Set marker support for concerts organized by sets rather than discs
- **Issue**: Text files with "Set 1:", "Set 2:" headers were not being recognized, causing incorrect track parsing
- **Example**: Billy Strings 2019-09-28 had filenames `s1t01.mp3`, `s2t01.mp3` but script only looked for `d` (disc) prefix
- **Solution**: Added "Set N" marker detection alongside existing "Disc N" detection
  - Updated first pass disc counting to also check for Set markers (lines 299-333)
  - Updated second pass track parsing to handle Set markers with cumulative offset (lines 335-379)
  - Updated filename pattern matching to recognize both `d` and `s` prefixes: `[ds]([0-9]+)[tT]`
  - Updated MP3 processing to calculate offsets for both disc and set prefixes (lines 418-432, 447-483)
- **Fixed**: UTF-8 encoding corruption in track titles with special characters
- **Issue**: Script was converting all files from WINDOWS-1252 to UTF-8, even files already in UTF-8
- **Impact**: UTF-8 characters like `'` (U+2019 RIGHT SINGLE QUOTATION MARK) were double-encoded to `â€™`
- **Examples**: 
  - "Daddy's Grave" was corrupted to "Daddyâ€™s Grave"
  - "Everything's The Same" was corrupted to "Everythingâ€™s The Same"
- **Solution**: Added encoding detection before conversion
  - Uses `file -I` command to detect charset
  - Only applies iconv conversion for non-UTF-8 files (windows-1252, iso-8859, us-ascii)
  - UTF-8 files are read directly with `cat` to preserve encoding
  - Applied to all file reading locations (lines 299-333, 335-379, parse_comma_separated_setlist function)
- **Files Modified**: `ia-update-concert-tags.sh`
- **Result**: 
  - Set-based concerts now parse correctly with proper track names and disc tags
  - UTF-8 characters in track titles are preserved correctly
  - Billy Strings 2019-09-28: Set 1 track 1 is "Likes of Me >" (not "intro"), Set 2 track 1 is "intro"
  - Special characters display correctly: "Daddy's Grave", "Everything's The Same", "I'm Still Here"

### 2026-04-19 (Download Script Enhancement)
- **Added**: Date filtering feature to `ia-download-concerts.sh`
- **Usage**: Accept additional arguments after creator name as date filters
- **Feature**: Only downloads concerts matching specified dates (uses prefix matching)
- **Examples**:
  - `ia-download-concerts.sh "Billy Strings" 2023-10-15` - single date
  - `ia-download-concerts.sh "Billy Strings" 2023-10-15 2023-10-16` - multiple dates
  - `ia-download-concerts.sh "Phil Lesh" 2023-10` - entire month
- **Behavior**: 
  - Extracts `metadata.date` from each concert's Internet Archive metadata
  - Compares against provided date filters using prefix matching
  - Skips concerts without date metadata or non-matching dates
  - Displays which dates are being filtered and skip reasons
- **Files Modified**: `ia-download-concerts.sh`
  - Lines 6-17: Updated usage and argument parsing
  - Lines 21-24: Display date filters if provided
  - Lines 43-62: Date matching logic with skip messages

### 2026-04-19
- **Fixed**: Added support for `01- Track Name` format (hyphen immediately followed by space)
- **Affected**: Grateful Mondays concerts now parse correctly
- **File Modified**: `ia-update-concert-tags.sh` line 75
- **Change**: Added `\-` to Pattern 1 character class: `[\.:\)\-]`

### 2026-04-19 (Evening)
- **Fixed**: Case sensitivity bug causing track duplication in multi-disc concerts
- **Root Cause**: Script looked for lowercase `t` in disc-track filenames (`d1t01.mp3`) but Grateful Mondays files use uppercase `T` (`d1T01.mp3`)
- **Impact**: Disc 2 tracks were numbered 1-7 instead of 8-14, causing duplicates in music players
- **Files Modified**: `ia-update-concert-tags.sh`
  - **Line 306**: Changed `-name` to `-iname` for case-insensitive file search during txt parsing
  - **Line 367**: Changed regex from `d([0-9]+)t` to `d([0-9]+)[tT]` to match both cases
  - **Line 378**: Changed `-name` to `-iname` for case-insensitive file search during MP3 processing
- **Result**: Multi-disc concerts now correctly number tracks sequentially (disc 2 track 1 = global track 8)

### 2026-04-19 (Late Evening)
- **Added**: Disc number tag support for multi-disc concert sets
- **Feature**: Script now detects total disc count and adds `disc` metadata tag
- **Detection Methods**:
  1. Counts "Disc N" / "Disk N" markers in txt files (case-insensitive)
  2. Falls back to detecting highest disc number from MP3 filenames (`dNtNN` pattern)
- **Tag Format**: `{disc_number}/{total_discs}` (e.g., "2/3" for disc 2 of 3)
- **Behavior**: Only adds disc tag when `TOTAL_DISCS > 1` (skips single-disc concerts)
- **Files Modified**: `ia-update-concert-tags.sh`
  - **Lines 293-314**: Added first pass to count total discs from txt file
  - **Lines 352-366**: Added fallback disc detection from MP3 filenames
  - **Line 369**: Modified to track `DISC_NUM` variable separately
  - **Lines 216-244**: Updated `needs_update()` function to check disc tag
  - **Lines 428-447**: Modified ffmpeg command to conditionally include disc metadata
- **Impact**: Multi-disc concerts now have proper disc tags for better organization in music players
- **Example**: Phil Lesh 1998-08-08 show with 3 discs now tagged as "1/3", "2/3", "3/3"

## Common Use Cases

### Download Specific Concert Dates
When you know specific dates you want to download:
```bash
# Single show
ia-download-concerts.sh "Billy Strings" 2023-10-15

# Multiple specific shows
ia-download-concerts.sh "Phil Lesh and Friends" 1998-08-08 1999-05-15 2000-03-20

# All shows from a specific month
ia-download-concerts.sh "Grateful Mondays" 2015-05

# All shows from a specific year
ia-download-concerts.sh "Billy Strings" 2023
```

The date filter uses prefix matching, so:
- `2023` matches any date starting with "2023" (entire year)
- `2023-10` matches any date starting with "2023-10" (entire month)
- `2023-10-15` matches exact date

### Workflow for Selective Downloads
1. Download specific concerts by date (automatically uses best quality):
   ```bash
   ia-download-concerts.sh "Billy Strings" 2023-10-15 2023-10-16
   ```
2. Update tags for downloaded concerts:
   ```bash
   ia-update-concert-tags.sh "Billy Strings"
   ```

### Manual Metadata Cache Management
```bash
# Force rebuild metadata cache (e.g., after new recordings uploaded to IA)
rm "Billy Strings/.metadata.yaml"
ia-build-metadata.sh "Billy Strings"

# View current cache
cat "Billy Strings/.metadata.yaml"

# Check cache age
ls -lh "Billy Strings/.metadata.yaml"
```

## Related Files and Locations

**Script Location**: `~/.local/bin/` ← **UPDATED: 2026-04-20**
- Scripts are installed system-wide for access from any directory
- Run commands from your working directory (where artist folders are located)
- Example working directory: `/Volumes/SSD/Music/Downloads/IA/`

**Script Files**:
- `~/.local/bin/ia-build-metadata.sh` - Builds metadata cache with scoring ← **NEW: 2026-04-19**
  - Fetches all recordings from Internet Archive
  - Scores based on quality factors
  - Outputs YAML cache for deduplication
- `~/.local/bin/ia-download-concerts.sh` - Downloads concerts from Internet Archive
  - Uses metadata cache for deduplication ← **UPDATED: 2026-04-19**
  - Auto-refreshes cache if >7 days old
  - Downloads `*.xml` files alongside MP3s for metadata
- `~/.local/bin/ia-update-concert-tags.sh` - Main tagging script
  - Lines 52-69: `extract_ia_identifier()` - Extract identifier from meta.xml ← **NEW: 2026-04-20**
  - Lines 70-80: `normalize_track_name()` - Track name cleanup
  - Lines 82-124: `parse_track_line()` - Text file parsing
  - Lines 126-167: `parse_filename_track()` - Filename parsing
  - Lines 220-254: `parse_xml_track_titles()` - XML metadata parsing ← **NEW: 2026-04-19 Evening**
  - Lines 280-313: `needs_update()` - Tag comparison including disc tag ← **UPDATED: 2026-04-20**
  - Lines 343-348: Internet Archive identifier and URL extraction ← **NEW: 2026-04-20**
  - Lines 360-379: XML file discovery and parsing ← **NEW: 2026-04-19 Evening**
  - Lines 593-606: Comment construction with IA URL ← **NEW: 2026-04-20**
  - Lines 673-690: ffmpeg command with ID3v2.3 format and disc metadata ← **UPDATED: 2026-04-20**
  - Line 603: Genre assignment

**Documentation Files** (in working directory):
- `COPILOT_INSTRUCTIONS.md` - Main documentation (this file)
- `COPILOT_INSTRUCTIONS_UPDATE.md` - Detailed update notes

**Data Files** (in working directory):
- `{Creator}/.metadata.yaml` - Cached metadata for deduplication
- Text files in concert directories - Source of track metadata (secondary priority)
- `*_files.xml` in concert directories - Internet Archive metadata (primary priority for track titles)
- `*_meta.xml` in concert directories - Internet Archive metadata with identifier for source URL ← **NEW: 2026-04-20**

