#!/usr/bin/env bash

set -euo pipefail

# Check if creator argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <creator_name>"
    echo "Example: $0 'Billy Strings'"
    exit 1
fi

CREATOR="$1"
BASE_DIR="${CREATOR}"
METADATA_FILE="${BASE_DIR}/.metadata.yaml"

# Create base directory for the creator
mkdir -p "${BASE_DIR}"

echo "Building metadata cache for ${CREATOR}..."
echo "This may take a few minutes depending on the number of recordings..."

# Search for items and get identifiers
ITEMS=$(ia search "creator:\"${CREATOR}\" AND mediatype:etree AND format:MP3" --itemlist)

if [ -z "${ITEMS}" ]; then
    echo "No items found for creator: ${CREATOR}"
    exit 0
fi

TOTAL_ITEMS=$(echo "${ITEMS}" | wc -l | tr -d ' ')
echo "Found ${TOTAL_ITEMS} recordings to process"

# Temporary file to store all metadata
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT

# Function to score a recording
score_recording() {
    local metadata_file="$1"
    local score=0
    
    # Count MP3 files (highest priority - 1000 points each)
    local mp3_count=$(jq -r '[.files[] | select(.format == "VBR MP3" or .format == "MP3")] | length' "$metadata_file")
    score=$((score + mp3_count * 1000))
    
    # Source quality (500 points for soundboard, 300 for matrix, 200 for quality mics)
    local source=$(jq -r '.metadata.source // ""' "$metadata_file" | tr '[:upper:]' '[:lower:]')
    if [[ "$source" =~ sbd|soundboard ]]; then
        score=$((score + 500))
    elif [[ "$source" =~ matrix ]]; then
        score=$((score + 300))
    fi
    
    # Quality microphones (200 points)
    if [[ "$source" =~ schoeps|dpa|neumann|akg|earthworks ]]; then
        score=$((score + 200))
    fi
    
    # Lineage quality (100 points for high-res indicators)
    local lineage=$(jq -r '.metadata.lineage // ""' "$metadata_file" | tr '[:upper:]' '[:lower:]')
    if [[ "$lineage" =~ 24bit|24/|96k|24-bit ]]; then
        score=$((score + 100))
    fi
    
    # Community rating (50 points per star if available)
    local avg_rating=$(jq -r '.metadata.avg_rating // "0"' "$metadata_file")
    if [[ "$avg_rating" != "null" && "$avg_rating" != "0" ]]; then
        # Convert to integer (multiply by 50)
        local rating_score=$(echo "$avg_rating * 50" | bc | cut -d. -f1)
        score=$((score + rating_score))
    fi
    
    # Total MP3 file size (small contribution - 1 point per 10MB)
    local total_size=$(jq '[.files[] | select(.format == "VBR MP3" or .format == "MP3") | (.size | tonumber)] | add // 0' "$metadata_file")
    local size_mb=$((total_size / 1024 / 1024))
    score=$((score + size_mb / 10))
    
    echo "$score"
}

# Fetch metadata for all items (with progress)
echo ""
echo "Fetching metadata..."
CURRENT=0
while IFS= read -r IDENTIFIER; do
    CURRENT=$((CURRENT + 1))
    echo -ne "\r  Progress: [$CURRENT/$TOTAL_ITEMS] ${IDENTIFIER}                    "
    
    ia metadata "${IDENTIFIER}" > "${TEMP_DIR}/${IDENTIFIER}.json" 2>/dev/null || {
        echo -e "\n  Warning: Failed to fetch metadata for ${IDENTIFIER}"
        continue
    }
done <<< "${ITEMS}"

echo -e "\n"

# Process metadata and build YAML structure
echo "Processing and scoring recordings..."

# Start YAML file
cat > "${METADATA_FILE}" << EOF
creator: "${CREATOR}"
last_updated: "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
recordings:
EOF

# Create associative array to group by date
declare -A DATE_GROUPS

