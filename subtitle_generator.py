import os
import sys
import subprocess
from typing import Optional, Tuple
import warnings

# Suppress FP16 warnings from Whisper
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")


class SubtitleGenerator:
    """
    Generate subtitles from video files using OpenAI's Whisper model.
    Supports automatic language detection and SRT format output.
    """
    
    def __init__(self, model_name: str = "base", language: Optional[str] = None):
        """
        Initialize the subtitle generator.
        
        Args:
            model_name: Whisper model to use (tiny, base, small, medium, large)
            language: Language code (e.g., 'en', 'es', 'ja') or None for auto-detect
        """
        self.model_name = model_name
        self.language = language
        self.model = None
        
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is installed."""
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _load_model(self):
        """Lazy load the Whisper model."""
        if self.model is None:
            try:
                import whisper
                print(f"📝 Loading Whisper '{self.model_name}' model (first time may take a while)...")
                self.model = whisper.load_model(self.model_name)
                print(f"✅ Whisper model loaded successfully")
            except ImportError:
                raise ImportError(
                    "Whisper is not installed. Please run: pip install openai-whisper"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load Whisper model: {e}")
    
    def _format_timestamp(self, seconds: float) -> str:
        """
        Convert seconds to SRT timestamp format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _generate_srt(self, segments: list) -> str:
        """
        Generate SRT format subtitle content from Whisper segments.
        
        Args:
            segments: List of transcription segments from Whisper
            
        Returns:
            SRT formatted subtitle string
        """
        srt_content = []
        
        for i, segment in enumerate(segments, start=1):
            start_time = self._format_timestamp(segment['start'])
            end_time = self._format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            srt_content.append(f"{i}")
            srt_content.append(f"{start_time} --> {end_time}")
            srt_content.append(text)
            srt_content.append("")  # Empty line between subtitles
        
        return "\n".join(srt_content)
    
    def generate_subtitles(
        self,
        video_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Generate subtitles for a video file.
        
        Args:
            video_path: Path to the video file
            output_path: Path for the output SRT file (optional, defaults to video_path with .srt)
            progress_callback: Optional callback function for progress updates
            
        Returns:
            Tuple of (success: bool, subtitle_path: str or None, error_message: str or None)
        """
        # Validate video file exists
        if not os.path.exists(video_path):
            return False, None, f"Video file not found: {video_path}"
        
        # Check ffmpeg
        if not self._check_ffmpeg():
            return False, None, "ffmpeg is not installed. Please install ffmpeg to generate subtitles."
        
        # Determine output path
        if output_path is None:
            base_path = os.path.splitext(video_path)[0]
            output_path = f"{base_path}.srt"
        
        try:
            # Load model
            self._load_model()
            
            if progress_callback:
                progress_callback("Extracting audio and transcribing...")
            
            print(f"🎤 Transcribing audio from: {os.path.basename(video_path)}")
            
            # Transcribe with Whisper
            transcribe_options = {
                "task": "transcribe",
                "verbose": False
            }
            
            if self.language:
                transcribe_options["language"] = self.language
            
            result = self.model.transcribe(video_path, **transcribe_options)
            
            # Detect language if not specified
            detected_language = result.get('language', 'unknown')
            print(f"🌐 Detected language: {detected_language}")
            
            # Generate SRT content
            if progress_callback:
                progress_callback("Generating subtitle file...")
            
            srt_content = self._generate_srt(result['segments'])
            
            # Write to file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
            
            print(f"✅ Subtitles saved to: {os.path.basename(output_path)}")
            
            return True, output_path, None
            
        except Exception as e:
            error_msg = f"Failed to generate subtitles: {str(e)}"
            print(f"⚠️ {error_msg}")
            return False, None, error_msg
    
    def generate_subtitles_batch(
        self,
        video_paths: list,
        progress_callback: Optional[callable] = None
    ) -> dict:
        """
        Generate subtitles for multiple video files.
        
        Args:
            video_paths: List of video file paths
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary mapping video paths to (success, subtitle_path, error) tuples
        """
        results = {}
        total = len(video_paths)
        
        for idx, video_path in enumerate(video_paths, start=1):
            print(f"\n[{idx}/{total}] Processing: {os.path.basename(video_path)}")
            
            success, subtitle_path, error = self.generate_subtitles(
                video_path,
                progress_callback=progress_callback
            )
            
            results[video_path] = (success, subtitle_path, error)
        
        return results


def main():
    """CLI interface for testing subtitle generation."""
    if len(sys.argv) < 2:
        print("Usage: python subtitle_generator.py <video_file> [model_name] [language]")
        print("Example: python subtitle_generator.py video.mkv base en")
        print("\nAvailable models: tiny, base, small, medium, large")
        sys.exit(1)
    
    video_file = sys.argv[1]
    model_name = sys.argv[2] if len(sys.argv) > 2 else "base"
    language = sys.argv[3] if len(sys.argv) > 3 else None
    
    generator = SubtitleGenerator(model_name=model_name, language=language)
    success, subtitle_path, error = generator.generate_subtitles(video_file)
    
    if success:
        print(f"\n✅ Success! Subtitle file: {subtitle_path}")
    else:
        print(f"\n❌ Failed: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main()
