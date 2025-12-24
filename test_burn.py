import os
import subprocess
from subtitle_generator import SubtitleGenerator

def create_dummy_video(filename="test_video.mkv"):
    # Create a 1-second black video with silent audio
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", "color=c=black:s=640x480:d=1",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264", "-c:a", "aac", "-shortest",
        filename
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return filename

def create_dummy_subtitle(filename="test_video.srt"):
    content = """1
00:00:00,000 --> 00:00:01,000
Hello World
"""
    with open(filename, "w") as f:
        f.write(content)
    return filename

def main():
    video_path = "test_video.mkv"
    subtitle_path = "test_video.srt"
    
    try:
        print("Creating dummy files...")
        create_dummy_video(video_path)
        create_dummy_subtitle(subtitle_path)
        
        print("Initializing generator...")
        generator = SubtitleGenerator()
        
        print("Testing burn_subtitles...")
        success, output_path, error = generator.burn_subtitles(video_path, subtitle_path)
        
        if success:
            print(f"✅ Success! Output: {output_path}")
            # Verify file exists and is different from original (timestamp check or size)
            if os.path.exists(output_path):
                print("File exists.")
            else:
                print("❌ File missing!")
        else:
            print(f"❌ Failed: {error}")
            
    finally:
        # Cleanup
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(subtitle_path):
            os.remove(subtitle_path)

if __name__ == "__main__":
    main()
