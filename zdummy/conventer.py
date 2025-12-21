import json
import csv
import re

# Function to safely extract season number
def parse_season_number(season_name):
    # Try to extract digits first
    match = re.search(r'\d+', season_name)
    if match:
        return int(match.group())
    # Optional: handle words like "One", "Two", etc.
    words_to_numbers = {
        "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
        "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10
    }
    for word, num in words_to_numbers.items():
        if word.lower() in season_name.lower():
            return num
    return None

# Load JSON data
with open('show_data_with_details.json', 'r', encoding='utf-8') as f:
    json_data = json.load(f)

# Load CSV data
csv_file = 'squidGame.csv'
csv_episodes = {}
with open(csv_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        filename, url = row
        match = re.search(r'S(\d+)E(\d+)', filename, re.IGNORECASE)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            csv_episodes[(season, episode)] = {'filename': filename, 'url': url}

# Combine JSON with CSV URLs while keeping season structure
combined_seasons = []

for season_dict in json_data.get('seasons_data', []):
    for season_name, episodes in season_dict.items():
        season_number = parse_season_number(season_name)
        if season_number is None:
            print(f"Warning: Could not extract season number from '{season_name}', skipping")
            continue

        new_episodes = []
        for ep in episodes:
            # Extract episode number from title
            ep_num_match = re.match(r'(\d+)\.', ep['title'])
            if ep_num_match:
                ep_number = int(ep_num_match.group(1))
                key = (season_number, ep_number)
                if key in csv_episodes:
                    ep['filename'] = csv_episodes[key]['filename']
                    ep['url'] = csv_episodes[key]['url']
            new_episodes.append(ep)
        combined_seasons.append({season_name: new_episodes})

# Save combined data to new JSON
with open('squidGame.json', 'w', encoding='utf-8') as f:
    json.dump({
        'show_title': json_data.get('show_title'),
        'year': json_data.get('year'),
        'seasons': json_data.get('seasons'),
        'rating': json_data.get('rating'),
        'genre': json_data.get('genre'),
        'description': json_data.get('description'),
        'starring': json_data.get('starring'),
        'creators': json_data.get('creators'),
        'genres': json_data.get('genres'),
        'show_characteristics': json_data.get('show_characteristics'),
        'audio': json_data.get('audio'),
        'subtitles': json_data.get('subtitles'),
        'cast': json_data.get('cast'),
        'Poster': json_data.get('Poster'),
        'seasons_data': combined_seasons
    }, f, indent=4)

print("JSON and CSV data combined successfully, seasons preserved!")
