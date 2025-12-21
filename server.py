# server.py
import json
import time
import re
import os
import asyncio
import csv
from flask import Flask, jsonify, request
from dotenv import load_dotenv

# Selenium imports (IMDb scraper)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Optional FileMoon import
try:
    from fileMoon import FileMoon
    FILEMOON_AVAILABLE = True
except ImportError:
    FileMoon = None
    FILEMOON_AVAILABLE = False
    print("⚠️ FileMoon module not found. FileMoon features will be disabled.")

# Local imports (assume these modules exist in your project)
from imdb_scraper import scrape_imdb
from filemoon_converter import fill_filemoon_urls
import db_utils

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============== CONFIGURATION ==============
DOWNLOAD_DIR = "downloads/"
FILEMOON_API_KEY = os.getenv("FILEMOON_API_KEY")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
MAX_CONCURRENT_UPLOADS = int(os.getenv("MAX_CONCURRENT_UPLOADS", 3))
# ===========================================

# Initialize FileMoon client
filemoon_client = None
if FILEMOON_AVAILABLE and FILEMOON_API_KEY:
    filemoon_client = FileMoon(FILEMOON_API_KEY)
    print("✅ FileMoon client initialized.")
elif not FILEMOON_AVAILABLE:
    print("⚠️ FileMoon module not available. FileMoon uploads will be skipped.")
else:
    print("⚠️ FILEMOON_API_KEY not found in .env. FileMoon uploads will be skipped.")

# ---------------- Helper: Strict FileMoon URL filter ----------------
# Keep only URLs that match: https?://(www.)?filemoon.in/e/<id> (optionally trailing slash or query)
FILEMOON_EPISODE_REGEX = re.compile(
    r"^https?://(?:www\.)?filemoon\.in/e/[A-Za-z0-9_-]+(?:/)?(?:\?.*)?$",
    re.IGNORECASE
)

def is_valid_filemoon_episode_url(url: str) -> bool:
    """Return True only if the URL matches a real FileMoon episode pattern."""
    if not url:
        return False
    url = url.strip()
    # Quick reject placeholder
    if "placeholder" in url.lower():
        return False
    # Match strict FileMoon /e/ pattern
    if FILEMOON_EPISODE_REGEX.match(url):
        return True
    return False

def remove_non_filemoon_episode_urls(data: dict) -> (dict, int, list):
    """
    Walk data['seasons_data'] and keep only episodes whose 'url' matches is_valid_filemoon_episode_url().
    Returns cleaned data, count removed, and a list of removed episodes for logging/audit.
    """
    removed_count = 0
    removed_items = []
    if not data:
        return data, removed_count, removed_items

    seasons = data.get("seasons_data", [])
    cleaned_seasons = []

    for season_entry in seasons:
        if not isinstance(season_entry, dict):
            continue
        new_season_entry = {}
        for season_key, episodes in season_entry.items():
            if not isinstance(episodes, list):
                continue
            cleaned_eps = []
            for ep in episodes:
                ep_url = (ep.get("url") or "").strip()
                if not is_valid_filemoon_episode_url(ep_url):
                    removed_count += 1
                    removed_items.append({
                        "season": season_key,
                        "title": ep.get("title"),
                        "filename": ep.get("filename"),
                        "url": ep_url
                    })
                    print(f"Removed non-filemoon or placeholder episode -> {ep.get('filename')} url='{ep_url}'")
                    continue
                cleaned_eps.append(ep)
            if cleaned_eps:
                new_season_entry[season_key] = cleaned_eps
        if new_season_entry:
            cleaned_seasons.append(new_season_entry)

    data["seasons_data"] = cleaned_seasons
    return data, removed_count, removed_items

# ---------------- Helper: Subtitle Matching ----------------
from pathlib import Path

