#!/usr/bin/env python3
"""
FileMoon Subtitle Generator
Downloads videos from FileMoon, generates subtitles, and uploads .srt files back to FileMoon.
"""

import os
import sys
import csv
import requests
from subtitle_generator import SubtitleGenerator
from fileMoon import FileMoon
from dotenv import load_dotenv

load_dotenv()

# Configuration
FILEMOON_API_KEY = os.getenv("FILEMOON_API_KEY")
FTP_HOST = os.getenv("FTP_HOST")
FTP_USER = os.getenv("FTP_USER")
FTP_PASS = os.getenv("FTP_PASS")
WHISPER_MODEL = "base"  # Change to "tiny" for faster processing
TEMP_DIR = "temp_subtitle_generation"

def read_filemoon_csv(csv_file="filemoon_files.csv"):
    """Read FileMoon files from CSV."""
    files = []
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return files
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            files.append(row)
    
    return files

def download_video_from_filemoon(file_code, output_path, filemoon_client):
    """Download video from FileMoon."""
    try:
        # Get file info to get download URL
        info = filemoon_client.f_info(file_code)
        
        if not info or 'result' not in info:
            print(f"❌ Could not get file info for {file_code}")
            return False
        
        # Get direct download URL (this varies by FileMoon API)
        # You may need to adjust this based on FileMoon's actual API response
        download_url = info['result'].get('download_url') or info['result'].get('url')
        
        if not download_url:
            print(f"⚠️  No download URL found for {file_code}")
            return False
        
        print(f"   📥 Downloading from FileMoon...")
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if int(progress) % 10 == 0:
                            print(f"   ⏳ Download progress: {progress:.0f}%", end='\r')
        
        print(f"\n   ✅ Downloaded: {os.path.basename(output_path)}")
        return True
        
    except Exception as e:
        print(f"   ❌ Download failed: {e}")
        return False

def upload_subtitle_to_filemoon(subtitle_path, remote_path, filemoon_client):
    """Upload subtitle file to FileMoon via FTP."""
    try:
        print(f"   📤 Uploading subtitle to FileMoon...")
        
        success = filemoon_client.ftp_upload(
            subtitle_path,
            FTP_HOST,
            FTP_USER,
            FTP_PASS,
            remote_path
        )
        
        if success:
            print(f"   ✅ Uploaded: {os.path.basename(subtitle_path)}")
            return True
        else:
            print(f"   ❌ Upload failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Upload error: {e}")
        return False

def process_filemoon_videos():
    """Main processing function."""
    
    # Initialize FileMoon client
    if not FILEMOON_API_KEY:
        print("❌ FILEMOON_API_KEY not found in .env")
        return
    
    filemoon_client = FileMoon(FILEMOON_API_KEY)
    
    # Create temp directory
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Read CSV
    print("📄 Reading FileMoon files from CSV...")
    files = read_filemoon_csv()
    
    if not files:
        print("❌ No files found in CSV")
        return
    
    # Filter video files only
    video_files = [f for f in files if f.get('title', '').lower().endswith(('.mkv', '.mp4', '.avi', '.mov'))]
    
    print(f"📊 Found {len(video_files)} video files in FileMoon")
    
    if not video_files:
        print("❌ No video files found")
        return
    
    # Show files
    print("\n📋 Video files:")
    for i, f in enumerate(video_files[:10], 1):  # Show first 10
        print(f"  {i}. {f.get('title', 'Unknown')}")
    if len(video_files) > 10:
        print(f"  ... and {len(video_files) - 10} more")
    
    # Confirm
    print(f"\n⚠️  This will:")
    print(f"  1. Download {len(video_files)} videos temporarily")
    print(f"  2. Generate subtitles for each")
    print(f"  3. Upload subtitle files to FileMoon")
    print(f"  4. Delete temporary files")
    print(f"\n⏱️  Estimated time: ~{len(video_files) * 5}-{len(video_files) * 8} minutes")
    
    response = input("\n❓ Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Cancelled")
        return
    
    # Initialize subtitle generator
    generator = SubtitleGenerator(model_name=WHISPER_MODEL, language="en")
    
    success_count = 0
    failed_count = 0
    
    # Process each video
    for idx, file_info in enumerate(video_files, 1):
        file_code = file_info.get('file_code', '')
        title = file_info.get('title', 'Unknown')
        
        print(f"\n{'='*60}")
        print(f"[{idx}/{len(video_files)}] Processing: {title}")
        print(f"{'='*60}")
        
        # Temporary paths
        temp_video = os.path.join(TEMP_DIR, title)
        temp_subtitle = os.path.splitext(temp_video)[0] + '.srt'
        remote_subtitle = title.replace('.mkv', '.srt').replace('.mp4', '.srt').replace('.avi', '.srt').replace('.mov', '.srt')
        
        try:
            # Step 1: Download video
            print("Step 1: Downloading video from FileMoon...")
            if not download_video_from_filemoon(file_code, temp_video, filemoon_client):
                print(f"⚠️  Skipping {title} (download failed)")
                failed_count += 1
                continue
            
            # Step 2: Generate subtitle
            print("\nStep 2: Generating subtitle...")
            success, subtitle_path, error = generator.generate_subtitles(temp_video)
            
            if not success:
                print(f"⚠️  Subtitle generation failed: {error}")
                failed_count += 1
                # Clean up video
                if os.path.exists(temp_video):
                    os.remove(temp_video)
                continue
            
            # Step 3: Upload subtitle
            print("\nStep 3: Uploading subtitle to FileMoon...")
            if upload_subtitle_to_filemoon(subtitle_path, remote_subtitle, filemoon_client):
                success_count += 1
            else:
                failed_count += 1
            
            # Step 4: Clean up
            print("\nStep 4: Cleaning up temporary files...")
            if os.path.exists(temp_video):
                os.remove(temp_video)
                print(f"   🗑️  Deleted: {os.path.basename(temp_video)}")
            if os.path.exists(subtitle_path):
                os.remove(subtitle_path)
                print(f"   🗑️  Deleted: {os.path.basename(subtitle_path)}")
            
        except Exception as e:
            print(f"❌ Error processing {title}: {e}")
            failed_count += 1
            # Clean up on error
            for temp_file in [temp_video, temp_subtitle]:
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except:
                        pass
    
    # Summary
    print(f"\n{'='*60}")
    print(f"🎉 Processing Complete!")
    print(f"{'='*60}")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📊 Total: {len(video_files)}")
    
    # Clean up temp directory
    try:
        os.rmdir(TEMP_DIR)
    except:
        pass

if __name__ == "__main__":
    print("="*60)
    print("FileMoon Subtitle Generator")
    print("="*60)
    print()
    
    process_filemoon_videos()
