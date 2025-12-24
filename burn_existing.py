import os
import sys
from subtitle_generator import SubtitleGenerator

def scan_and_burn(directory):
    print(f"📂 Scanning directory: {directory}")
    
    # Initialize generator
    generator = SubtitleGenerator()
    
    video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.webm'}
    
    files_processed = 0
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            base, ext = os.path.splitext(file)
            if ext.lower() in video_extensions:
                video_path = os.path.join(root, file)
                subtitle_path = os.path.join(root, base + ".srt")
                
                # Check if subtitle exists and hasn't been burned yet
                # We mark burned subtitles by renaming them to .srt.burned
                if os.path.exists(subtitle_path):
                    print(f"\nFound pair: {file} + {base}.srt")
                    
                    success, output_path, error = generator.burn_subtitles(video_path, subtitle_path)
                    
                    if success:
                        print(f"✅ Successfully burned subtitles for: {file}")
                        # Delete subtitle file
                        try:
                            os.remove(subtitle_path)
                            print(f"🗑️ Deleted subtitle file: {os.path.basename(subtitle_path)}")
                        except Exception as e:
                            print(f"⚠️ Failed to delete subtitle file: {e}")
                        files_processed += 1
                    else:
                        print(f"❌ Failed to burn subtitles for {file}: {error}")
                
                elif os.path.exists(subtitle_path + ".burned"):
                    print(f"⏭️  Skipping {file} (already burned)")
                else:
                    # print(f"ℹ️  No subtitle found for {file}")
                    pass

    print(f"\n🎉 Finished processing. Total videos burned: {files_processed}")

if __name__ == "__main__":
    download_dir = "downloads/"
    if not os.path.exists(download_dir):
        print(f"❌ Directory not found: {download_dir}")
        sys.exit(1)
        
    scan_and_burn(download_dir)