def find_local_subtitles(download_dir: str) -> dict:
    """
    Walks through DOWNLOAD_DIR and finds all .srt files.
    Returns a dict: { filename_stem: full_path_to_subtitle }
    """
    subtitle_map = {}
    if not os.path.isdir(download_dir):
        return subtitle_map

    for root, _, files in os.walk(download_dir):
        for file in files:
            if file.lower().endswith(".srt"):
                # stem "Show_S01E01" from "Show_S01E01.srt"
                stem = Path(file).stem
                full_path = os.path.join(root, file)
                subtitle_map[stem] = full_path
    return subtitle_map

def attach_local_subtitles(data: dict, download_dir: str) -> dict:
    """
    Matches episodes to local subtitles based on filename stem.
    """
    subtitle_map = find_local_subtitles(download_dir)
    if not subtitle_map:
        return data

    seasons = data.get("seasons_data", [])
    for season_entry in seasons:
        if not isinstance(season_entry, dict):
            continue
        for season_key, episodes in season_entry.items():
            if not isinstance(episodes, list):
                continue
            for ep in episodes:
                filename = ep.get("filename")
                if filename:
                    stem = Path(filename).stem
                    if stem in subtitle_map:
                        ep["subtitle"] = subtitle_map[stem]
                        print(f"Found subtitle for {filename}: {subtitle_map[stem]}")
    return data
# -------------------------------------------------------------------

# ---------------- FileMoon upload utilities (unchanged) -----------------
def extract_info_from_filename(filename):
    """Extracts series, season, and episode from a filename like 'Breaking_Bad_S01E01.mkv' or .mp4."""
    info = {}
    # Support multiple video extensions
    match = re.match(r"^(.*?)_S(\d+)E(\d+)\.(mkv|mp4|avi|mov)$", filename, re.IGNORECASE)
    if match:
        info["series"] = match.group(1).replace('_', ' ').strip()
        info["season_number"] = int(match.group(2))
        info["episode_number"] = int(match.group(3))
    return info

def upload_progress_callback(current, total, file_name):
    percentage = (current / total) * 100
    if int(percentage) % 10 == 0 and int(percentage) > 0:
         print(f"         Uploading '{file_name}': {percentage:.0f}%", end='\r')

def upload_single_file_sync(local_file_path, remote_ftp_path, filename):
    try:
        print(f"      ⬆️ Starting upload: '{filename}'")
        success = filemoon_client.ftp_upload(
            local_file_path,
            FTP_HOST,
            FTP_USER,
            FTP_PASS,
            remote_ftp_path,
            progress_callback=upload_progress_callback
        )
        return success, None
    except Exception as e:
        return False, str(e)

def cleanup_empty_dirs(file_path):
    try:
        season_dir = os.path.dirname(file_path)
        if os.path.isdir(season_dir) and not os.listdir(season_dir):
            os.rmdir(season_dir)
            print(f"         🗑️ Deleted empty season folder: '{season_dir}'")
            series_dir = os.path.dirname(season_dir)
            if os.path.isdir(series_dir) and not os.listdir(series_dir):
                os.rmdir(series_dir)
                print(f"         🗑️ Deleted empty series folder: '{series_dir}'")
    except Exception as e:
        print(f"         ⚠️ Error during cleanup: {e}")

