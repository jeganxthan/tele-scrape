import csv
import re
from typing import Dict, List

def load_filemoon_csv(csv_path="filemoon_files.csv") -> Dict[str, str]:
    """
    Load FileMoon CSV and create a mapping of normalized filenames to file codes.
    Returns: {normalized_filename: file_code}
    """
    filename_to_code = {}
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                file_code = row.get('file_code', '').strip()
                
                if title and file_code:
                    # Normalize the title to match our filename format
                    # Example: "The Witcher S01E01" -> "The_Witcher_S01E01"
                    normalized = normalize_filename(title)
                    filename_to_code[normalized] = file_code
                    
    except Exception as e:
        print(f"Error loading CSV: {e}")
    
    return filename_to_code

def normalize_filename(title: str) -> str:
    """
    Normalize a title to match filename format.
    Examples:
        "The Witcher S01E01" -> "The_Witcher_S01E01"
        "Squid Game 2021 S01E01" -> "Squid_Game_2021_S01E01"
    """
    # Remove special characters except spaces and alphanumeric
    cleaned = re.sub(r'[^\w\s-]', '', title)
    # Replace spaces with underscores
    normalized = cleaned.strip().replace(' ', '_')
    return normalized

def extract_season_episode(filename: str) -> tuple:
    """
    Extract season and episode numbers from filename.
    Returns: (season_num, episode_num) or (None, None)
    """
    match = re.search(r'S(\d+)E(\d+)', filename, re.IGNORECASE)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    return (None, None)

def fill_filemoon_urls(data: Dict, csv_path="filemoon_files.csv") -> Dict:
    """
    Replace placeholder URLs in scraped data with actual FileMoon URLs.
    
    Args:
        data: Scraped IMDb data dictionary
        csv_path: Path to filemoon_files.csv
        
    Returns:
        Updated data dictionary with FileMoon URLs
    """
    # Load the CSV mapping
    filename_to_code = load_filemoon_csv(csv_path)
    
    if not filename_to_code:
        print("Warning: No FileMoon data loaded from CSV")
        return data
    
    # Process each season
    for season_dict in data.get("seasons_data", []):
        for season_name, episodes in season_dict.items():
            for episode in episodes:
                filename = episode.get("filename", "")
                
                if not filename:
                    continue
                
                # Remove .mkv extension for matching
                base_filename = filename.replace(".mkv", "")
                normalized = normalize_filename(base_filename)
                
                # Try exact match first
                if normalized in filename_to_code:
                    file_code = filename_to_code[normalized]
                    episode["url"] = f"https://filemoon.in/e/{file_code}"
                    print(f"DEBUG: Matched '{normalized}' -> {file_code}")
                    continue
                else:
                    print(f"DEBUG: No match for '{normalized}'")
                
                # Try fuzzy matching by season/episode
                season_num, episode_num = extract_season_episode(filename)
                if season_num and episode_num:
                    # Try to find a match with same S##E## pattern
                    pattern = f"S{season_num:02d}E{episode_num:02d}"
                    
                    for csv_filename, file_code in filename_to_code.items():
                        if pattern in csv_filename:
                            # Check if show name is similar
                            show_name = data.get("show_title", "")
                            show_clean = re.sub(r'[^\w\s-]', '', show_name).strip().replace(' ', '_')
                            
                            # Fuzzy match: check if main words from show title are in CSV filename
                            show_words = set(show_clean.lower().split('_'))
                            csv_words = set(csv_filename.lower().split('_'))
                            
                            # If at least 2 words match (or 1 for short titles), consider it a match
                            common_words = show_words & csv_words
                            if len(common_words) >= min(2, len(show_words)):
                                episode["url"] = f"https://filemoon.in/e/{file_code}"
                                break
    
    return data

if __name__ == "__main__":
    import sys
    
    # Get query from command line argument or default to The Witcher
    query = sys.argv[1] if len(sys.argv) > 1 else "The Witcher"
    
    # Clean the query for filename
    query_clean = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_').lower()
    
    input_file = f"{query_clean}_data.json"
    output_file = f"{query_clean}_data_with_urls.json"
    
    print(f"Processing: {query}")
    print(f"Input file: {input_file}")
    
    try:
        # Load scraped data
        with open(input_file, "r", encoding="utf-8") as f:
            test_data = json.load(f)
        
        # Fill URLs
        print("Filling FileMoon URLs...")
        updated_data = fill_filemoon_urls(test_data)
        
        # Save result
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, indent=4, ensure_ascii=False)
        
        print(f"✅ Complete! Saved to: {output_file}")
        
        # Show stats
        total_episodes = sum(len(list(season_dict.values())[0]) 
                           for season_dict in updated_data.get("seasons_data", []))
        matched_urls = sum(1 for season_dict in updated_data.get("seasons_data", [])
                          for episodes in season_dict.values()
                          for ep in episodes
                          if "placeholder" not in ep.get("url", ""))
        
        print(f"📊 Stats: {matched_urls}/{total_episodes} episodes matched with FileMoon URLs")
        
    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found!")
        print(f"💡 Tip: First scrape the show using imdb_scraper.py or the API")
        print(f"   Example: python3 imdb_scraper.py '{query}'")
    except Exception as e:
        print(f"❌ Error: {e}")
