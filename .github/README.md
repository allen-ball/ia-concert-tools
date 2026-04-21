# Internet Archive Concert Downloader & Tagger

Bash scripts for downloading and managing live concert recordings from the Internet Archive (archive.org). Automatically downloads the best quality recording per concert date and updates ID3 tags with metadata from Internet Archive.

## Features

- **Automatic deduplication**: Downloads only the highest-quality recording per concert date
- **Smart quality scoring**: Evaluates recordings based on source type (soundboard/matrix/audience), equipment quality, track completeness, and community ratings
- **Metadata caching**: 7-day cache of Internet Archive metadata for fast subsequent runs
- **Comprehensive ID3 tagging**: Extracts metadata from Internet Archive XML files and tracklists
- **Music.app compatibility**: Properly formatted ID3v2.3 tags with comment fields that display correctly in Apple Music
- **Multi-disc support**: Handles concerts split across multiple discs or sets
- **Jam band notation**: Preserves segue symbols (`>`, `->`) and musical notation from original tapers

## Installation

### Dependencies

```bash
# macOS (via Homebrew)
brew install internetarchive jq ffmpeg

# Install Python dependencies
pip3 install mutagen
```

### Install Scripts

```bash
# Clone the repository
git clone https://github.com/allen-ball/ia-mp3-download-and-tag.git
cd ia-mp3-download-and-tag

# Install scripts to ~/.local/bin
mkdir -p ~/.local/bin
cp ia-*.sh ia-set-comment.py ~/.local/bin/
chmod +x ~/.local/bin/ia-*.sh ~/.local/bin/ia-set-comment.py

# Add to PATH (if not already present)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Quick Start

```bash
# Download all concerts for an artist
ia-download-concerts.sh "Billy Strings"

# Download specific dates
ia-download-concerts.sh "Billy Strings" 2023-10-15 2023-10-16

# Download all shows from a specific month
ia-download-concerts.sh "Phil Lesh and Friends" 2023-10

# Update ID3 tags on downloaded concerts
ia-update-concert-tags.sh "Billy Strings"
```

## How It Works

### 1. Metadata Cache (`ia-build-metadata.sh`)

Fetches all recordings from Internet Archive for an artist and scores them based on:
- Track completeness (1000 points per track)
- Source quality: Soundboard (+500), Matrix (+300), Audience (0)
- Equipment: Schoeps, DPA, Neumann, etc. (+200)
- Processing: 24-bit indicators (+100)
- Community ratings (50 points per star)

Results are cached in `{Artist}/.metadata.yaml` for 7 days.

### 2. Smart Download (`ia-download-concerts.sh`)

- Uses metadata cache to select best recording per date
- Downloads to clean directory structure: `{Artist}/{YYYY-MM-DD}/`
- Skips already-downloaded concerts
- Shows selection rationale (e.g., "Selected best of 3 recordings (score: 21850)")

### 3. Tag Update (`ia-update-concert-tags.sh`)

Updates ID3 tags with metadata extracted from:
- Internet Archive XML files (highest priority for track titles)
- Text tracklists included with recordings
- ID3v2.3 format for Music.app compatibility
- Adds source URL to comments: `https://archive.org/details/{identifier}`

## Directory Structure

```
Billy Strings/
├── .metadata.yaml          # Cached metadata (auto-generated)
├── 2021-05-21/            # Concert date
│   ├── 01.mp3
│   ├── 02.mp3
│   ├── *_files.xml        # IA metadata (track titles)
│   ├── *_meta.xml         # IA metadata (album/artist)
│   └── *.txt              # Tracklist files
└── 2023-10-15/
    └── ...
```

## Scripts

- **`ia-build-metadata.sh`** - Build metadata cache with quality scoring
- **`ia-download-concerts.sh`** - Download concerts with automatic deduplication
- **`ia-update-concert-tags.sh`** - Update MP3 ID3 tags from metadata
- **`ia-set-comment.py`** - Helper for Music.app COMM frame compatibility

## Configuration

### Changing Default Genre

Edit line 603 in `ia-update-concert-tags.sh`:
```bash
GENRE="Bluegrass"  # Change to your preferred genre
```

### Adjusting Quality Scoring

Edit scoring logic in `ia-build-metadata.sh` (lines 40-80) to adjust preferences:
```bash
# Example: Prioritize soundboard recordings even more
if [[ "$source" =~ sbd|soundboard ]]; then
    score=$((score + 1000))  # Increased from 500
fi
```

## Troubleshooting

**Metadata cache is stale:**
```bash
rm "{Artist}/.metadata.yaml"
ia-build-metadata.sh "Artist Name"
```

**Comments not displaying in Music.app:**
```bash
# Re-run tag update (will fix COMM frames)
ia-update-concert-tags.sh "Artist Name"
```

**Track titles are generic:**
- Ensure `*_files.xml` exists (should be downloaded automatically)
- Check text file format matches supported patterns

See `.github/copilot-instructions.md` for comprehensive troubleshooting guide.

## Documentation

- **[Copilot Instructions](copilot-instructions.md)** - Comprehensive guide for AI assistants and developers
- Detailed architecture, code patterns, and troubleshooting information

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Credits

Designed for managing live concert recordings from the Internet Archive's [Live Music Archive](https://archive.org/details/etree) (etree collection).

Special thanks to the tapers and uploaders who preserve and share live music recordings.