async def upload_local_files_to_filemoon():
    if not filemoon_client:
        return {"status": "error", "message": "FileMoon API key not configured. Uploads skipped."}
    if not FTP_HOST or not FTP_USER or not FTP_PASS:
        return {"status": "error", "message": "FTP credentials not configured in .env. FTP uploads skipped."}

    uploaded_count = 0
    failed_uploads = []
    files_to_upload = []

    if not os.path.isdir(DOWNLOAD_DIR):
        print(f"Download dir '{DOWNLOAD_DIR}' does not exist.")
        return {"status": "success", "uploaded_count": 0, "failed_uploads": [], "csv_report": None}

    for series_folder in sorted(os.listdir(DOWNLOAD_DIR)):
        series_path = os.path.join(DOWNLOAD_DIR, series_folder)
        if not os.path.isdir(series_path):
            continue
        series_name = series_folder.replace('_', ' ').strip()
        season_folders = [f for f in os.listdir(series_path) if os.path.isdir(os.path.join(series_path, f)) and f.lower().startswith("season")]
        season_folders.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)))
        for season_folder in season_folders:
            season_path = os.path.join(series_path, season_folder)
            # Support multiple video formats: .mkv, .mp4, .avi, .mov
            episode_files = [f for f in os.listdir(season_path) if f.lower().endswith((".mkv", ".mp4", ".avi", ".mov", ".srt"))]
            episode_files.sort(key=lambda x: extract_info_from_filename(x).get("episode_number", 0))
            for filename in episode_files:
                local_file_path = os.path.join(season_path, filename)
                remote_ftp_dir = os.path.join("/", series_name, season_folder)
                remote_ftp_path = os.path.join(remote_ftp_dir, filename)
                files_to_upload.append({
                    "local_path": local_file_path,
                    "remote_path": remote_ftp_path,
                    "filename": filename,
                    "series": series_name,
                    "season": season_folder
                })

    print(f"Found {len(files_to_upload)} files to process.")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    loop = asyncio.get_running_loop()

    async def upload_task(file_info):
        async with semaphore:
            success, error = await loop.run_in_executor(
                None,
                upload_single_file_sync,
                file_info["local_path"],
                file_info["remote_path"],
                file_info["filename"]
            )
            if success:
                print(f"\n         ✅ Finished: '{file_info['filename']}'")
                try:
                    os.remove(file_info['local_path'])
                    print(f"         🗑️ Deleted local file: '{file_info['local_path']}'")
                    cleanup_empty_dirs(file_info['local_path'])
                except OSError as e:
                    print(f"         ⚠️ Error deleting file: {e}")
                return True, None
            else:
                print(f"\n         ❌ Failed: '{file_info['filename']}' - {error if error else 'Unknown error'}")
                return False, f"{file_info['local_path']} (Error: {error})"

    tasks = [upload_task(f) for f in files_to_upload]
    if tasks:
        results = await asyncio.gather(*tasks)
        for success, error_msg in results:
            if success:
                uploaded_count += 1
            else:
                failed_uploads.append(error_msg)

    print(f"\n🎉 Completed FileMoon upload process. Total uploaded: {uploaded_count}, Failed: {len(failed_uploads)}")
    csv_file = await generate_filemoon_csv()
    return {
        "status": "success",
        "uploaded_count": uploaded_count,
        "failed_uploads": failed_uploads,
        "csv_report": csv_file
    }

async def generate_filemoon_csv():
    if not filemoon_client:
        return None
    print("\n📄 Generating FileMoon CSV report...")
    csv_filename = "filemoon_files.csv"
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_csv_sync, csv_filename)
        print(f"✅ CSV report saved to: {csv_filename}")
        return csv_filename
    except Exception as e:
        print(f"❌ Failed to generate CSV: {e}")
        return None

