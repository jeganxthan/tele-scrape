#!/usr/bin/env python3
"""
Movie and Subtitle Uploader to FileMoon

This script uploads video files from the 'movie' directory to FileMoon via FTP,
then automatically uploads their corresponding subtitle files via the web interface.
"""

import os
import sys
import time
import csv
from pathlib import Path
from dotenv import load_dotenv
from fileMoon import FileMoon

# Load environment variables
load_dotenv()

# Configuration
MOVIE_DIR = os.path.join(os.getcwd(), "downloads")
FILEMOON_API_KEY = os.getenv("FILEMOON_API_KEY")
# Support both naming conventions
FILEMOON_FTP_HOST = os.getenv("FILEMOON_FTP_HOST") or os.getenv("FTP_HOST", "ftp.filemoon.sx")
FILEMOON_FTP_USER = os.getenv("FILEMOON_FTP_USER") or os.getenv("FTP_USER")
FILEMOON_FTP_PASS = os.getenv("FILEMOON_FTP_PASS") or os.getenv("FTP_PASS")
CSV_FILE = "filemoon_files.csv"

# Video extensions to process
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm')
SUBTITLE_EXTENSIONS = ('.srt', '.vtt', '.sub', '.ass')

def get_ftp_credentials():
    """Get FTP credentials from environment variables"""
    # FileMoon FTP credentials are typically:
    # Host: ftp.filemoonapi.com
    # User: Your email or username
    # Pass: Your API key or FTP password
    
    if FILEMOON_FTP_USER and FILEMOON_FTP_PASS:
        print(f"✅ Using FTP credentials from .env")
        return {
            'host': FILEMOON_FTP_HOST,
            'user': FILEMOON_FTP_USER,
            'pass': FILEMOON_FTP_PASS
        }
    else:
        print("⚠️ FTP credentials not found in .env")
        print("Please add to .env file:")
        print("  FILEMOON_FTP_USER=your_email_or_username")
        print("  FILEMOON_FTP_PASS=your_ftp_password_or_api_key")
        print("\nNote: Check FileMoon dashboard for FTP credentials")
        return None

def find_subtitle_for_video(video_path):
    """Find matching subtitle file for a video"""
    video_name = os.path.splitext(video_path)[0]
    
    # Check for subtitle with same name
    for ext in SUBTITLE_EXTENSIONS:
        subtitle_path = video_name + ext
        if os.path.exists(subtitle_path):
            return subtitle_path
    
    return None

def upload_video_to_filemoon(filemoon_client, video_path, ftp_creds, progress_callback=None):
    """Upload video file to FileMoon via FTP"""
    filename = os.path.basename(video_path)
    file_size = os.path.getsize(video_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"\n{'='*60}")
    print(f"📹 Uploading: {filename}")
    print(f"📊 Size: {file_size_mb:.2f} MB")
    print(f"{'='*60}")
    
    # Remote path on FTP server
    remote_path = f"/{filename}"
    
    # Default Progress callback if none provided
    def default_progress_callback(current, total, fname):
        percent = (current / total) * 100
        mb_current = current / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        print(f"\r⏳ Progress: {percent:.1f}% ({mb_current:.1f}/{mb_total:.1f} MB)", end='', flush=True)
        if progress_callback:
            progress_callback(current, total, fname)
    
    try:
        success = filemoon_client.ftp_upload(
            local_file_path=video_path,
            ftp_host=ftp_creds['host'],
            ftp_user=ftp_creds['user'],
            ftp_pass=ftp_creds['pass'],
            remote_file_path=remote_path,
            progress_callback=default_progress_callback
        )
        
        print()  # New line after progress
        
        if success:
            print(f"✅ Video uploaded successfully!")
            
            # Wait for FileMoon to process the file (indexing delay)
            print("⏳ Waiting 15s for FileMoon to index the file...")
            time.sleep(15)
            
            # Retry loop to get file info (FileMoon API can be slow to reflect new uploads)
            for attempt in range(3):
                print(f"🔍 Retrieval attempt {attempt + 1}/3...")
                file_list = filemoon_client.f_list(name=filename)
                if file_list.get('result') and file_list['result'].get('files'):
                    files = file_list['result']['files']
                    # Sort by created if multiple found, or just take first
                    if files:
                        file_code = files[0].get('file_code')
                        print(f"✅ File code retrieved: {file_code}")
                        return file_code
                
                if attempt < 2:
                    print("⚠️ Not found yet, waiting 10s before retry...")
                    time.sleep(10)
            
            print("❌ Failed to retrieve file code after multiple attempts.")
            return None
        else:
            print(f"❌ Upload failed")
            return None
            
    except Exception as e:
        print(f"\n❌ Upload error: {e}")
        return None

