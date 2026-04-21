# Internet Archive Concert Tools

Python toolkit for downloading and tagging live concert recordings from [Internet Archive's etree collection](https://archive.org/details/etree).

## Features

- **Automatic deduplication**: Downloads only the best recording per concert date
- **Smart quality scoring**: Ranks recordings by track count, source quality, equipment, and ratings
- **Metadata caching**: 7-day cache for fast repeated operations
- **Comprehensive ID3 tagging**: Extracts metadata from XML and text files
- **Multi-disc support**: Handles complex multi-disc/set concerts correctly
- **Music.app compatible**: Proper COMM frame formatting for macOS Music.app
- **Date filtering**: Download specific dates, months, or years
- **Dry-run mode**: Preview tag changes before applying

## Installation

### From Source (Development)

```bash
# Clone repository
git clone https://github.com/allen-ball/ia-mp3-download-and-tag.git
cd ia-mp3-download-and-tag

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode
pip install -e .
```

### System-wide Installation (pipx recommended)

```bash
# Install pipx if not already installed
brew install pipx  # macOS
# or: python3 -m pip install --user pipx

# Install ia-concerts
pipx install /path/to/ia-mp3-download-and-tag
```

## Usage

The `ia-concerts` command provides three subcommands:

### 1. Build Metadata Cache

Fetches all recordings for an artist and creates a scored cache:

```bash
ia-concerts build-cache "Billy Strings"
```

Options:
- `--force`: Force rebuild even if cache is fresh

### 2. Download Concerts

Downloads concerts with automatic deduplication:

```bash
# Download all concerts
ia-concerts download "Billy Strings"

# Download specific dates
ia-concerts download "Billy Strings" 2023-10-15 2023-10-16

# Download entire month
ia-concerts download "Phil Lesh and Friends" 2023-10

# Download entire year
ia-concerts download "Grateful Mondays" 2015
```

Options:
- `--skip-cache`: Download all recordings without deduplication

### 3. Update ID3 Tags

Updates MP3 tags from metadata files:

```bash
ia-concerts update-tags "Billy Strings"
```

Options:
- `--genre GENRE`: Override default genre (default: Bluegrass)
- `--dry-run`: Show changes without modifying files

### Global Options

Available for all commands:

- `-v, --verbose`: Enable debug logging
- `-q, --quiet`: Show only warnings and errors
- `--version`: Show version number

## How It Works

### Quality Scoring Algorithm

Recordings are scored based on:

- **Track count** (1000 pts/track): Completeness is highest priority
- **Source quality**:
  - Soundboard (SBD): +500 pts
  - Matrix: +300 pts
- **Equipment quality** (+200 pts): Schoeps, DPA, Neumann, AKG, Earthworks
- **High-resolution** (+100 pts): 24-bit/96kHz indicators
- **Community ratings** (50 pts/star): User feedback
- **File size** (+1 pt/10MB): Minor tiebreaker

### Directory Structure

```
{Creator}/
├── .metadata.yaml          # Cache file (auto-generated)
├── 2023-10-15/            # Concert directory (YYYY-MM-DD)
│   ├── *.mp3              # Audio files
│   ├── *_meta.xml         # Archive.org metadata
│   ├── *_files.xml        # File list with track titles
│   └── *.txt              # Tracklists
└── 2023-10-16/
    └── ...
```

### ID3 Tag Priority

Track titles are extracted in priority order:

1. **XML files** (`*_files.xml`) - Most accurate, preserves taper's notation
2. **Text files** (`.txt` tracklists) - Manual tracklists
3. **Filenames/existing tags** - Fallback

### Music.app Compatibility

Sets proper COMM frames for comment display:
- `COMM::XXX` (UTF-16, lang='XXX')
- `COMM::eng` (LATIN1, lang='eng')

Both frames are required for Music.app to display comments in its UI.

## Configuration

Default settings are in `ia_concert_tools/config.py`. You can modify:

- Scoring weights
- File patterns
- Default genre
- Cache expiry (default: 7 days)
- Excluded filenames

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for development setup and workflow.

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=ia_concert_tools --cov-report=html

# Type checking
mypy ia_concert_tools

# Code formatting
black ia_concert_tools tests
```

### Project Structure

```
ia_concert_tools/
├── __init__.py           # Package initialization
├── __main__.py           # CLI entry point
├── config.py             # Configuration constants
├── logging_config.py     # Logging setup
├── metadata.py           # Metadata caching
├── downloader.py         # Download logic
├── tagger.py             # ID3 tagging
├── parsers/              # Metadata parsers
│   ├── xml_parser.py     # XML parsing
│   ├── tracklist_parser.py
│   └── filename_parser.py
└── utils/                # Utilities
    ├── encoding.py       # Character encoding
    └── validation.py     # Input validation
```

## Requirements

- Python 3.8+
- Dependencies (auto-installed):
  - `internetarchive` - Internet Archive API
  - `mutagen` - ID3 tag manipulation
  - `pyyaml` - YAML cache handling
  - `chardet` - Character encoding detection
  - `click` - CLI framework

## Troubleshooting

### Comments not showing in Music.app

Re-run tag update: `ia-concerts update-tags "Artist Name"`

The script now properly sets both COMM frames required by Music.app.

### Character encoding errors

Script automatically detects encoding (UTF-8 vs Windows-1252) and converts only when needed to prevent double-encoding.

### Wrong track numbers on multi-disc concerts

Script handles both disc notation (`d2t01`) and set notation (`s2t01`) with case-insensitive matching.

### Metadata cache is stale

Delete `.metadata.yaml` or use `--force`: `ia-concerts build-cache "Artist" --force`

Cache automatically refreshes after 7 days.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

MIT License - See LICENSE file for details

## Credits

Original Bash implementation by Allen Ball.

Uses the excellent [internetarchive](https://archive.org/developers/internetarchive/) Python library by Internet Archive.

## Links

- [Internet Archive etree Collection](https://archive.org/details/etree)
- [Internet Archive Python Library](https://archive.org/developers/internetarchive/)
- [Project Repository](https://github.com/allen-ball/ia-mp3-download-and-tag)
