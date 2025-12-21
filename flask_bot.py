import os
import re
import json
import asyncio
import concurrent.futures
import csv
from flask import Flask, jsonify
from dotenv import load_dotenv
from fileMoon import FileMoon  # Import the FileMoon class

# Load environment variables
load_dotenv()

app = Flask(__name__)

# ============== CONFIGURATION ==============
DOWNLOAD_DIR = "downloads/"      # where files will be saved
FILEMOON_API_KEY = os.getenv("FILEMOON_API_KEY")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
MAX_CONCURRENT_UPLOADS = 3
# ===========================================

# Initialize FileMoon client
filemoon_client = None
if FILEMOON_API_KEY:
    filemoon_client = FileMoon(FILEMOON_API_KEY)
    print("✅ FileMoon client initialized.")
else:
    print("⚠️ FILEMOON_API_KEY not found in .env. FileMoon uploads will be skipped.")

def extract_info_from_filename(filename):
    """Extracts series, season, and episode from a filename like 'Breaking_Bad_S01E01.mkv'."""
    info = {}
    match = re.match(r"^(.*?)_S(\d+)E(\d+)\.mkv$", filename, re.IGNORECASE)
    if match:
        info["series"] = match.group(1).replace('_', ' ').strip()
        info["season_number"] = int(match.group(2))
        info["episode_number"] = int(match.group(3))
    return info

def upload_progress_callback(current, total, file_name):
    """Callback function to display upload progress."""
    # Simplified progress to avoid garbled output with concurrency
    percentage = (current / total) * 100
    if int(percentage) % 20 == 0 and int(percentage) > 0: # Print every 20%
         print(f"         Uploading '{file_name}': {percentage:.0f}%", end='\r')

def upload_single_file_sync(local_file_path, remote_ftp_path, filename):
    """Synchronous wrapper for the upload to be run in a thread."""
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

async def upload_local_files_to_filemoon():
    if not filemoon_client:
        return {"status": "error", "message": "FileMoon API key not configured. Uploads skipped."}
    
    if not FTP_HOST or not FTP_USER or not FTP_PASS:
        return {"status": "error", "message": "FTP credentials not configured in .env. FTP uploads skipped."}

    uploaded_count = 0
    failed_uploads = []
    
    # Collect all files to upload
    files_to_upload = []

    # Sort series folders alphabetically
    for series_folder in sorted(os.listdir(DOWNLOAD_DIR)):
        series_path = os.path.join(DOWNLOAD_DIR, series_folder)
        if not os.path.isdir(series_path):
            continue

        series_name = series_folder.replace('_', ' ').strip()
        
        # Sort season folders numerically by season number
        season_folders = [f for f in os.listdir(series_path) if os.path.isdir(os.path.join(series_path, f)) and f.lower().startswith("season")]
        season_folders.sort(key=lambda x: int(re.search(r'(\d+)', x).group(1)))

        for season_folder in season_folders:
            season_path = os.path.join(series_path, season_folder)
            season_name = season_folder
            
            # Sort episode files numerically by episode number
            episode_files = [f for f in os.listdir(season_path) if f.lower().endswith((".mkv", ".srt"))]
            episode_files.sort(key=lambda x: extract_info_from_filename(x).get("episode_number", 0))

            for filename in episode_files:
                local_file_path = os.path.join(season_path, filename)
                remote_ftp_dir = os.path.join("/", series_name, season_name)
                remote_ftp_path = os.path.join(remote_ftp_dir, filename)
                
                files_to_upload.append({
                    "local_path": local_file_path,
                    "remote_path": remote_ftp_path,
                    "filename": filename,
                    "series": series_name,
                    "season": season_name
                })

    print(f"Found {len(files_to_upload)} files to process.")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_UPLOADS)
    loop = asyncio.get_running_loop()
    
    async def upload_task(file_info):
        async with semaphore:
            # Run the synchronous upload in a thread pool
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
                except OSError as e:
                    print(f"         ⚠️ Error deleting file: {e}")
                return True, None
            else:
                print(f"\n         ❌ Failed: '{file_info['filename']}' - {error if error else 'Unknown error'}")
                return False, f"{file_info['local_path']} (Error: {error})"

    # Create tasks
    tasks = [upload_task(f) for f in files_to_upload]
    
    if tasks:
        results = await asyncio.gather(*tasks)
        
        for success, error_msg in results:
            if success:
                uploaded_count += 1
            else:
                failed_uploads.append(error_msg)

    print(f"\n🎉 Completed FileMoon upload process. Total uploaded: {uploaded_count}, Failed: {len(failed_uploads)}")
    
    # Generate CSV after uploads
    csv_file = await generate_filemoon_csv()
    
    return {
        "status": "success", 
        "uploaded_count": uploaded_count, 
        "failed_uploads": failed_uploads,
        "csv_report": csv_file
    }

async def generate_filemoon_csv():
    """Fetches all files from FileMoon and saves them to a CSV file."""
    if not filemoon_client:
        return None

    print("\n📄 Generating FileMoon CSV report...")
    csv_filename = "filemoon_files.csv"
    
    try:
        # Run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_csv_sync, csv_filename)
        print(f"✅ CSV report saved to: {csv_filename}")
        return csv_filename
    except Exception as e:
        print(f"❌ Failed to generate CSV: {e}")
        return None

def _write_csv_sync(filename):
    """Synchronous helper to fetch files and write CSV."""
    with open(filename, mode='w', newline='', encoding='utf-8') as csv_file:
        fieldnames = ['file_code', 'title', 'file_size', 'uploaded', 'status', 'public']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        
        page = 1
        while True:
            # Fetch files page by page
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
            
            # Check if we have more pages (simple check: if we got fewer than requested, we're likely done)
            # But safer to just increment and check if next page returns empty
            if len(files) < 100:
                break
            page += 1

@app.route("/")
def index():
    return "Telegram FileMoon Bot Flask Server is running. Use /upload_to_filemoon to initiate local file uploads."

# curl "http://localhost:5000/upload_to_filemoon"

@app.route("/upload_to_filemoon", methods=["GET"])
async def upload_endpoint():
    result = await upload_local_files_to_filemoon()
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
