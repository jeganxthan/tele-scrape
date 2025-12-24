import os
import shutil
import subprocess
from burn_existing import scan_and_burn

def create_dummy_video(filename):
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=640x480:d=1",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        filename
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def create_dummy_subtitle(filename):
    content = """1
00:00:00,000 --> 00:00:01,000
Test Subtitle
"""
    with open(filename, "w") as f:
        f.write(content)

def main():
    test_dir = "test_downloads"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    try:
        print("Creating test files...")
        video_path = os.path.join(test_dir, "video1.mkv")
        sub_path = os.path.join(test_dir, "video1.srt")
        
        create_dummy_video(video_path)
        create_dummy_subtitle(sub_path)
        
        print("Running scan_and_burn...")
        scan_and_burn(test_dir)
        
        # Verify
        if not os.path.exists(sub_path):
            print("✅ Subtitle file deleted")
        else:
            print("❌ Subtitle file still exists")
            
        if os.path.exists(video_path):
            print("✅ Video file exists")
        else:
            print("❌ Video file missing")
            
    finally:
        # Cleanup
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    main()