def update_csv(video_filename, file_code):
    """Update or create CSV with uploaded file info"""
    csv_exists = os.path.exists(CSV_FILE)
    
    # Read existing data
    existing_data = []
    fieldnames = ['filename', 'file_code']
    
    if csv_exists:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Get all fieldnames from existing CSV
            if reader.fieldnames:
                fieldnames = list(reader.fieldnames)
                # Ensure filename and file_code are present
                if 'filename' not in fieldnames:
                    fieldnames.insert(0, 'filename')
                if 'file_code' not in fieldnames:
                    fieldnames.insert(1, 'file_code')
            existing_data = list(reader)
    
    # Check if file already exists in CSV
    updated = False
    for row in existing_data:
        if row.get('filename') == video_filename:
            row['file_code'] = file_code
            updated = True
            break
    
    # Add new entry if not found
    if not updated:
        new_row = {field: '' for field in fieldnames}  # Initialize all fields
        new_row['filename'] = video_filename
        new_row['file_code'] = file_code
        existing_data.append(new_row)
    
    # Write back to CSV
    with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_data)
    
    print(f"✅ Updated CSV: {CSV_FILE}")

def upload_subtitle_for_video(video_filename, subtitle_path):
    """Upload subtitle using the filemoon_subtitle_uploader module"""
    try:
        import filemoon_subtitle_uploader
        
        print(f"\n📤 Uploading subtitle: {os.path.basename(subtitle_path)}")
        success = filemoon_subtitle_uploader.upload_subtitle_to_filemoon(
            video_filename,
            subtitle_path,
            headless=True
        )
        
        if success:
            print(f"✅ Subtitle uploaded successfully!")
        else:
            print(f"❌ Subtitle upload failed")
        
        return success
        
    except ImportError:
        print("⚠️ filemoon_subtitle_uploader not available, skipping subtitle upload")
        return False
    except Exception as e:
        print(f"❌ Error uploading subtitle: {e}")
        return False

