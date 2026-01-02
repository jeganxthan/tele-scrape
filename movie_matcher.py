#!/usr/bin/env python3
"""
Movie Metadata Matcher

Scrapes movie metadata from Stremio and matches with FileMoon CSV entries.
Works like imdb_scraper.py with placeholder replacement and MongoDB storage.
"""

import json
import sys
import os
import re
from movie_metadata import scrape_movie_metadata
import filemoon_converter
import db_utils

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 movie_matcher.py \"Movie Name\"")
        print("\nExample: python3 movie_matcher.py \"Jujutsu Kaisen 0\"")
        return
    
    movie_name = sys.argv[1]
    
    print(f"\n{'='*60}")
    print(f"Scraping metadata for: {movie_name}")
    print(f"{'='*60}\n")
    
    # Scrape metadata from Stremio
    metadata = scrape_movie_metadata(movie_name)
    
    if not metadata:
        print("❌ Failed to scrape metadata")
        return
    
    # Ensure category is set
    if 'category' not in metadata:
        metadata['category'] = "anime" if "anime" in movie_name.lower() else "movie"
    
    # For MongoDB compatibility: add show_title if it's a movie (db_utils expects show_title)
    if metadata.get('category') == 'movie' and 'show_title' not in metadata:
        metadata['show_title'] = metadata.get('title', movie_name)
    
    # Create filename for the movie (used for placeholder matching)
    movie_clean = re.sub(r'[^\w\s-]', '', movie_name).strip().replace(' ', '_')
    
    # Add placeholder URL and filename (will be replaced by filemoon_converter)
    if not metadata.get('url'):
        metadata['url'] = "https://filemoon.in/placeholder"
        # Use a more flexible filename pattern for matching
        metadata['filename'] = f"{movie_clean}"  # Without extension for better matching
    
    # Save to static folder (like imdb_scraper.py does)
    STATIC_DIR = "static"
    os.makedirs(STATIC_DIR, exist_ok=True)
    
    query_clean = re.sub(r'[^\w\s-]', '', movie_name).strip().replace(' ', '_').lower()
    output_file = os.path.join(STATIC_DIR, f"{query_clean}.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Data saved to {output_file}")
    
    # Fill FileMoon URLs from CSV (like imdb_scraper.py)
    print("\n🔄 Converting placeholders to FileMoon URLs...")
    metadata = filemoon_converter.fill_filemoon_urls(metadata)
    
    # Display final metadata
    print(f"\n{'='*60}")
    print("FINAL METADATA (with FileMoon URL)")
    print(f"{'='*60}\n")
    print(json.dumps(metadata, indent=4, ensure_ascii=False))
    
    # Save to MongoDB (like imdb_scraper.py)
    try:
        print("\n💾 Saving to MongoDB...")
        db_utils.save_show_data(metadata)
        print("✅ Data saved to MongoDB")
    except Exception as e:
        print(f"❌ Failed to save to MongoDB: {e}")
        import traceback
        traceback.print_exc()
    
    # Save final version with FileMoon URL
    final_output = f"{query_clean}_final.json"
    with open(final_output, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)
    print(f"✅ Final data saved to: {final_output}")

if __name__ == "__main__":
    main()