def _write_csv_sync(filename):
    with open(filename, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['file_code', 'title', 'file_size', 'uploaded', 'status', 'public']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        page = 1
        while True:
            response = filemoon_client.f_list(per_page="100", page=str(page))
            if not response or 'result' not in response or 'files' not in response['result']:
                break
            files = response['result']['files']
            if not files:
                break
            for file_data in files:
                writer.writerow({
                    'file_code': file_data.get('file_code', ''),
                    'title': file_data.get('title', ''),
                    'file_size': file_data.get('file_size', ''),
                    'uploaded': file_data.get('uploaded', ''),
                    'status': file_data.get('status', ''),
                    'public': file_data.get('public', '')
                })
            if len(files) < 100:
                break
            page += 1

# ============== ROUTES ==============

@app.route("/")
def index():
    return """
    <h1>Unified IMDb Scraper & FileMoon Bot Server</h1>
    <h2>Available Endpoints:</h2>
    <ul>
        <li><code>GET /scrape_imdb?query=SHOW_NAME</code> - Scrape IMDb data and save JSON</li>
        <li><code>GET /upload_to_filemoon</code> - Upload local files to FileMoon</li>
        <li><code>GET /health</code> - Health check</li>
    </ul>
    <h3>Examples:</h3>
    <ul>
        <li><a href="/scrape_imdb?query=The Boys">/scrape_imdb?query=The Boys</a></li>
    </ul>
    """

@app.route('/scrape_imdb', methods=['GET'])
def scrape_imdb_endpoint():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required. Use ?query=SHOW_NAME"}), 400

    try:
        print(f"Scraping request for: {query}")

        # 1. Scrape IMDb for full metadata (episodes, cast, etc.)
        print("Step 1: Scraping IMDb for metadata...")
        imdb_data = scrape_imdb(query)

        if not imdb_data:
            return jsonify({"error": "IMDb scraping failed"}), 500

        data = imdb_data

        # 2. Try to fill FileMoon URLs (this may replace placeholders)
        print("Filling FileMoon URLs...")
        try:
            data = fill_filemoon_urls(data)
        except Exception as e:
            print(f"Error filling FileMoon URLs (continuing anyway): {e}")

        # 3. STRICTLY keep only valid FileMoon /e/ episode URLs
        data, removed_count, removed_items = remove_non_filemoon_episode_urls(data)
        print(f"Filtered non-FileMoon/placeholder episodes before DB save. Removed {removed_count} episodes.")
        if removed_count:
            # optional: attach removed items for debugging (not saved to DB)
            data['_removed_episodes'] = removed_items

        # 4. Attach local subtitles if found
        print("Checking for local subtitles...")
        data = attach_local_subtitles(data, DOWNLOAD_DIR)

        # Save to Database (defensive: do not save if seasons_data becomes empty entirely)
        print(f"Saving to Database... Data keys: {list(data.keys())}")
        if "show_title" in data:
            print(f"Show Title to save: '{data['show_title']}'")

        seasons_left = data.get("seasons_data", [])
        if not seasons_left:
            print("No valid episodes left after filtering. Aborting DB save.")
            return jsonify({
                "status": "failed",
                "message": "No episodes with valid FileMoon /e/ URLs were found after processing.",
                "removed_placeholder_episodes": removed_count,
                "data_snapshot": {
                    "show_title": data.get("show_title"),
                    "seasons_count": 0
                }
            }), 200

        try:
            saved = db_utils.save_show_data(data)
        except Exception as e:
            print(f"Error saving to DB: {e}")
            saved = False

        if saved:
            print(f"✅ Data saved to MongoDB database.")
            return jsonify({
                "status": "success",
                "message": f"Data scraped and saved to database for '{query}'",
                "removed_placeholder_episodes": removed_count,
                "data": data
            })
        else:
            return jsonify({"error": "Failed to save data to database"}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/upload_to_filemoon", methods=["GET"])
async def upload_endpoint():
    result = await upload_local_files_to_filemoon()
    return jsonify(result)

@app.route("/shows", methods=["GET"])
def get_shows():
    shows = db_utils.get_all_shows()
    return jsonify(shows)

@app.route("/shows/<path:title>", methods=["GET"])
def get_show(title):
    data = db_utils.get_show_data(title)
    if not data:
        data = db_utils.get_show_data(title.replace("_", " "))
    if data:
        return jsonify(data)
    return jsonify({"error": "Show not found"}), 404

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "filemoon_configured": filemoon_client is not None,
        "ftp_configured": all([FTP_HOST, FTP_USER, FTP_PASS])
    })

if __name__ == "__main__":
    print("🚀 Starting Unified Server on port 5014...")
    print("📦 Initializing Database...")
    db_utils.init_db()
    print("📡 IMDb Scraper API: http://localhost:5014/scrape_imdb?query=SHOW_NAME")
    print("📤 FileMoon Upload API: http://localhost:5014/upload_to_filemoon")
    app.run(debug=False, host='0.0.0.0', port=5014)
