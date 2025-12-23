"""Video processor for creating title cards and concatenating videos.

Uses FFmpeg for video processing operations.
"""

import os
import subprocess
import tempfile
import requests
from typing import Dict, Optional
from utils.logger import log_info, log_error, log_warning


class VideoProcessingError(Exception):
    """Raised when video processing fails."""
    pass


class VideoProcessor:
    """Process videos using FFmpeg - create title cards and concatenate."""

    # Title card duration in seconds
    DEFAULT_TITLE_CARD_DURATION = 1.0

    # Video settings
    FRAME_RATE = 30
    VIDEO_CODEC = 'libx264'
    AUDIO_CODEC = 'aac'
    PIXEL_FORMAT = 'yuv420p'

    # Background music
    BACKGROUND_MUSIC_URL = "https://mqemiteirxwscxtamdtj.supabase.co/storage/v1/object/public/media/background-music/deep-house-lounge-music-349539.mp3"
    BACKGROUND_MUSIC_CACHE_PATH = "/tmp/background_music.mp3"

    def __init__(self, temp_dir: Optional[str] = None):
        """Initialize the video processor.

        Args:
            temp_dir: Directory for temporary files. Defaults to system temp.
        """
        self.temp_dir = temp_dir or tempfile.gettempdir()
        self._verify_ffmpeg()
        log_info("VideoProcessor initialized")

    def _verify_ffmpeg(self):
        """Verify FFmpeg is available."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise VideoProcessingError("FFmpeg not working properly")
            log_info("FFmpeg verified")
        except FileNotFoundError:
            raise VideoProcessingError(
                "FFmpeg not found. Please install FFmpeg."
            )

    def _run_ffmpeg(self, args: list, description: str) -> subprocess.CompletedProcess:
        """Run FFmpeg command with error handling."""
        cmd = ['ffmpeg', '-y'] + args  # -y to overwrite output
        log_info(f"Running FFmpeg: {description}")
        log_info(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                log_error(f"FFmpeg error: {result.stderr}")
                raise VideoProcessingError(f"FFmpeg failed: {result.stderr[-500:]}")

            return result

        except subprocess.TimeoutExpired:
            raise VideoProcessingError("FFmpeg timed out")

    def download_video(self, url: str, output_path: Optional[str] = None) -> str:
        """Download video from URL to local file.

        Args:
            url: Video URL (e.g., HeyGen CDN URL)
            output_path: Optional output path. Auto-generated if not provided.

        Returns:
            Path to downloaded video file.
        """
        if output_path is None:
            output_path = os.path.join(self.temp_dir, f"video_{os.getpid()}.mp4")

        log_info(f"Downloading video from: {url[:80]}...")

        response = requests.get(url, stream=True, timeout=120)
        response.raise_for_status()

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(output_path)
        log_info(f"Downloaded video: {output_path} ({file_size / 1024 / 1024:.2f} MB)")

        return output_path

    def create_title_card_video(
        self,
        image_path: str,
        output_path: Optional[str] = None,
        duration: float = DEFAULT_TITLE_CARD_DURATION,
        fps: Optional[float] = None
    ) -> str:
        """Convert an image to a video clip (title card).

        Args:
            image_path: Path to the thumbnail image (JPEG)
            output_path: Optional output path. Auto-generated if not provided.
            duration: Duration of the title card in seconds.
            fps: Frame rate. Defaults to FRAME_RATE constant if not provided.

        Returns:
            Path to the title card video file.
        """
        if output_path is None:
            output_path = os.path.join(self.temp_dir, f"title_card_{os.getpid()}.mp4")

        if fps is None:
            fps = self.FRAME_RATE

        log_info(f"Creating {duration}s title card from: {image_path} at {fps} fps")

        # FFmpeg command to create video from image
        # -loop 1: loop the image
        # -t: duration
        # -framerate: output frame rate
        # -pix_fmt: pixel format for compatibility
        args = [
            '-loop', '1',
            '-i', image_path,
            '-c:v', self.VIDEO_CODEC,
            '-t', str(duration),
            '-pix_fmt', self.PIXEL_FORMAT,
            '-r', str(fps),
            output_path
        ]

        self._run_ffmpeg(args, "Creating title card video")
        log_info(f"Title card created: {output_path}")

        return output_path

    def get_video_properties(self, video_path: str) -> Dict:
        """Get video properties using FFprobe.

        Returns dict with width, height, duration, has_audio.
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            '-show_format',
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            log_warning(f"FFprobe failed: {result.stderr}")
            return {}

        import json
        data = json.loads(result.stdout)

        props = {
            'has_audio': False,
            'width': None,
            'height': None,
            'duration': None
        }

        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                props['width'] = stream.get('width')
                props['height'] = stream.get('height')
            elif stream.get('codec_type') == 'audio':
                props['has_audio'] = True

        if 'format' in data:
            props['duration'] = float(data['format'].get('duration', 0))

        return props

    def get_video_info(self, video_path: str) -> dict:
        """Get video frame rate and audio sample rate using ffprobe."""
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        import json
        data = json.loads(result.stdout)

        info = {'fps': 30, 'sample_rate': 48000}  # defaults

        for stream in data.get('streams', []):
            if stream['codec_type'] == 'video':
                # Parse frame rate (e.g., "30/1" or "25/1")
                fps_str = stream.get('r_frame_rate', '30/1')
                num, den = map(int, fps_str.split('/'))
                info['fps'] = num / den if den else 30
            elif stream['codec_type'] == 'audio':
                info['sample_rate'] = int(stream.get('sample_rate', 48000))

        return info

    def concatenate_videos(
        self,
        title_card_path: str,
        main_video_path: str,
        output_path: Optional[str] = None,
        sample_rate: Optional[int] = None
    ) -> str:
        """Concatenate title card with main video.

        Handles cases where main video has audio but title card doesn't.

        Args:
            title_card_path: Path to title card video
            main_video_path: Path to main HeyGen video
            output_path: Optional output path. Auto-generated if not provided.
            sample_rate: Audio sample rate. Defaults to 48000 if not provided.

        Returns:
            Path to concatenated video file.
        """
        if output_path is None:
            output_path = os.path.join(self.temp_dir, f"combined_{os.getpid()}.mp4")

        log_info("Concatenating title card with main video...")

        # Default sample rate if not provided
        if sample_rate is None:
            sample_rate = 48000

        # Get properties of main video
        main_props = self.get_video_properties(main_video_path)
        has_audio = main_props.get('has_audio', True)
        width = main_props.get('width', 1080)
        height = main_props.get('height', 1920)

        log_info(f"Main video: {width}x{height}, has_audio={has_audio}, sample_rate={sample_rate}")

        # Create concat file list
        concat_list_path = os.path.join(self.temp_dir, f"concat_{os.getpid()}.txt")

        if has_audio:
            # Need to add silent audio to title card before concatenating
            title_card_with_audio = os.path.join(
                self.temp_dir, f"title_card_audio_{os.getpid()}.mp4"
            )

            # Add silent audio to title card using detected sample rate
            args = [
                '-i', title_card_path,
                '-f', 'lavfi',
                '-i', f'anullsrc=channel_layout=stereo:sample_rate={sample_rate}',
                '-c:v', 'copy',
                '-c:a', self.AUDIO_CODEC,
                '-shortest',
                title_card_with_audio
            ]
            self._run_ffmpeg(args, "Adding silent audio to title card")

            title_card_for_concat = title_card_with_audio
        else:
            title_card_for_concat = title_card_path

        # Write concat list
        with open(concat_list_path, 'w') as f:
            f.write(f"file '{title_card_for_concat}'\n")
            f.write(f"file '{main_video_path}'\n")

        # Concatenate using concat demuxer
        # Re-encode audio to ensure sync even if there are slight differences
        args = [
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-ar', str(sample_rate),
            output_path
        ]

        self._run_ffmpeg(args, "Concatenating videos")

        # Clean up temp files
        try:
            os.remove(concat_list_path)
            if has_audio and os.path.exists(title_card_with_audio):
                os.remove(title_card_with_audio)
        except Exception as e:
            log_warning(f"Could not clean up temp files: {e}")

        output_size = os.path.getsize(output_path)
        log_info(f"Combined video created: {output_path} ({output_size / 1024 / 1024:.2f} MB)")

        return output_path

    def process_video_with_title_card(
        self,
        thumbnail_path: str,
        video_url: str,
        output_path: Optional[str] = None,
        title_card_duration: float = DEFAULT_TITLE_CARD_DURATION
    ) -> Dict:
        """Complete pipeline: create title card and prepend to video.

        Args:
            thumbnail_path: Path to thumbnail image with text overlay
            video_url: URL of the HeyGen video
            output_path: Optional output path for final video
            title_card_duration: Duration of title card in seconds

        Returns:
            Dict with:
                - success: bool
                - output_path: str (path to combined video)
                - title_card_duration: float
                - error: str (if failed)
        """
        try:
            # Step 1: Download main video
            main_video_path = self.download_video(video_url)

            # Step 2: Probe main video to get fps and sample_rate
            video_info = self.get_video_info(main_video_path)
            fps = video_info.get('fps', 30)
            sample_rate = video_info.get('sample_rate', 48000)
            log_info(f"Detected video properties: fps={fps}, sample_rate={sample_rate}")

            # Step 3: Create title card video from thumbnail with matching fps
            title_card_path = self.create_title_card_video(
                thumbnail_path,
                duration=title_card_duration,
                fps=fps
            )

            # Step 4: Concatenate with matching sample_rate
            combined_path = self.concatenate_videos(
                title_card_path,
                main_video_path,
                sample_rate=sample_rate
            )

            # Step 5: Add background music
            log_info("Step 5: Adding background music...")
            if output_path is None:
                output_path = os.path.join(self.temp_dir, f"final_{os.getpid()}.mp4")

            video_with_music_path = self.add_background_music(
                video_path=combined_path,
                output_path=output_path,
                volume=0.2,
                fade_duration=2.0
            )
            log_info("Background music added successfully")

            # Clean up intermediate files
            try:
                os.remove(main_video_path)
                os.remove(title_card_path)
                os.remove(combined_path)
            except Exception as e:
                log_warning(f"Could not clean up intermediate files: {e}")

            return {
                'success': True,
                'output_path': video_with_music_path,
                'title_card_duration': title_card_duration
            }

        except Exception as e:
            log_error(f"Video processing failed: {e}")
            import traceback
            log_error(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }

    def cleanup_temp_files(self, *paths):
        """Clean up temporary files."""
        for path in paths:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    log_info(f"Cleaned up: {path}")
                except Exception as e:
                    log_warning(f"Could not remove {path}: {e}")

    def _download_music(self, music_url: str) -> str:
        """Download music file if not already cached.

        Args:
            music_url: URL of the music file to download.

        Returns:
            Path to the local music file.
        """
        cache_path = self.BACKGROUND_MUSIC_CACHE_PATH

        # Check if file is already cached
        if os.path.exists(cache_path):
            file_size = os.path.getsize(cache_path)
            if file_size > 0:
                log_info(f"Using cached music file: {cache_path} ({file_size / 1024 / 1024:.2f} MB)")
                return cache_path

        log_info(f"Downloading background music from: {music_url[:80]}...")

        try:
            response = requests.get(music_url, stream=True, timeout=120)
            response.raise_for_status()

            with open(cache_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(cache_path)
            log_info(f"Downloaded music: {cache_path} ({file_size / 1024 / 1024:.2f} MB)")
            return cache_path

        except Exception as e:
            log_error(f"Failed to download music: {e}")
            raise VideoProcessingError(f"Failed to download background music: {e}")

    def _get_audio_duration(self, audio_path: str) -> float:
        """Get duration of an audio file using FFprobe.

        Args:
            audio_path: Path to the audio file.

        Returns:
            Duration in seconds.
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            audio_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            log_warning(f"FFprobe failed for audio: {result.stderr}")
            return 0.0

        import json
        data = json.loads(result.stdout)

        if 'format' in data:
            return float(data['format'].get('duration', 0))

        return 0.0

    def add_background_music(
        self,
        video_path: str,
        music_url: Optional[str] = None,
        output_path: Optional[str] = None,
        volume: float = 0.2,
        fade_duration: float = 2.0
    ) -> str:
        """Add background music to a video.

        Args:
            video_path: Path to the input video file
            music_url: URL of the music file. Uses default if not provided.
            output_path: Optional output path. Auto-generated if not provided.
            volume: Volume of background music (0.0 to 1.0). Default 0.2 (20%)
            fade_duration: Duration of fade out at end in seconds. Default 2.0

        Returns:
            Path to the video with background music added.
        """
        log_info(f"Adding background music to video: {video_path}")

        # Use default music URL if not provided
        if music_url is None:
            music_url = self.BACKGROUND_MUSIC_URL
            log_info("Using default background music URL")

        # Download or get cached music
        music_path = self._download_music(music_url)

        # Get video properties
        video_props = self.get_video_properties(video_path)
        video_duration = video_props.get('duration', 0)
        has_audio = video_props.get('has_audio', False)

        if video_duration <= 0:
            raise VideoProcessingError("Could not determine video duration")

        log_info(f"Video duration: {video_duration:.2f}s, has_audio: {has_audio}")

        # Get music duration
        music_duration = self._get_audio_duration(music_path)
        log_info(f"Music duration: {music_duration:.2f}s")

        if music_duration <= 0:
            raise VideoProcessingError("Could not determine music duration")

        # Generate output path if not provided
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_path = os.path.join(self.temp_dir, f"{base_name}_with_music_{os.getpid()}.mp4")

        # Calculate fade start time (fade_duration seconds before end)
        fade_start = max(0, video_duration - fade_duration)

        # Build the filter complex
        # Strategy:
        # - If video is longer than music: loop the music
        # - Apply volume adjustment to music
        # - Apply fade out at the end
        # - Mix with original audio (if present) or just use the music

        if video_duration > music_duration:
            # Need to loop the music
            loop_count = int(video_duration / music_duration) + 1
            log_info(f"Video longer than music, looping {loop_count} times")

            if has_audio:
                # Mix looped music with original audio
                filter_complex = (
                    f"[1:a]aloop=loop={loop_count}:size={int(music_duration * 48000)},"
                    f"atrim=0:{video_duration},"
                    f"volume={volume},"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[music];"
                    f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                )
            else:
                # No original audio, just use the music
                filter_complex = (
                    f"[1:a]aloop=loop={loop_count}:size={int(music_duration * 48000)},"
                    f"atrim=0:{video_duration},"
                    f"volume={volume},"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[aout]"
                )
        else:
            # Music is longer than or equal to video, trim and fade
            log_info("Music longer than or equal to video, trimming with fade out")

            if has_audio:
                # Mix trimmed music with original audio
                filter_complex = (
                    f"[1:a]atrim=0:{video_duration},"
                    f"volume={volume},"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[music];"
                    f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
                )
            else:
                # No original audio, just use the trimmed music
                filter_complex = (
                    f"[1:a]atrim=0:{video_duration},"
                    f"volume={volume},"
                    f"afade=t=out:st={fade_start}:d={fade_duration}[aout]"
                )

        # Build FFmpeg command
        args = [
            '-i', video_path,
            '-i', music_path,
            '-filter_complex', filter_complex,
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', self.AUDIO_CODEC,
            '-shortest',
            output_path
        ]

        self._run_ffmpeg(args, "Adding background music")

        output_size = os.path.getsize(output_path)
        log_info(f"Video with music created: {output_path} ({output_size / 1024 / 1024:.2f} MB)")

        return output_path
