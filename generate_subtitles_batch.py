#!/usr/bin/env python3
"""
Batch Subtitle Generator
Generates subtitles for all existing video files in the downloads directory.
"""

import os
import sys
from subtitle_generator import SubtitleGenerator

def find_all_videos(base_dir="downloads"):
    """Find all video files in the downloads directory."""
    video_extensions = ('.mkv', '.mp4', '.avi', '.mov')
    videos = []
    
    if not os.path.exists(base_dir):
        print(f"❌ Directory '{base_dir}' does not exist")
        return videos
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.lower().endswith(video_extensions):
                video_path = os.path.join(root, file)
                subtitle_path = os.path.splitext(video_path)[0] + '.srt'
                
                # Check if subtitle already exists
                if os.path.exists(subtitle_path):
                    print(f"⏭️  Skipping '{file}' (subtitle already exists)")
                else:
                    videos.append(video_path)
    
    return videos

def generate_subtitles_batch(videos, model_name="base", language=None):
    """Generate subtitles for a list of videos."""
    if not videos:
        print("✅ All videos already have subtitles!")
        return
    
    print(f"\n📊 Found {len(videos)} videos without subtitles")
    print(f"🎬 Using Whisper model: {model_name}")
    print(f"🌐 Language: {'Auto-detect' if not language else language}")
    print("\n" + "="*60)
    
    generator = SubtitleGenerator(model_name=model_name, language=language)
    
    success_count = 0
    failed_count = 0
    
    for idx, video_path in enumerate(videos, 1):
        print(f"\n[{idx}/{len(videos)}] Processing: {os.path.basename(video_path)}")
        print(f"📁 Path: {video_path}")
        
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        print(f"📊 Size: {file_size_mb:.1f} MB")
        
        success, subtitle_path, error = generator.generate_subtitles(video_path)
        
        if success:
            success_count += 1
            subtitle_size_kb = os.path.getsize(subtitle_path) / 1024
            print(f"✅ Success! Subtitle: {os.path.basename(subtitle_path)} ({subtitle_size_kb:.1f} KB)")
        else:
            failed_count += 1
            print(f"❌ Failed: {error}")
    
    print("\n" + "="*60)
    print(f"\n🎉 Batch processing complete!")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {failed_count}")
    print(f"📊 Total processed: {len(videos)}")

def main():
    print("="*60)
    print("Batch Subtitle Generator for Existing Videos")
    print("="*60)
    print()
    
    # Configuration
    DOWNLOAD_DIR = "downloads"
    WHISPER_MODEL = "base"  # Change to "tiny" for faster processing
    SUBTITLE_LANGUAGE = None  # None for auto-detect, or "en", "es", etc.
    
    # Allow command-line override
    if len(sys.argv) > 1:
        WHISPER_MODEL = sys.argv[1]
        print(f"📝 Using model from command line: {WHISPER_MODEL}")
    
    if len(sys.argv) > 2:
        SUBTITLE_LANGUAGE = sys.argv[2]
        print(f"🌐 Using language from command line: {SUBTITLE_LANGUAGE}")
    
    # Find all videos without subtitles
    print(f"🔍 Scanning '{DOWNLOAD_DIR}' for videos without subtitles...")
    videos = find_all_videos(DOWNLOAD_DIR)
    
    if not videos:
        print("\n✅ All videos already have subtitles! Nothing to do.")
        return
    
    # Show what will be processed
    print(f"\n📋 Videos to process:")
    for i, video in enumerate(videos, 1):
        print(f"  {i}. {os.path.relpath(video, DOWNLOAD_DIR)}")
    
    # Confirm before starting
    print(f"\n⚠️  This will process {len(videos)} videos.")
    print(f"⏱️  Estimated time: ~{len(videos) * 3}-{len(videos) * 5} minutes (with '{WHISPER_MODEL}' model)")
    
    response = input("\n❓ Continue? (y/n): ").strip().lower()
    if response != 'y':
        print("❌ Cancelled by user")
        return
    
    # Generate subtitles
    generate_subtitles_batch(videos, WHISPER_MODEL, SUBTITLE_LANGUAGE)

if __name__ == "__main__":
    main()
