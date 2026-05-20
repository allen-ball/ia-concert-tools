# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.3] - 2026-05-20

### Fixed
- Fixed filename parser to correctly handle `setDTT` pattern (e.g., `set101`, `set209`) used in some Grateful Dead recordings
  - Pattern `setDTT` now correctly parsed as disc D, track TT
  - Example: `GD791027set101.wav_vbr.mp3` → disc 1, track 01 (not disc 1, track 10)
  - Example: `GD791027set209.wav_vbr.mp3` → disc 2, track 09 (not disc 1, track 20)
  - Fixes incorrect disc/track numbering for concerts using this naming convention
  - Pattern matching now prioritized correctly: `setDTT` checked before less specific `tNN` pattern

### Changed
- Updated filename parser pattern priority to prevent false matches on `setDTT` filenames

## [1.0.2] - 2026-04-24

### Added
- Initial production release
- Complete Python rewrite of original Bash scripts
- Automatic deduplication with quality scoring
- Multi-disc concert support
- Music.app compatible ID3 tagging
- Character encoding detection
- Idempotent operations

### Features
- `ia-concerts build-cache` - Build metadata cache for a creator
- `ia-concerts download` - Download concerts with automatic deduplication
- `ia-concerts update-tags` - Update ID3 tags on downloaded concerts

## [1.0.0] - 2026-04-20

### Added
- Initial development version
- Core functionality implemented
- Parsers for XML, tracklists, and filenames
- Metadata caching with YAML
- Internet Archive API integration