# Process each metadata file
for metadata_file in "${TEMP_DIR}"/*.json; do
    [ -f "$metadata_file" ] || continue
    
    IDENTIFIER=$(basename "$metadata_file" .json)
    
    # Extract key metadata
    DATE=$(jq -r '.metadata.date // "unknown"' "$metadata_file")
    TITLE=$(jq -r '.metadata.title // .metadata.identifier // ""' "$metadata_file" | sed 's/"/\\"/g')
    SOURCE=$(jq -r '.metadata.source // ""' "$metadata_file" | sed 's/"/\\"/g')
    LINEAGE=$(jq -r '.metadata.lineage // ""' "$metadata_file" | sed 's/"/\\"/g')
    AVG_RATING=$(jq -r '.metadata.avg_rating // "null"' "$metadata_file")
    MP3_COUNT=$(jq -r '[.files[] | select(.format == "VBR MP3" or .format == "MP3")] | length' "$metadata_file")
    TOTAL_SIZE=$(jq '[.files[] | select(.format == "VBR MP3" or .format == "MP3") | (.size | tonumber)] | add // 0' "$metadata_file")
    SIZE_MB=$((TOTAL_SIZE / 1024 / 1024))
    
    # Calculate score
    SCORE=$(score_recording "$metadata_file")
    
    # Add to date group
    if [ -z "${DATE_GROUPS[$DATE]+x}" ]; then
        DATE_GROUPS[$DATE]=""
    fi
    
    # Append recording info (we'll sort later)
    DATE_GROUPS[$DATE]+="SCORE:${SCORE}|ID:${IDENTIFIER}|TITLE:${TITLE}|MP3:${MP3_COUNT}|SIZE:${SIZE_MB}|SRC:${SOURCE}|LIN:${LINEAGE}|RATING:${AVG_RATING}"$'\n'
done

# Sort dates and write to YAML
# Check if we have any dates to process
if [ ${#DATE_GROUPS[@]} -gt 0 ]; then
echo "Writing YAML for ${#DATE_GROUPS[@]} dates..."
# Temporarily disable exit on error for the YAML writing loop
set +e
DATES_WRITTEN=0
for DATE in $(echo "${!DATE_GROUPS[@]}" | tr ' ' '\n' | sort); do
    DATES_WRITTEN=$((DATES_WRITTEN + 1))
    if [ $((DATES_WRITTEN % 50)) -eq 0 ]; then
        echo "  Written $DATES_WRITTEN dates..."
    fi
    
    echo "  \"${DATE}\":" >> "${METADATA_FILE}"
    
    # Sort recordings by score (descending) and write to YAML
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        
        # Parse the pipe-delimited data
        SCORE=$(echo "$line" | grep -o 'SCORE:[^|]*' | cut -d: -f2)
        IDENTIFIER=$(echo "$line" | grep -o 'ID:[^|]*' | cut -d: -f2)
        TITLE=$(echo "$line" | grep -o 'TITLE:[^|]*' | cut -d: -f2-)
        MP3_COUNT=$(echo "$line" | grep -o 'MP3:[^|]*' | cut -d: -f2)
        SIZE_MB=$(echo "$line" | grep -o 'SIZE:[^|]*' | cut -d: -f2)
        SOURCE=$(echo "$line" | grep -o 'SRC:[^|]*' | cut -d: -f2-)
        LINEAGE=$(echo "$line" | grep -o 'LIN:[^|]*' | cut -d: -f2-)
        AVG_RATING=$(echo "$line" | grep -o 'RATING:[^|]*' | cut -d: -f2)
        
        cat >> "${METADATA_FILE}" << EOF
    - identifier: "${IDENTIFIER}"
      title: "${TITLE}"
      mp3_count: ${MP3_COUNT}
      source: "${SOURCE}"
      lineage: "${LINEAGE}"
      total_size_mb: ${SIZE_MB}
      avg_rating: ${AVG_RATING}
      score: ${SCORE}
EOF
    done < <(echo "${DATE_GROUPS[$DATE]}" | sort -t: -k2 -rn)
done
set -e
echo "  Completed writing all $DATES_WRITTEN dates"
else
    echo ""
    echo "Warning: No recordings with valid metadata found."
fi

echo ""
if [ ${#DATE_GROUPS[@]} -gt 0 ]; then
    echo "✓ Metadata cache built successfully: ${METADATA_FILE}"
    echo ""
    echo "Summary:"
    echo "  Total recordings: ${TOTAL_ITEMS}"
    echo "  Unique dates: ${#DATE_GROUPS[@]}"
    echo ""
    echo "Cache will be used by ia-download-concerts.sh and auto-refreshes after 7 days."
else
    echo "✗ No valid recordings found to cache."
    echo "  Total items checked: ${TOTAL_ITEMS}"
    exit 1
fi
