#!/usr/bin/env bash

set -euo pipefail

# Check if artist directory argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <artist_directory>"
    echo "Example: $0 'Billy Strings'"
    exit 1
fi

ARTIST_DIR="$1"

if [ ! -d "${ARTIST_DIR}" ]; then
    echo "Error: Directory '${ARTIST_DIR}' not found"
    exit 1
fi

echo "Updating MP3 tags in: ${ARTIST_DIR}"
echo ""

# Create a temporary file to track statistics
STATS_FILE=$(mktemp)
echo "0 0 0" > "$STATS_FILE"  # updated skipped concerts

# Cleanup function
cleanup() {
    rm -f "$STATS_FILE"
}
trap cleanup EXIT

# Function to decode HTML entities
decode_html_entities() {
    local text="$1"
    # Use sed to decode common HTML entities
    # Decode &amp; last since & is part of other entities
    echo "$text" | sed -e 's/&gt;/>/g' -e 's/&lt;/</g' -e 's/&quot;/"/g' -e "s/&apos;/'/g" -e 's/&amp;/\&/g'
}

# Function to extract year from directory name (format: "... on YYYY-MM-DD")
extract_year() {
    local dir_name="$1"
    if [[ "$dir_name" =~ on[[:space:]]([0-9]{4})-[0-9]{2}-[0-9]{2}$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Function to extract date from directory name (format: "... on YYYY-MM-DD")
extract_date() {
    local dir_name="$1"
    if [[ "$dir_name" =~ on[[:space:]]([0-9]{4}-[0-9]{2}-[0-9]{2})$ ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# Function to extract Internet Archive identifier from meta.xml file
extract_ia_identifier() {
    local concert_dir="$1"
    local identifier=""
    
    # Look for *_meta.xml file in the concert directory
    for xml_file in "$concert_dir"/*_meta.xml; do
        if [ -f "$xml_file" ]; then
            # Extract identifier from XML using grep and sed
            identifier=$(grep -m1 '<identifier>' "$xml_file" 2>/dev/null | sed -E 's/.*<identifier>([^<]+)<\/identifier>.*/\1/')
            if [ -n "$identifier" ]; then
                echo "$identifier"
                return 0
            fi
        fi
    done
    
    return 1
}

# Function to extract metadata from meta.xml file
# Returns: tag value or empty string if not found
extract_meta_xml_tag() {
    local concert_dir="$1"
    local tag_name="$2"
    local value=""
    
    # Look for *_meta.xml file in the concert directory
    for xml_file in "$concert_dir"/*_meta.xml; do
        if [ -f "$xml_file" ]; then
            # Extract tag value from XML using grep and sed
            value=$(grep -m1 "<${tag_name}>" "$xml_file" 2>/dev/null | sed -E "s/.*<${tag_name}>([^<]+)<\/${tag_name}>.*/\1/")
            if [ -n "$value" ]; then
                # Decode HTML entities
                value=$(decode_html_entities "$value")
                echo "$value"
                return 0
            fi
        fi
    done
    
    return 1
}

# Function to normalize track name (canonicalize whitespace and trim)
normalize_track_name() {
    local track_name="$1"
    # Remove duration prefix like [09:23] or [1:23:45]
    track_name=$(echo "$track_name" | sed -E 's/^\[?[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?\][[:space:]]*//')
    # Canonicalize whitespace: convert multiple spaces/tabs to single space, then trim
    track_name=$(echo "$track_name" | tr -s '[:space:]' ' ' | sed -e 's/^[[:space:]-]*//' -e 's/[[:space:]]*$//')
    # Remove trailing commas
    track_name=$(echo "$track_name" | sed -E 's/,[[:space:]]*$//')
    echo "$track_name"
}

# Function to parse track list from txt file line
# Returns: "TRACK_NUM|TRACK_NAME" or empty if no match
parse_track_line() {
    local line="$1"
    local track_num=""
    local track_name=""
    
    # Remove any carriage return characters (for Windows CRLF)
    line="${line%$'\r'}"
    
    # Try pattern 1: "01. Track" or "01: Track" or "01) Track" or "01- Track" (punctuation separator)
    if [[ "$line" =~ ^([0-9]{1,2})[\.:\)\-][[:space:]]*(.+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]}"
    # Try pattern 2: "01 - Track" (space + hyphen separator)
    elif [[ "$line" =~ ^([0-9]{1,2})[[:space:]]+-[[:space:]]*(.+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]}"
    # Try pattern 3: "01 Track" or "01  Track" (1+ spaces)
    elif [[ "$line" =~ ^([0-9]{1,2})[[:space:]]+(.+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]}"
    else
        return 1
    fi
    
    # Filter out common non-track lines (notes, technical info, etc.)
    # Skip if track name starts with certain keywords
    if [[ "$track_name" =~ ^(shntool|ffp|md5|checksum|note|source|encoding|conversion|recorded|lineage) ]]; then
        return 1
    fi
    
    # Normalize the track name
    track_name=$(normalize_track_name "$track_name")
    
    # After normalization, if track name is empty, skip
    if [ -z "$track_name" ]; then
        return 1
    fi
    
    # Remove leading zeros for track number
    track_num=$((10#$track_num))
    
    echo "${track_num}|${track_name}"
    return 0
}

# Function to parse track name from MP3 filename
# Returns: "TRACK_NUM|TRACK_NAME" or empty if no match
parse_filename_track() {
    local filename="$1"
    local track_num=""
    local track_name=""
    
    # Try pattern 1: "01 Track Name.mp3" (space separator)
    if [[ "$filename" =~ ^([0-9]{1,2})[[:space:]]+(.+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]}"
    # Try pattern 2: "01_Track_Name.mp3" (underscore separator)
    elif [[ "$filename" =~ ^([0-9]{1,2})_(.+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]//_/ }"  # Replace underscores with spaces
    # Try pattern 3: "01TrackName" (no separator, PascalCase - digits followed by capital letter)
    elif [[ "$filename" =~ ^([0-9]{1,2})([A-Z].+)$ ]]; then
        track_num="${BASH_REMATCH[1]}"
        track_name="${BASH_REMATCH[2]}"
        # Insert spaces before capital letters (convert PascalCase to Title Case)
        track_name=$(echo "$track_name" | sed -E 's/([A-Z])/ \1/g' | sed 's/^ //')
    # Try pattern 4: "Prefix_01.mp3" (track number at end)
    elif [[ "$filename" =~ ^(.+[_-])([0-9]{1,2})$ ]]; then
        track_num="${BASH_REMATCH[2]}"
        track_name="${BASH_REMATCH[1]%_}"    # Remove trailing underscore
        track_name="${track_name%-}"          # Remove trailing hyphen
    # Try pattern 5: "gd94-09-24d1t01" (date-disc-track format)
    elif [[ "$filename" =~ (d[0-9]+)?t([0-9]{1,2})$ ]]; then
        track_num="${BASH_REMATCH[2]}"
        # For this pattern, we don't have a track name, so return empty
        track_name=""
    else
        return 1
    fi
    
    # Normalize the track name
    track_name=$(normalize_track_name "$track_name")
    
    # Remove leading zeros for track number
    track_num=$((10#$track_num))
    
    echo "${track_num}|${track_name}"
    return 0
}

# Function to extract venue from directory name (format: "Artist Live at Venue on Date")
extract_venue() {
    local dir_name="$1"
    # Remove "Artist Live at " from the beginning and " on YYYY-MM-DD" from the end
    local venue=$(echo "$dir_name" | sed -E 's/^.* Live at //; s/ on [0-9]{4}-[0-9]{2}-[0-9]{2}$//')
    echo "$venue"
}

# Function to parse comma-separated setlist (format: "Set 1: Song1, Song2, Song3")
# Returns: array of track names
parse_comma_separated_setlist() {
    local txt_file="$1"
    local -a track_list=()
    
    # Detect file encoding and read appropriately
    FILE_ENCODING=$(file -I "$txt_file" | grep -o 'charset=[^[:space:]]*' | cut -d= -f2)
    READ_CMD="cat"
    if [[ "$FILE_ENCODING" =~ (iso-8859|windows-1252|us-ascii) ]]; then
        # Only convert if file is NOT already UTF-8
        READ_CMD="iconv -f WINDOWS-1252 -t UTF-8//TRANSLIT"
    fi
    
    # Read file and look for Set lines
    while IFS= read -r line || [ -n "$line" ]; do
        # Remove carriage returns
        line="${line%$'\r'}"
        
        # Match "Set N: " or "Disc N: " or "CD N: " followed by comma-separated songs
        if [[ "$line" =~ ^[[:space:]]*(Set|Disc|CD|Encore)[[:space:]]*[0-9]*:[[:space:]]*(.+)$ ]]; then
            local songs="${BASH_REMATCH[2]}"
            
            # Split by comma and process each song
            IFS=',' read -ra SONG_ARRAY <<< "$songs"
            for song in "${SONG_ARRAY[@]}"; do
                # Remove duration prefix like [09:23] if present
                song=$(echo "$song" | sed -E 's/^\[?[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?\][[:space:]]*//')
                # Normalize: trim whitespace, remove special chars like * # > ^ etc at end
                song=$(echo "$song" | sed -E -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's/[*#>^]+[[:space:]]*$//')
                # Only add non-empty songs
                if [ -n "$song" ]; then
                    track_list+=("$song")
                fi
            done
        fi
    done < <($READ_CMD "$txt_file" 2>/dev/null || cat "$txt_file")
    
    # Return the track list (one per line)
    printf '%s\n' "${track_list[@]}"
}

# Function to parse track titles from Internet Archive *_files.xml
# Returns: associative array with filename -> title mappings
# Usage: parse_xml_track_titles "/path/to/*_files.xml"
parse_xml_track_titles() {
    local xml_file="$1"
    declare -g -A XML_TRACK_TITLES
    
    [ ! -f "$xml_file" ] && return 1
    
    # Extract MP3 file entries with their titles using grep and sed
    # Look for <file name="*.mp3"> blocks and extract name and title
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
            # Decode HTML entities
            current_title=$(decode_html_entities "$current_title")
            # Store the mapping
            XML_TRACK_TITLES["$current_file"]="$current_title"
            current_file=""
        fi
    done < "$xml_file"
    
    # Return success if we found any titles
    [ ${#XML_TRACK_TITLES[@]} -gt 0 ] && return 0 || return 1
}

# Function to parse track list from txt file
parse_tracklist() {
    local txt_file="$1"
    
    # Extract lines that start with track numbers (01, 02, etc.)
    grep -E '^[0-9]{1,2}[[:space:]]' "$txt_file" 2>/dev/null || echo ""
}

# Function to get current tag value from MP3
get_tag() {
    local mp3_file="$1"
    local tag_name="$2"
    
    ffprobe -v quiet -print_format json -show_format "$mp3_file" 2>/dev/null | \
        jq -r ".format.tags.${tag_name} // \"\"" 2>/dev/null || echo ""
}

# Function to check if tags need updating
needs_update() {
    local mp3_file="$1"
    local new_artist="$2"
    local new_album="$3"
    local new_year="$4"
    local new_title="$5"
    local new_track="$6"
    local new_comment="$7"
    local new_genre="$8"
    local new_disc="$9"
    
    local current_artist=$(get_tag "$mp3_file" "artist")
    local current_album=$(get_tag "$mp3_file" "album")
    local current_date=$(get_tag "$mp3_file" "date")
    local current_title=$(get_tag "$mp3_file" "title")
    local current_track=$(get_tag "$mp3_file" "track")
    local current_comment=$(get_tag "$mp3_file" "comment")
    local current_genre=$(get_tag "$mp3_file" "genre")
    local current_disc=$(get_tag "$mp3_file" "disc")
    
    # Check if any tag differs from desired value
    if [ "$current_artist" != "$new_artist" ] || \
       [ "$current_album" != "$new_album" ] || \
       [ "$current_date" != "$new_year" ] || \
       [ "$current_title" != "$new_title" ] || \
       [ "$current_track" != "$new_track" ] || \
       [ "$current_comment" != "$new_comment" ] || \
       [ "$current_genre" != "$new_genre" ] || \
       [ "$current_disc" != "$new_disc" ]; then
        return 0  # Needs update
    else
        return 1  # No update needed
    fi
}

# Process each concert directory
CONCERT_NUM=0
for CONCERT_DIR in "${ARTIST_DIR}"/*/ ; do
    [ -d "$CONCERT_DIR" ] || continue
    
    # Remove trailing slash
    CONCERT_DIR="${CONCERT_DIR%/}"
    
    CONCERT_NUM=$((CONCERT_NUM + 1))
    CONCERT_NAME=$(basename "$CONCERT_DIR")
    
    echo "[$CONCERT_NUM] Processing: $CONCERT_NAME"
    
    # Extract metadata from XML file (priority) or directory name (fallback)
    META_TITLE=$(extract_meta_xml_tag "$CONCERT_DIR" "title")
    META_CREATOR=$(extract_meta_xml_tag "$CONCERT_DIR" "creator")
    META_DATE=$(extract_meta_xml_tag "$CONCERT_DIR" "date")
    META_YEAR=$(extract_meta_xml_tag "$CONCERT_DIR" "year")
    
    # Use metadata from XML if available, otherwise parse from directory name
    if [ -n "$META_TITLE" ]; then
        ALBUM="$META_TITLE"
    else
        # Fallback: parse from directory name
        VENUE=$(extract_venue "$CONCERT_NAME")
        DATE=$(extract_date "$CONCERT_NAME")
        ALBUM="Live at ${VENUE}"
        if [ -n "$DATE" ]; then
            ALBUM="${ALBUM} (${DATE})"
        fi
    fi
    
    if [ -n "$META_CREATOR" ]; then
        ARTIST="$META_CREATOR"
    else
        # Fallback: extract from directory name (everything before " Live at")
        ARTIST=$(echo "$CONCERT_NAME" | sed -E 's/ Live at.*//')
    fi
    
    if [ -n "$META_YEAR" ]; then
        YEAR="$META_YEAR"
    elif [ -n "$META_DATE" ]; then
        # Extract year from date (YYYY-MM-DD format)
        YEAR=$(echo "$META_DATE" | cut -d'-' -f1)
    else
        # Fallback: extract from directory name
        YEAR=$(extract_year "$CONCERT_NAME")
    fi
    
    # Extract Internet Archive identifier and construct URL
    IA_IDENTIFIER=$(extract_ia_identifier "$CONCERT_DIR")
    IA_URL=""
    if [ -n "$IA_IDENTIFIER" ]; then
        IA_URL="https://archive.org/details/${IA_IDENTIFIER}"
    fi
    
    # Find txt file with track listing (exclude checksum/metadata files)
    TXT_FILE=""
    for file in "$CONCERT_DIR"/*.txt; do
        [ -f "$file" ] || continue
        basename_file=$(basename "$file")
        # Exclude known non-tracklist files
        if [[ "$basename_file" != "md5.txt" && \
              "$basename_file" != "info.txt" && \
              "$basename_file" != "etree.txt" && \
              "$basename_file" != "shntool.txt" && \
              "$basename_file" != "fingerprint.ffp.txt" && \
              ! "$basename_file" =~ ^(md5|ffp|fingerprint|checksum) ]]; then
            TXT_FILE="$file"
            break
        fi
    done
    
    # Parse track listing from txt file if it exists, otherwise from MP3 filenames
    declare -A TRACK_NAMES
    TOTAL_DISCS=0  # Track total number of discs
    
    # First, try to find and parse Internet Archive XML files for track titles
    declare -A XML_TRACK_TITLES
    for xml_file in "$CONCERT_DIR"/*_files.xml; do
        if [ -f "$xml_file" ]; then
            if parse_xml_track_titles "$xml_file"; then
                echo "  → Found track titles in $(basename "$xml_file")"
                break  # Use the first XML file found
            fi
        fi
    done
    
    if [ -n "$TXT_FILE" ] && [ -f "$TXT_FILE" ]; then
        # Detect file encoding and read appropriately
        FILE_ENCODING=$(file -I "$TXT_FILE" | grep -o 'charset=[^[:space:]]*' | cut -d= -f2)
        READ_CMD="cat"
        if [[ "$FILE_ENCODING" =~ (iso-8859|windows-1252|us-ascii) ]]; then
            # Only convert if file is NOT already UTF-8
            READ_CMD="iconv -f WINDOWS-1252 -t UTF-8//TRANSLIT"
        fi
        
        # First pass: count total discs (also check for "Set" markers)
        max_disc=0
        max_set=0
        while IFS= read -r line || [ -n "$line" ]; do
            # Check for Disc/Disk markers
            if [[ "$line" =~ ^[[:space:]]*[Dd][Ii][Ss][CcKk][[:space:]]+([0-9]+) ]]; then
                disc_num="${BASH_REMATCH[1]}"
                disc_num=$((10#$disc_num))
                if [ "$disc_num" -gt "$max_disc" ]; then
                    max_disc=$disc_num
                fi
            # Check for Set markers (e.g., "Set 1:", "Set 2:")
            elif [[ "$line" =~ ^[[:space:]]*[Ss][Ee][Tt][[:space:]]+([0-9]+) ]]; then
                set_num="${BASH_REMATCH[1]}"
                set_num=$((10#$set_num))
                if [ "$set_num" -gt "$max_set" ]; then
                    max_set=$set_num
                fi
            fi
        done < <($READ_CMD "$TXT_FILE" 2>/dev/null || cat "$TXT_FILE")
        
        # Use whichever is greater: disc count or set count
        if [ "$max_set" -gt "$max_disc" ]; then
            TOTAL_DISCS=$max_set
        else
            TOTAL_DISCS=$max_disc
        fi
        
        # Second pass: parse tracks (handle both Unix LF and Windows CRLF line endings)
        current_disc=1
        cumulative_offset=0  # Cumulative track count from all previous discs/sets
        found_numbered_tracks=0
        
        while IFS= read -r line || [ -n "$line" ]; do
            # Detect disc/disk markers like "DISC 2", "Disc 2", or "Disk 2" (case-insensitive)
            if [[ "$line" =~ ^[[:space:]]*[Dd][Ii][Ss][CcKk][[:space:]]+([0-9]+) ]]; then
                new_disc="${BASH_REMATCH[1]}"
                if [ "$new_disc" != "$current_disc" ]; then
                    # Switching to a new disc - add current disc's track count to cumulative offset
                    current_disc_tracks=$(find "$CONCERT_DIR" -maxdepth 1 -iname "*d${current_disc}t*.mp3" -type f 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$current_disc_tracks" -gt 0 ]; then
                        cumulative_offset=$((cumulative_offset + current_disc_tracks))
                    fi
                    current_disc="$new_disc"
                fi
            # Detect set markers like "Set 1:", "Set 2:" (case-insensitive)
            elif [[ "$line" =~ ^[[:space:]]*[Ss][Ee][Tt][[:space:]]+([0-9]+) ]]; then
                new_disc="${BASH_REMATCH[1]}"
                if [ "$new_disc" != "$current_disc" ]; then
                    # Switching to a new set - add current set's track count to cumulative offset
                    # Use 's' prefix for set-based filenames (e.g., s1t01, s2t01)
                    current_set_tracks=$(find "$CONCERT_DIR" -maxdepth 1 -iname "*s${current_disc}t*.mp3" -type f 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$current_set_tracks" -eq 0 ]; then
                        # Fallback to 'd' prefix if 's' prefix not found
                        current_set_tracks=$(find "$CONCERT_DIR" -maxdepth 1 -iname "*d${current_disc}t*.mp3" -type f 2>/dev/null | wc -l | tr -d ' ')
                    fi
                    if [ "$current_set_tracks" -gt 0 ]; then
                        cumulative_offset=$((cumulative_offset + current_set_tracks))
                    fi
                    current_disc="$new_disc"
                fi
            fi
            
            if result=$(parse_track_line "$line"); then
                IFS='|' read -r track_num track_name <<< "$result"
                found_numbered_tracks=1
                # For multi-disc/set, adjust track number by cumulative offset
                if [ "$cumulative_offset" -gt 0 ]; then
                    global_track=$((cumulative_offset + track_num))
                    TRACK_NAMES[$global_track]="$track_name"
                else
                    TRACK_NAMES[$track_num]="$track_name"
                fi
            fi
        done < <($READ_CMD "$TXT_FILE" 2>/dev/null || cat "$TXT_FILE")
        
        # If no numbered tracks found, try comma-separated setlist format
        if [ "$found_numbered_tracks" -eq 0 ]; then
            mapfile -t comma_tracks < <(parse_comma_separated_setlist "$TXT_FILE")
            if [ ${#comma_tracks[@]} -gt 0 ]; then
                for i in "${!comma_tracks[@]}"; do
                    track_num=$((i + 1))
                    TRACK_NAMES[$track_num]="${comma_tracks[$i]}"
                done
            fi
        fi
    else
        # No txt file - parse track names from MP3 filenames
        for mp3_file in "$CONCERT_DIR"/*.mp3; do
            [ -f "$mp3_file" ] || continue
            mp3_basename=$(basename "$mp3_file" .mp3)
            
            if result=$(parse_filename_track "$mp3_basename"); then
                IFS='|' read -r track_num track_name <<< "$result"
                # Only store if we don't already have a name for this track
                if [ -z "${TRACK_NAMES[$track_num]:-}" ]; then
                    TRACK_NAMES[$track_num]="$track_name"
                fi
            fi
        done
    fi
    
    # If no disc info from txt, detect from filenames
    if [ "$TOTAL_DISCS" -eq 0 ]; then
        max_disc=0
        for mp3_file in "$CONCERT_DIR"/*.mp3; do
            [ -f "$mp3_file" ] || continue
            mp3_basename=$(basename "$mp3_file" .mp3)
            # Check for both 'd' (disc) and 's' (set) patterns
            if [[ "$mp3_basename" =~ [ds]([0-9]+)[tT]([0-9]{1,2}) ]]; then
                disc_num="${BASH_REMATCH[1]}"
                disc_num=$((10#$disc_num))
                if [ "$disc_num" -gt "$max_disc" ]; then
                    max_disc=$disc_num
                fi
            fi
        done
        TOTAL_DISCS=$max_disc
    fi
    
    # Count total tracks in this concert
    TOTAL_TRACKS=$(find "$CONCERT_DIR" -maxdepth 1 -name "*.mp3" -type f | wc -l | tr -d ' ')
    
    # Process each MP3 file
    CONCERT_UPDATED=0
    CONCERT_SKIPPED=0
    
    for MP3_FILE in "$CONCERT_DIR"/*.mp3; do
        [ -f "$MP3_FILE" ] || continue
        
        MP3_BASENAME=$(basename "$MP3_FILE" .mp3)
        
        # Extract track number and disc number from filename
        # Try multiple patterns: disc-track format (d/s prefix), digits at end, or at beginning
        DISC_NUM=""
        if [[ "$MP3_BASENAME" =~ [ds]([0-9]+)[tT]([0-9]{1,2}) ]]; then
            # Pattern: "...d2t01.mp3" or "...s2t01.mp3" (disc/set and track format)
            # Extract the prefix character (d or s) to determine if it's disc or set
            prefix_char="${MP3_BASENAME:${#MP3_BASENAME}-${#BASH_REMATCH[0]}:1}"
            DISC_NUM="${BASH_REMATCH[1]}"
            DISC_NUM=$((10#$DISC_NUM))
            TRACK_NUM="${BASH_REMATCH[2]}"
            TRACK_NUM_INT=$((10#$TRACK_NUM))
            
            # Calculate global track number for multi-disc/set
            if [ "$DISC_NUM" != "1" ]; then
                # Count how many tracks are on ALL previous discs/sets (cumulative)
                offset=0
                for ((prev_d=1; prev_d<DISC_NUM; prev_d++)); do
                    # Try 's' prefix first (set), then fall back to 'd' (disc)
                    prev_disc_tracks=$(find "$CONCERT_DIR" -maxdepth 1 -iname "*${prefix_char}${prev_d}t*.mp3" -type f 2>/dev/null | wc -l | tr -d ' ')
                    if [ "$prev_disc_tracks" -eq 0 ]; then
                        # Try alternative prefix
                        alt_prefix="d"
                        if [ "$prefix_char" = "d" ]; then
                            alt_prefix="s"
                        fi
                        prev_disc_tracks=$(find "$CONCERT_DIR" -maxdepth 1 -iname "*${alt_prefix}${prev_d}t*.mp3" -type f 2>/dev/null | wc -l | tr -d ' ')
                    fi
                    offset=$((offset + prev_disc_tracks))
                done
                if [ "$offset" -gt 0 ]; then
                    TRACK_NUM_INT=$((offset + TRACK_NUM_INT))
                fi
            fi
        elif [[ "$MP3_BASENAME" =~ ([0-9]{1,2})$ ]]; then
            # Pattern: "...01.mp3" or "..._01.mp3" (digits at end)
            TRACK_NUM="${BASH_REMATCH[1]}"
            TRACK_NUM_INT=$((10#$TRACK_NUM))
        elif [[ "$MP3_BASENAME" =~ ^([0-9]{1,2})[[:space:]_] ]]; then
            # Pattern: "01 Track Name.mp3" or "01_Track_Name.mp3" (digits at start)
            TRACK_NUM="${BASH_REMATCH[1]}"
            TRACK_NUM_INT=$((10#$TRACK_NUM))
        elif [[ "$MP3_BASENAME" =~ ([0-9]{1,2}) ]]; then
            # Pattern: any digits in filename (fallback)
            TRACK_NUM="${BASH_REMATCH[1]}"
            TRACK_NUM_INT=$((10#$TRACK_NUM))
        else
            echo "  ⚠ Warning: Could not extract track number from $MP3_BASENAME"
            continue
        fi
        
        # Get track name from XML, parsed txt file, or use current title
        MP3_FILENAME=$(basename "$MP3_FILE")
        TITLE=""
        
        # Priority 1: Check XML file for this specific MP3 filename
        if [ -n "${XML_TRACK_TITLES[$MP3_FILENAME]:-}" ]; then
            TITLE="${XML_TRACK_TITLES[$MP3_FILENAME]}"
        # Priority 2: Check parsed txt file track listing
        elif [ -n "${TRACK_NAMES[$TRACK_NUM_INT]:-}" ]; then
            TITLE="${TRACK_NAMES[$TRACK_NUM_INT]}"
        # Priority 3: Use current tag value if present
        else
            TITLE=$(get_tag "$MP3_FILE" "title")
            if [ -z "$TITLE" ]; then
                TITLE="Track $TRACK_NUM"
            fi
        fi
        
        # Format track number as "N/Total"
        TRACK_TAG="${TRACK_NUM_INT}/${TOTAL_TRACKS}"
        
        # Create comment with archive.org link (just the URL)
        if [ -n "$IA_URL" ]; then
            COMMENT="$IA_URL"
        else
            # Fallback if no identifier found
            COMMENT="Live concert recording - ${DATE}"
        fi
        
        # Genre
        GENRE="Bluegrass"
        
        # Format disc tag if multi-disc
        DISC_TAG=""
        if [ "$TOTAL_DISCS" -gt 1 ] && [ -n "$DISC_NUM" ]; then
            DISC_TAG="${DISC_NUM}/${TOTAL_DISCS}"
        fi
        
        # Check if update is needed
        if needs_update "$MP3_FILE" "$ARTIST" "$ALBUM" "$YEAR" "$TITLE" "$TRACK_TAG" "$COMMENT" "$GENRE" "$DISC_TAG"; then
            echo "  → Updating: $(basename "$MP3_FILE")"
            echo "     Title: $TITLE"
            echo "     Track: $TRACK_TAG"
            if [ -n "$DISC_TAG" ]; then
                echo "     Disc: $DISC_TAG"
            fi
            
            # Create temporary file for output (must keep .mp3 extension)
            TEMP_FILE="${MP3_FILE%.mp3}_TEMP_$$.mp3"
            
            # Build ffmpeg command with conditional disc tag
            # Use ID3v2.3 for better Music.app compatibility
            # Also write ID3v1 tags for maximum compatibility
            FFMPEG_CMD="ffmpeg -i \"$MP3_FILE\" -y \
                -id3v2_version 3 \
                -write_id3v1 1 \
                -metadata artist=\"$ARTIST\" \
                -metadata album=\"$ALBUM\" \
                -metadata date=\"$YEAR\" \
                -metadata title=\"$TITLE\" \
                -metadata track=\"$TRACK_TAG\" \
                -metadata comment=\"$COMMENT\" \
                -metadata genre=\"$GENRE\" \
                -metadata album_artist=\"$ARTIST\""
            
            if [ -n "$DISC_TAG" ]; then
                FFMPEG_CMD="$FFMPEG_CMD -metadata disc=\"$DISC_TAG\""
            fi
            
            FFMPEG_CMD="$FFMPEG_CMD -codec copy \"$TEMP_FILE\" -v error -hide_banner"
            
            # Update tags using ffmpeg
            if eval "$FFMPEG_CMD" 2>&1; then
                
                # Replace original file with updated version
                mv "$TEMP_FILE" "$MP3_FILE"
                
                # Set comment with proper COMM frame descriptor using mutagen
                # This ensures Music.app displays the comment correctly
                if command -v ia-set-comment.py &> /dev/null; then
                    ia-set-comment.py "$MP3_FILE" "$COMMENT" 2>/dev/null || true
                fi
                
                CONCERT_UPDATED=$((CONCERT_UPDATED + 1))
                
                # Update stats file
                read -r total_updated total_skipped total_concerts < "$STATS_FILE"
                echo "$((total_updated + 1)) $total_skipped $total_concerts" > "$STATS_FILE"
            else
                echo "     ✗ Error updating file"
                rm -f "$TEMP_FILE"
            fi
        else
            echo "  ✓ Already tagged: $(basename "$MP3_FILE")"
            CONCERT_SKIPPED=$((CONCERT_SKIPPED + 1))
            
            # Update stats file
            read -r total_updated total_skipped total_concerts < "$STATS_FILE"
            echo "$total_updated $((total_skipped + 1)) $total_concerts" > "$STATS_FILE"
        fi
    done
    
    echo "  Concert summary: $CONCERT_UPDATED updated, $CONCERT_SKIPPED skipped"
    echo ""
    
    # Update concert counter
    read -r total_updated total_skipped total_concerts < "$STATS_FILE"
    echo "$total_updated $total_skipped $((total_concerts + 1))" > "$STATS_FILE"
done

# Read final statistics
read -r TOTAL_UPDATED TOTAL_SKIPPED TOTAL_CONCERTS < "$STATS_FILE"

echo "═══════════════════════════════════════"
echo "Complete!"
echo "Total concerts processed: $TOTAL_CONCERTS"
echo "Total files updated: $TOTAL_UPDATED"
echo "Total files skipped: $TOTAL_SKIPPED"
echo "═══════════════════════════════════════"
