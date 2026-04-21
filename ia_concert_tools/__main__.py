"""
Command-line interface for Internet Archive Concert Tools.

Provides subcommands:
- build-cache: Build metadata cache for a creator
- download: Download concerts for a creator
- update-tags: Update ID3 tags on downloaded concerts
"""

import sys
from pathlib import Path
from typing import List, Optional

import click

from ia_concert_tools import __version__
from ia_concert_tools.logging_config import setup_logging, get_logger


@click.group()
@click.version_option(version=__version__, prog_name="ia-concerts")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output (debug logging)")
@click.option("-q", "--quiet", is_flag=True, help="Quiet mode (warnings and errors only)")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Internet Archive Concert Tools - Download and tag concert recordings."""
    # Set up logging
    logger = setup_logging(verbose=verbose, quiet=quiet)
    
    # Store logger in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["logger"] = logger
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


@main.command("build-cache")
@click.argument("creator")
@click.option(
    "--force",
    is_flag=True,
    help="Force rebuild even if cache is fresh"
)
@click.pass_context
def build_cache(ctx: click.Context, creator: str, force: bool) -> None:
    """
    Build metadata cache for a creator.
    
    Fetches all recordings from Internet Archive, scores them based on quality,
    and creates a YAML cache file for fast deduplication.
    
    CREATOR: Artist or creator name (e.g., "Billy Strings")
    """
    logger = ctx.obj["logger"]
    logger.info(f"Building metadata cache for: {creator}")
    
    try:
        from ia_concert_tools.metadata import MetadataBuilder
        
        builder = MetadataBuilder(creator)
        cache_path = builder.build_cache(force=force)
        
        logger.info(f"✓ Cache built successfully: {cache_path}")
        
    except ImportError:
        logger.error("Metadata module not yet implemented")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to build cache: {e}")
        if ctx.obj["verbose"]:
            logger.exception("Full traceback:")
        sys.exit(1)


@main.command("download")
@click.argument("creator")
@click.argument("dates", nargs=-1)
@click.option(
    "--skip-cache",
    is_flag=True,
    help="Skip metadata cache and download all recordings"
)
@click.pass_context
def download(ctx: click.Context, creator: str, dates: tuple, skip_cache: bool) -> None:
    """
    Download concerts for a creator.
    
    Downloads MP3s, metadata, and tracklists from Internet Archive.
    Uses metadata cache for automatic deduplication (best recording per date).
    
    CREATOR: Artist or creator name (e.g., "Billy Strings")
    
    DATES: Optional date filters (e.g., 2023-10-15 or 2023-10 for entire month)
    """
    logger = ctx.obj["logger"]
    logger.info(f"Downloading concerts by: {creator}")
    
    if dates:
        logger.info(f"Filtering by dates: {', '.join(dates)}")
    
    try:
        from ia_concert_tools.downloader import Downloader
        
        downloader = Downloader(creator, use_cache=not skip_cache)
        results = downloader.download(date_filters=list(dates))
        
        logger.info("\nDownload complete!")
        logger.info(f"  Downloaded: {results['downloaded']} concert(s)")
        logger.info(f"  Skipped (already present): {results['skipped']}")
        
    except ImportError:
        logger.error("Downloader module not yet implemented")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Download failed: {e}")
        if ctx.obj["verbose"]:
            logger.exception("Full traceback:")
        sys.exit(1)


@main.command("update-tags")
@click.argument("creator")
@click.option(
    "--genre",
    default=None,
    help="Override default genre (default: Bluegrass)"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be changed without modifying files"
)
@click.pass_context
def update_tags(ctx: click.Context, creator: str, genre: Optional[str], dry_run: bool) -> None:
    """
    Update ID3 tags on downloaded concerts.
    
    Parses metadata from XML files and tracklists, then updates MP3 ID3v2.3 tags.
    Handles multi-disc sets and ensures Music.app compatibility.
    
    CREATOR: Artist or creator name (e.g., "Billy Strings")
    """
    logger = ctx.obj["logger"]
    logger.info(f"Updating MP3 tags in: {creator}")
    
    if dry_run:
        logger.info("DRY RUN MODE - no files will be modified")
    
    try:
        from ia_concert_tools.tagger import Tagger
        
        tagger = Tagger(creator, genre=genre)
        results = tagger.update_tags(dry_run=dry_run)
        
        logger.info("\nTag update complete!")
        logger.info(f"  Updated: {results['updated']} file(s)")
        logger.info(f"  Skipped (unchanged): {results['skipped']}")
        logger.info(f"  Concerts processed: {results['concerts']}")
        
    except ImportError:
        logger.error("Tagger module not yet implemented")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Tag update failed: {e}")
        if ctx.obj["verbose"]:
            logger.exception("Full traceback:")
        sys.exit(1)


if __name__ == "__main__":
    main()
