import os
import shutil
from pathlib import Path
from server import attach_local_subtitles

# Setup dummy environment
DOWNLOAD_DIR = "dummy_downloads"
SHOW_NAME = "Test_Show"
SEASON = "Season 01"
EPISODE = "Test_Show_S01E01"
SUBTITLE_FILE = f"{EPISODE}.srt"

os.makedirs(os.path.join(DOWNLOAD_DIR, SHOW_NAME, SEASON), exist_ok=True)
with open(os.path.join(DOWNLOAD_DIR, SHOW_NAME, SEASON, SUBTITLE_FILE), "w") as f:
    f.write("1\n00:00:01,000 --> 00:00:02,000\nHello")

# Mock data
data = {
    "show_title": "Test Show",
    "seasons_data": [
        {
            "Season 1": [
                {
                    "title": "Pilot",
                    "filename": f"{EPISODE}.mkv",
                    "url": "https://filemoon.in/e/12345"
                }
            ]
        }
    ]
}

# Run function
print("Before:", data["seasons_data"][0]["Season 1"][0])
data = attach_local_subtitles(data, DOWNLOAD_DIR)
print("After:", data["seasons_data"][0]["Season 1"][0])

# Cleanup
shutil.rmtree(DOWNLOAD_DIR)
