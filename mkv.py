import os
import subprocess
import shutil
from pathlib import Path
import subtitle_downloader

def mux_to_mkv(movie_dir):
    movie_path = Path(movie_dir)
    movie_name = movie_path.name
    
    mp4_files = list(movie_path.glob("*.mp4"))
    srt_files = list(movie_path.glob("*.srt"))
    
    if not mp4_files:
        print(f"No MP4 file found in {movie_dir}")
        return False
    
    # Check for subtitles, if missing try to download
    if not srt_files:
        print(f"No SRT file found in {movie_dir}. Attempting to download...")
        clean_name = subtitle_downloader.get_clean_movie_name(movie_name)
        downloaded_srt = subtitle_downloader.download_subtitle(clean_name, movie_path)
        
        if downloaded_srt:
            print(f"Subtitle downloaded: {downloaded_srt}")
            srt_files = [downloaded_srt]
        else:
            print(f"Failed to find or download subtitles for {movie_dir}")
            return False
    
    video_file = mp4_files[0]
    subtitle_file = srt_files[0]
    output_mkv = movie_path / f"{video_file.stem}.mkv"
    
    print(f"Muxing {video_file} and {subtitle_file} into {output_mkv}...")
    
    cmd = [
        "ffmpeg",
        "-i", str(video_file),
        "-i", str(subtitle_file),
        "-c", "copy",
        "-map", "0",
        "-map", "1",
        "-y",
        str(output_mkv)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"Successfully created {output_mkv}")
        
        # Delete all files EXCEPT the new MKV file
        print(f"Cleaning up {movie_dir}, keeping only the MKV...")
        for file in movie_path.iterdir():
            if file.is_file() and file != output_mkv:
                os.remove(file)
                print(f"Deleted: {file.name}")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error muxing {movie_dir}: {e}")
        return False

def main():
    base_dir = Path("/home/jegan/Desktop/movie/tele-scrape/movie")
    downloads_dir = Path("/home/jegan/Desktop/movie/tele-scrape/downloads")
    
    if not base_dir.exists():
        print(f"Base directory {base_dir} does not exist.")
        return

    # Ensure downloads directory exists
    downloads_dir.mkdir(parents=True, exist_ok=True)

    for folder in base_dir.iterdir():
        if folder.is_dir():
            print(f"Processing folder: {folder.name}")
            if mux_to_mkv(folder):
                # Find the generated MKV file
                mkv_files = list(folder.glob("*.mkv"))
                if mkv_files:
                    mkv_file = mkv_files[0]
                    target_path = downloads_dir / mkv_file.name
                    print(f"Moving {mkv_file.name} to {downloads_dir}...")
                    try:
                        if target_path.exists():
                            os.remove(target_path)
                        shutil.move(str(mkv_file), str(target_path))
                        print(f"Moved {mkv_file.name} to downloads.")
                        
                        # Remove the original folder
                        shutil.rmtree(folder)
                        print(f"Deleted folder: {folder}")
                    except Exception as e:
                        print(f"Error moving {mkv_file.name}: {e}")
                else:
                    print(f"No MKV file found in {folder} after muxing.")

if __name__ == "__main__":
    main()
