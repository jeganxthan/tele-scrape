import os
import shutil
import json
from pathlib import Path
from server import attach_local_subtitles

# Setup dummy directories and files
TEST_DIR = "test_downloads"
SHOW_NAME = "Test_Show"
SEASON = "Season 01"
EPISODE_FILE = "Test_Show_S01E01.mkv"
SUBTITLE_FILE = "Test_Show_S01E01.srt"

def setup():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    
    season_path = os.path.join(TEST_DIR, SHOW_NAME, SEASON)
    os.makedirs(season_path)
    
    # Create dummy subtitle file
    with open(os.path.join(season_path, SUBTITLE_FILE), "w") as f:
        f.write("1\n00:00:01,000 --> 00:00:02,000\nHello World")

def test_matching():
    setup()
    
    # Mock data
    data = {
        "show_title": "Test Show",
        "seasons_data": [
            {
                "Season 1": [
                    {
                        "title": "Episode 1",
                        "filename": EPISODE_FILE,
                        "url": "https://filemoon.in/e/12345"
                    }
                ]
            }
        ]
    }
    
    print("Running attach_local_subtitles...")
    updated_data = attach_local_subtitles(data, TEST_DIR)
    
    episode = updated_data["seasons_data"][0]["Season 1"][0]
    if "subtitle" in episode:
        print(f"✅ Success! Subtitle found: {episode['subtitle']}")
        assert episode["subtitle"].endswith(SUBTITLE_FILE)
    else:
        print("❌ Failed! Subtitle not found.")
        print(f"Data: {json.dumps(updated_data, indent=2)}")

    # Cleanup
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)

if __name__ == "__main__":
    test_matching()
