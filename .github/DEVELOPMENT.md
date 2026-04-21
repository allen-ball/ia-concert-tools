# Development Guide

## Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

## Running the CLI

```bash
# Activate virtual environment
source venv/bin/activate

# Run CLI
ia-concerts --help
ia-concerts download "Billy Strings" --help
```

## Development Workflow

### Implementation Status

**Phase 1: Core Infrastructure** ✅ COMPLETE
- [x] Package structure with pyproject.toml
- [x] Configuration module with all constants
- [x] CLI framework with Click (3 subcommands)
- [x] Logging infrastructure with colors
- [x] Character encoding detection (chardet)
- [x] Input validation utilities

**Phase 2: Metadata Module** 🚧 TODO
- [ ] Fetch recordings from Internet Archive API
- [ ] Implement quality scoring algorithm
- [ ] Generate YAML cache
- [ ] Cache age validation

**Phase 3: Download Module** 🚧 TODO
- [ ] Download using internetarchive library
- [ ] Date filtering with prefix matching
- [ ] Deduplication logic
- [ ] Progress reporting

**Phase 4: Parsing Modules** 🚧 TODO
- [ ] XML parser (*_meta.xml, *_files.xml)
- [ ] Tracklist parser (multiple formats)
- [ ] Filename pattern matching
- [ ] HTML entity decoding

**Phase 5: Tagging Module** 🚧 TODO
- [ ] Replace ffmpeg with mutagen
- [ ] Metadata extraction from XML
- [ ] Track name normalization
- [ ] Multi-disc/set numbering
- [ ] Music.app COMM frames
- [ ] Idempotent tag updates

**Phase 6: Testing** 🚧 TODO
- [ ] Unit tests for parsers
- [ ] Integration tests
- [ ] End-to-end tests
- [ ] Type hints and docstrings

**Phase 7: Deployment** 🚧 TODO
- [ ] pipx installation
- [ ] Validation against Bash scripts
- [ ] Migration guide

### Current Stats
- **Files created**: 14 Python modules
- **Lines of code**: ~900 lines
- **Todos complete**: 5/31 (16.1%)
- **Phase 1**: ✅ Complete

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ia_concert_tools --cov-report=html
open htmlcov/index.html

# Run specific test
pytest tests/test_metadata.py

# Run with verbose output
pytest -v

# Type checking
mypy ia_concert_tools
```

## Code Style

```bash
# Format code
black ia_concert_tools tests

# Check formatting without making changes
black --check ia_concert_tools tests

# Sort imports
isort ia_concert_tools tests
```

## Debugging

```bash
# Run with verbose logging
ia-concerts -v download "Billy Strings"

# Python debugger
python -m pdb -m ia_concert_tools download "Billy Strings"

# Or add breakpoint in code:
import pdb; pdb.set_trace()
```

## Project Structure

```
ia-mp3-download-and-tag/
├── ia_concert_tools/          # Main package
│   ├── __init__.py           # Package init
│   ├── __main__.py           # CLI entry point ✅
│   ├── config.py             # Configuration ✅
│   ├── logging_config.py     # Logging setup ✅
│   ├── metadata.py           # Metadata builder (stub)
│   ├── downloader.py         # Downloader (stub)
│   ├── tagger.py             # ID3 tagger (stub)
│   ├── parsers/              # Parsers
│   │   ├── __init__.py       ✅
│   │   ├── xml_parser.py     # XML parsing (stub)
│   │   ├── tracklist_parser.py (stub)
│   │   └── filename_parser.py  (stub)
│   └── utils/                # Utilities
│       ├── __init__.py       ✅
│       ├── encoding.py       # Encoding detection ✅
│       └── validation.py     # Input validation ✅
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── test_metadata.py      (TODO)
│   ├── test_parsers.py       (TODO)
│   └── fixtures/             # Test data
├── venv/                     # Virtual environment (gitignored)
├── pyproject.toml            # Package configuration ✅
├── README.md                 # User documentation ✅
└── DEVELOPMENT.md            # This file ✅
```

## Implementation Order

Based on dependency graph:

1. **Parsers** (no external deps)
   - `filename_parser.py` - Pattern matching
   - `xml_parser.py` - XML metadata extraction
   - `tracklist_parser.py` - Text file parsing

2. **Metadata Builder**
   - Uses internetarchive library
   - Implements scoring algorithm
   - Outputs YAML

3. **Downloader**
   - Uses metadata cache
   - Downloads files
   - Progress reporting

4. **Tagger**
   - Uses all parsers
   - Mutagen for ID3 tags
   - Most complex module

## Next Steps

### Immediate (Phase 2)
1. Implement `metadata.py` - MetadataBuilder class
2. Test with Internet Archive API
3. Verify YAML cache output matches Bash version

### After Phase 2
1. Implement downloaders
2. Build out parsers
3. Implement tagger
4. Add comprehensive tests

## Useful Commands

```bash
# Check installed version
ia-concerts --version

# View package info
pip show ia-concert-tools

# Reinstall after changes
pip install -e .

# Clean build artifacts
rm -rf build/ dist/ *.egg-info

# View dependency tree
pip install pipdeptree
pipdeptree -p ia-concert-tools
```

## Resources

- [Internet Archive Python Library](https://internetarchive.readthedocs.io/)
- [Mutagen Documentation](https://mutagen.readthedocs.io/)
- [Click Documentation](https://click.palletsprojects.com/)
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation)
- [ID3v2.3 Specification](https://id3.org/id3v2.3.0)

## Troubleshooting

### Import errors
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall in editable mode
pip install -e .
```

### CLI not found
```bash
# Check if entry point is registered
pip show -f ia-concert-tools | grep ia-concerts

# Reinstall package
pip install --force-reinstall -e .
```

### Dependencies out of sync
```bash
# Upgrade all dependencies
pip install --upgrade -r <(pip freeze)

# Or start fresh
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```