def get_all_video_files(directory):
    """Find all video files in a directory recursively"""
    video_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(VIDEO_EXTENSIONS):
                # We store the relative path from the directory to keep it clean
                rel_path = os.path.relpath(os.path.join(root, file), directory)
                video_files.append(rel_path)
    return video_files

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload movies and subtitles to FileMoon")
    parser.add_argument("--skip-subtitles", action="store_true", help="Skip subtitle upload")
    parser.add_argument("--video-only", action="store_true", help="Only upload videos without subtitles")
    parser.add_argument("--delete", action="store_true", help="Delete local files after successful upload")
    args = parser.parse_args()
    
    # Validate configuration
    if not FILEMOON_API_KEY:
        print("❌ Error: FILEMOON_API_KEY not found in .env file")
        print("Please add: FILEMOON_API_KEY=your_api_key")
        return
    
    if not os.path.exists(MOVIE_DIR):
        print(f"❌ Error: Movie directory not found: {MOVIE_DIR}")
        return
    
    # Initialize FileMoon client
    print("🚀 Initializing FileMoon client...")
    filemoon = FileMoon(FILEMOON_API_KEY)
    
    # Get FTP credentials from environment
    print("🔑 Getting FTP credentials...")
    ftp_creds = get_ftp_credentials()
    if not ftp_creds:
        print("\n❌ Error: FTP credentials not configured")
        print("\nFileMoon requires FTP credentials to upload videos.")
        print("Add these to your .env file:")
        print("  FILEMOON_FTP_USER=your_email_or_username")
        print("  FILEMOON_FTP_PASS=your_ftp_password")
        print("\nTo find your FTP credentials:")
        print("  1. Login to FileMoon dashboard")
        print("  2. Go to Settings → FTP/Upload")
        print("  3. Copy your FTP username and password")
        return
    
    print(f"✅ FTP Host: {ftp_creds['host']}")
    
    # Get list of video files recursively
    video_files = get_all_video_files(MOVIE_DIR)
    
    if not video_files:
        print(f"⚠️ No video files found in {MOVIE_DIR}")
        return
    
    print(f"\n📁 Found {len(video_files)} video file(s)")
    
    # Statistics
    stats = {
        "videos_uploaded": 0,
        "videos_failed": 0,
        "subtitles_uploaded": 0,
        "subtitles_failed": 0,
        "subtitles_not_found": 0
    }
    
    # Process each video
    for idx, video_file in enumerate(video_files, 1):
        print(f"\n{'#'*60}")
        print(f"Processing {idx}/{len(video_files)}: {video_file}")
        print(f"{'#'*60}")
        
        video_path = os.path.join(MOVIE_DIR, video_file)
        
        # Upload video
        file_code = upload_video_to_filemoon(filemoon, video_path, ftp_creds)
        
        if file_code:
            stats["videos_uploaded"] += 1
            
            # Update CSV
            update_csv(video_file, file_code)
            
            # Upload subtitle if available and not skipped
            if not args.skip_subtitles and not args.video_only:
                subtitle_path = find_subtitle_for_video(video_path)
                
                if subtitle_path:
                    print(f"📝 Found subtitle: {os.path.basename(subtitle_path)}")
                    
                    # Wait a bit before uploading subtitle
                    time.sleep(3)
                    
                    if upload_subtitle_for_video(video_file, subtitle_path):
                        stats["subtitles_uploaded"] += 1
                        # Delete subtitle if --delete is set
                        if args.delete:
                            try:
                                os.remove(subtitle_path)
                                print(f"🗑️ Deleted local subtitle: {os.path.basename(subtitle_path)}")
                            except Exception as e:
                                print(f"⚠️ Error deleting subtitle: {e}")
                    else:
                        stats["subtitles_failed"] += 1
                else:
                    print("⚠️ No subtitle file found for this video")
                    stats["subtitles_not_found"] += 1
            
            # Delete video if --delete is set and video upload was successful
            if args.delete:
                try:
                    os.remove(video_path)
                    print(f"🗑️ Deleted local video: {video_file}")
                except Exception as e:
                    print(f"⚠️ Error deleting video: {e}")
        else:
            stats["videos_failed"] += 1
        
        # Small delay between uploads
        if idx < len(video_files):
            print("\n⏳ Waiting before next upload...")
            time.sleep(5)
    
    # Final summary
    print(f"\n{'='*60}")
    print("📊 UPLOAD SUMMARY")
    print(f"{'='*60}")
    print(f"Videos uploaded: {stats['videos_uploaded']}/{len(video_files)}")
    print(f"Videos failed: {stats['videos_failed']}")
    
    if not args.skip_subtitles and not args.video_only:
        print(f"Subtitles uploaded: {stats['subtitles_uploaded']}")
        print(f"Subtitles failed: {stats['subtitles_failed']}")
        print(f"Subtitles not found: {stats['subtitles_not_found']}")
    
    print(f"{'='*60}")
    print("✅ Upload process completed!")

if __name__ == "__main__":
    main()
