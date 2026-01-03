import os
import sys
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

# Import existing modules
import movie_metadata
import anime_metadata
import mkv
import subtitle_downloader
import movie_uploader
import filemoon_subtitle_uploader
import update_csv
import db_utils
from fileMoon import FileMoon

# Load environment variables
load_dotenv()

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "service": "tele-scrape-server"}), 200

@app.route('/scrape/movie', methods=['POST'])
def scrape_movie():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Missing 'name' in body"}), 400
    try:
        metadata = movie_metadata.scrape_movie_metadata(data['name'], scrape_type="movie")
        return jsonify({"status": "success", "data": metadata}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/scrape/series', methods=['POST'])
def scrape_series():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Missing 'name' in body"}), 400
    try:
        metadata = movie_metadata.scrape_movie_metadata(data['name'], scrape_type="series")
        return jsonify({"status": "success", "data": metadata}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/scrape/anime', methods=['POST'])
def scrape_anime():
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({"error": "Missing 'name' in body"}), 400
    try:
        metadata = anime_metadata.scrape_anime_meta(data['name'])
        return jsonify({"status": "success", "data": metadata}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/db/collections', methods=['GET'])
def get_db_collections():
    """Get content from MongoDB collections."""
    try:
        client = db_utils.get_db_connection()
        if not client: return jsonify({"error": "DB Connection failed"}), 500
        
        db = client[db_utils.DB_NAME]
        
        # Series
        series_coll = db[db_utils.COLLECTION_NAME]
        series = list(series_coll.find({}, {"show_title": 1, "created_at": 1, "_id": 0}).sort("show_title", 1))
        
        # Movies
        movie_coll = db[db_utils.MOVIE_COLLECTION_NAME]
        movies = list(movie_coll.find({}, {"title": 1, "created_at": 1, "_id": 0}).sort("title", 1))
        
        # Popular
        popular = db_utils.get_popular_titles()
        
        return jsonify({"status": "success", "data": {"movies": movies, "series": series, "popular": popular}}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/db/popular', methods=['POST'])
def add_popular():
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({"error": "Missing title"}), 400
        
    title = data['title']
    category = data.get('category', 'movie')
    
    res = db_utils.add_popular_title(title, category)
    if res:
         return jsonify({"status": "success", "id": res}), 200
    elif res is False:
         return jsonify({"status": "error", "message": "Already exists"}), 400
    else:
         return jsonify({"status": "error", "message": "Failed to add"}), 500

@app.route('/db/popular/<item_id>', methods=['DELETE'])
def delete_popular(item_id):
    res = db_utils.remove_popular_title(item_id)
    if res:
        return jsonify({"status": "success", "message": "Deleted"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to delete"}), 500

@app.route('/db/popular/reorder', methods=['PUT'])
def reorder_popular():
    data = request.get_json()
    if not data or 'ids' not in data:
        return jsonify({"error": "Missing 'ids' array"}), 400
    
    ids = data['ids']
    if not isinstance(ids, list):
        return jsonify({"error": "'ids' must be an array"}), 400
    
    res = db_utils.reorder_popular_titles(ids)
    if res:
        return jsonify({"status": "success", "message": "Reordered"}), 200
    else:
        return jsonify({"status": "error", "message": "Failed to reorder"}), 500

@app.route('/uploads/all', methods=['GET'])
def get_all_uploads():
    """Get all uploads from CSV."""
    csv_path = "filemoon_files.csv"
    if not os.path.exists(csv_path):
        return jsonify({"status": "success", "data": []}), 200
    
    try:
        entries = []
        import csv
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            entries = list(reader)
            
        # Return all, newest first
        all_entries = entries[::-1]
        return jsonify({"status": "success", "data": all_entries}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/process/mkv', methods=['POST'])
def process_mkv():
    """
    Trigger the MKV muxing and organization process.
    Uses hardcoded paths in mkv.py effectively, or we can look to make it dynamic if needed.
    For now, calling mkv.main() as requested to not change code heavily.
    """
    try:
        # mkv.main() processes files from /home/jegan/Desktop/movie/tele-scrape/movie
        # and moves to /home/jegan/Desktop/movie/tele-scrape/downloads
        mkv.main()
        return jsonify({"status": "success", "message": "MKV processing cycle completed."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/download/subtitles', methods=['POST'])
def download_subtitles():
    """
    Download subtitles for a specific movie.
    Body: { "movie_name": "Inception", "download_dir": "/optional/path" }
    """
    data = request.get_json()
    if not data or 'movie_name' not in data:
        return jsonify({"error": "Missing 'movie_name' in body"}), 400
    
    movie_name = data['movie_name']
    download_dir = data.get('download_dir', os.getcwd())
    
    try:
        path = Path(download_dir)
        subtitle_path = subtitle_downloader.download_subtitle(movie_name, path)
        if subtitle_path:
            return jsonify({"status": "success", "file": str(subtitle_path)}), 200
        else:
            return jsonify({"status": "error", "message": "Subtitle download failed"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

import threading

# Global state for upload progress
upload_status = {
    "is_uploading": False,
    "current_file": "",
    "current_index": 0,
    "total_files": 0,
    "current_file_percent": 0,
    "results": []
}

def run_upload_task(skip_subtitles, delete_after):
    global upload_status
    upload_status["is_uploading"] = True
    upload_status["results"] = []
    
    try:
        FILEMOON_API_KEY = os.getenv("FILEMOON_API_KEY")
        MOVIE_DIR = movie_uploader.MOVIE_DIR
        filemoon = FileMoon(FILEMOON_API_KEY)
        ftp_creds = movie_uploader.get_ftp_credentials()
        
        video_files = movie_uploader.get_all_video_files(MOVIE_DIR)
        upload_status["total_files"] = len(video_files)
        
        for idx, video_file in enumerate(video_files):
            upload_status["current_index"] = idx + 1
            upload_status["current_file"] = video_file
            upload_status["current_file_percent"] = 0
            
            # Absolute path for recursive uploads
            video_path = os.path.join(MOVIE_DIR, video_file)
            
            def progress_cb(current, total, fname):
                upload_status["current_file_percent"] = round((current / total) * 100, 1)

            file_code = movie_uploader.upload_video_to_filemoon(
                filemoon, video_path, ftp_creds, progress_callback=progress_cb
            )
            
            result = {"file": video_file, "uploaded": False, "file_code": None, "subtitle_uploaded": False}
            
            if file_code:
                result["uploaded"] = True
                result["file_code"] = file_code
                movie_uploader.update_csv(video_file, file_code)
                
                if not skip_subtitles:
                    subtitle_path = movie_uploader.find_subtitle_for_video(video_path)
                    if subtitle_path:
                        sub_success = movie_uploader.upload_subtitle_for_video(video_file, subtitle_path)
                        result["subtitle_uploaded"] = sub_success
                        if sub_success and delete_after:
                             try:
                                 os.remove(subtitle_path)
                                 print(f"🗑️ Deleted subtitle: {subtitle_path}")
                             except Exception as e:
                                 print(f"⚠️ Failed to delete sub {subtitle_path}: {e}")
                
                if delete_after:
                    try:
                        os.remove(video_path)
                        print(f"🗑️ Deleted video: {video_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete video {video_path}: {e}")
            
            upload_status["results"].append(result)
            
    except Exception as e:
        print(f"Error in upload thread: {e}")
    finally:
        upload_status["is_uploading"] = False

@app.route('/upload/movies', methods=['POST'])
def upload_movies():
    """
    Trigger upload in a background thread.
    """
    if upload_status["is_uploading"]:
        return jsonify({"status": "error", "message": "Upload already in progress"}), 400
        
    data = request.get_json() or {}
    skip_subtitles = data.get('skip_subtitles', False)
    # Default to True as requested
    delete_after = data.get('delete_after', True)
    
    thread = threading.Thread(target=run_upload_task, args=(skip_subtitles, delete_after))
    thread.start()
    
    return jsonify({"status": "success", "message": "Upload started in background"}), 202

@app.route('/upload/status', methods=['GET'])
def get_upload_status():
    """
    Polling endpoint for upload progress.
    """
    return jsonify(upload_status), 200



@app.route('/update/csv', methods=['POST'])
def trigger_update_csv():
    """
    Update the local CSV with data from FileMoon.
    """
    try:
        update_csv.main()
        return jsonify({"status": "success", "message": "CSV updated"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # Run on 0.0.0.0 to be accessible, port 5000 default
    app.run(host='0.0.0.0', port=5000, debug=True)
