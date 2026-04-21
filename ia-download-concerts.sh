#!/usr/bin/env bash

set -euo pipefail

# Check if creator argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <creator_name> [date1] [date2] ..."
    echo "Example: $0 'Billy Strings'"
    echo "Example: $0 'Billy Strings' 2023-10-15 2023-10-16"
    exit 1
fi

CREATOR="$1"
shift # Remove creator from arguments, leaving only dates

# Store date filters if provided
DATE_FILTERS=("$@")
BASE_DIR="${CREATOR}"
METADATA_FILE="${BASE_DIR}/.metadata.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Create base directory for the creator
mkdir -p "${BASE_DIR}"

echo "Downloading concerts by ${CREATOR}..."

# Display date filters if provided
if [ ${#DATE_FILTERS[@]} -gt 0 ]; then
    echo "Filtering by dates: ${DATE_FILTERS[*]}"
fi

# Check if metadata cache exists and is fresh (< 7 days old)
REBUILD_METADATA=false

if [ ! -f "${METADATA_FILE}" ]; then
    echo ""
    echo "Metadata cache not found. Building cache..."
    REBUILD_METADATA=true
else
    # Check if file is older than 7 days
    if [ "$(uname)" = "Darwin" ]; then
        # macOS
        FILE_AGE_SECONDS=$(( $(date +%s) - $(stat -f %m "${METADATA_FILE}") ))
    else
        # Linux
        FILE_AGE_SECONDS=$(( $(date +%s) - $(stat -c %Y "${METADATA_FILE}") ))
    fi
    
    SEVEN_DAYS_SECONDS=$((7 * 24 * 60 * 60))
    
    if [ ${FILE_AGE_SECONDS} -gt ${SEVEN_DAYS_SECONDS} ]; then
        echo ""
        echo "Metadata cache is older than 7 days. Refreshing..."
        REBUILD_METADATA=true
    else
        echo "Using metadata cache: ${METADATA_FILE}"
    fi
fi

# Rebuild metadata if needed
if [ "${REBUILD_METADATA}" = true ]; then
    "${SCRIPT_DIR}/ia-build-metadata.sh" "${CREATOR}"
    echo ""
fi

# Parse YAML and extract dates and identifiers
# Simple YAML parser for our specific structure
echo "Processing metadata..."
echo ""

# Extract all dates from metadata file
DATES=$(grep -E '^  "[0-9]{4}-[0-9]{2}-[0-9]{2}":$' "${METADATA_FILE}" | sed 's/[": ]//g' | sort)

if [ -z "${DATES}" ]; then
    echo "No dated recordings found in metadata cache."
    exit 0
fi

# Apply date filters upfront if specified
if [ ${#DATE_FILTERS[@]} -gt 0 ]; then
    FILTERED_DATES=""
    while IFS= read -r DATE; do
        for FILTER_DATE in "${DATE_FILTERS[@]}"; do
            if [[ "${DATE}" == "${FILTER_DATE}"* ]]; then
                FILTERED_DATES+="${DATE}"$'\n'
                break
            fi
        done
    done <<< "${DATES}"
    
    # Use filtered dates
    DATES=$(echo -n "${FILTERED_DATES}" | grep -v '^$')
    
    if [ -z "${DATES}" ]; then
        echo "No recordings found matching the specified dates."
        exit 0
    fi
fi

TOTAL_DATES=$(echo "${DATES}" | wc -l | tr -d ' ')
echo "Found ${TOTAL_DATES} unique dates with recordings"

CURRENT=0
DOWNLOADED=0
SKIPPED=0

# Process each date
while IFS= read -r DATE; do
    CURRENT=$((CURRENT + 1))
    
    echo ""
    echo "[$CURRENT/$TOTAL_DATES] Date: ${DATE}"
    
    # Extract the best (first) recording for this date from YAML
    # Get the line number of this date section
    DATE_LINE=$(grep -n "^  \"${DATE}\":$" "${METADATA_FILE}" | cut -d: -f1)
    
    # Extract the first identifier after this date (the best one, since they're sorted by score)
    # Temporarily disable pipefail for these commands to avoid SIGPIPE errors
    set +o pipefail
    IDENTIFIER=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | grep -m1 "identifier:" | sed 's/.*identifier: "\(.*\)"/\1/')
    SCORE=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | grep -m1 "score:" | sed 's/.*score: \(.*\)/\1/')
    MP3_COUNT=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | grep -m1 "mp3_count:" | sed 's/.*mp3_count: \(.*\)/\1/')
    
    # Count total recordings for this date
    NEXT_DATE_LINE=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | grep -n "^  \"" | head -1 | cut -d: -f1)
    if [ -z "${NEXT_DATE_LINE}" ]; then
        # This is the last date, count to end of file
        RECORDING_COUNT=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | grep -c "identifier:")
    else
        # Count recordings between this date and next date
        RECORDING_COUNT=$(tail -n +$((DATE_LINE + 1)) "${METADATA_FILE}" | head -n $((NEXT_DATE_LINE - 1)) | grep -c "identifier:")
    fi
    set -o pipefail
    
    if [ -z "${IDENTIFIER}" ]; then
        echo "  ⊘ No recordings found for this date (metadata parse error)"
        continue
    fi
    
    # Show selection info
    if [ ${RECORDING_COUNT} -gt 1 ]; then
        echo "  ℹ Selected best of ${RECORDING_COUNT} recordings (score: ${SCORE}, ${MP3_COUNT} tracks)"
    else
        echo "  ℹ Only recording available (${MP3_COUNT} tracks)"
    fi
    
    # Create directory name: just the date (since we deduplicate)
    DIR_NAME="${DATE}"
    TARGET_DIR="${BASE_DIR}/${DIR_NAME}"
    
    # Check if directory already exists
    if [ -d "${TARGET_DIR}" ]; then
        echo "  ✓ Already downloaded: ${DIR_NAME}"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi
    
    echo "  → Downloading: ${IDENTIFIER}"
    
    mkdir -p "${TARGET_DIR}"
    
    # Download the item (MP3s and metadata)
    # Use pipe-separated glob patterns for multiple file types
    ia download "${IDENTIFIER}" \
        --destdir="${TARGET_DIR}" \
        --glob="*.mp3|*.txt|*.xml|*.md5" \
        --no-directories
    
    echo "  ✓ Downloaded: ${DIR_NAME}"
    DOWNLOADED=$((DOWNLOADED + 1))
    
done <<< "${DATES}"

echo ""
echo "Download complete!"
echo "  Downloaded: ${DOWNLOADED} concert(s)"
echo "  Skipped (already present): ${SKIPPED}"
echo "  All saved to: ${BASE_DIR}/"
