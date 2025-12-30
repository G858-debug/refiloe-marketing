"""Reel composer for stitching video clips with music and text overlays.

Creates Instagram/Facebook Reels by combining video clips, adding background music,
and overlaying text with various styles using FFmpeg.
"""

import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Dict, List, Optional

import requests

from utils.logger import log_debug, log_error, log_info, log_warning


class ReelComposerError(Exception):
    """Raised when reel composition fails."""
    pass


class ReelComposer:
    """Compose video reels by stitching clips with music and text overlays.

    Creates vertical 9:16 format videos suitable for Instagram/Facebook Reels
    by combining multiple video clips, adding background music at configurable
    volume, and overlaying styled text at specified timestamps.
    """

    # Video settings for Instagram/Facebook Reels
    OUTPUT_WIDTH = 1080
    OUTPUT_HEIGHT = 1920
    FRAME_RATE = 30
    VIDEO_CODEC = 'libx264'
    AUDIO_CODEC = 'aac'
    PIXEL_FORMAT = 'yuv420p'

    # Default clip settings
    DEFAULT_CLIP_DURATION = 5.0  # seconds per clip
    DEFAULT_TOTAL_CLIPS = 6
    DEFAULT_MUSIC_VOLUME = 0.2  # 20%
    DEFAULT_FADE_DURATION = 3.0  # seconds

    # Temp directory for processing
    TEMP_DIR = "/tmp/refiloe_reels"
    OUTPUT_DIR = "/home/claude"

    # Font settings (using DejaVu Sans - commonly available on Linux)
    DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FALLBACK_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    # Brand colors
    BRAND_PURPLE = "#7C3AED"

    # Text overlay style presets
    TEXT_STYLES = {
        "hook": {
            "fontsize": 48,
            "fontcolor": "white",
            "shadowcolor": "black",
            "shadowx": 2,
            "shadowy": 2,
            "box": 0,
        },
        "point": {
            "fontsize": 32,
            "fontcolor": "white",
            "box": 1,
            "boxcolor": "black@0.6",
            "boxborderw": 10,
        },
        "cta": {
            "fontsize": 36,
            "fontcolor": "white",
            "box": 1,
            "boxcolor": "0x7C3AED",  # Refiloe brand purple
            "boxborderw": 15,
        },
    }

    # Position presets (x, y coordinates as expressions for drawtext)
    POSITION_PRESETS = {
        "center": {"x": "(w-text_w)/2", "y": "(h-text_h)/2"},
        "bottom_third": {"x": "(w-text_w)/2", "y": "h*0.75-text_h/2"},
        "top": {"x": "(w-text_w)/2", "y": "h*0.1"},
    }

    def __init__(
        self,
        temp_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
    ):
        """Initialize the reel composer.

        Args:
            temp_dir: Directory for temporary files. Defaults to /tmp/refiloe_reels.
            output_dir: Directory for output files. Defaults to /home/claude.
        """
        self.temp_dir = temp_dir or self.TEMP_DIR
        self.output_dir = output_dir or self.OUTPUT_DIR

        # Ensure directories exist
        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        # Verify FFmpeg is available
        self._verify_ffmpeg()

        # Determine available font
        self.font_path = self._get_available_font()

        log_info(f"ReelComposer initialized (temp={self.temp_dir}, output={self.output_dir})")

    def _verify_ffmpeg(self) -> None:
        """Verify FFmpeg is available on the system."""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise ReelComposerError("FFmpeg not working properly")
            log_info("FFmpeg verified")
        except FileNotFoundError:
            raise ReelComposerError(
                "FFmpeg not found. Please install FFmpeg."
            )

    def _get_available_font(self) -> str:
        """Get an available font path for text overlays."""
        for font_path in [self.DEFAULT_FONT, self.FALLBACK_FONT]:
            if os.path.exists(font_path):
                log_debug(f"Using font: {font_path}")
                return font_path

        # Try to find any DejaVu font
        font_search_paths = [
            "/usr/share/fonts/truetype/dejavu/",
            "/usr/share/fonts/dejavu/",
            "/usr/share/fonts/",
        ]

        for search_path in font_search_paths:
            if os.path.exists(search_path):
                for font_file in os.listdir(search_path):
                    if font_file.endswith('.ttf'):
                        font_path = os.path.join(search_path, font_file)
                        log_debug(f"Using fallback font: {font_path}")
                        return font_path

        log_warning("No TTF font found, text overlays may not render correctly")
        return "Sans"  # FFmpeg default font

    def _run_ffmpeg(
        self,
        args: List[str],
        description: str,
        timeout: int = 600,
    ) -> subprocess.CompletedProcess:
        """Run FFmpeg command with error handling.

        Args:
            args: FFmpeg command arguments (without 'ffmpeg' prefix).
            description: Human-readable description of the operation.
            timeout: Timeout in seconds. Defaults to 600 (10 minutes).

        Returns:
            CompletedProcess instance with command results.

        Raises:
            ReelComposerError: If FFmpeg command fails.
        """
        cmd = ['ffmpeg', '-y'] + args  # -y to overwrite output
        log_info(f"Running FFmpeg: {description}")
        log_debug(f"Command: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                log_error(f"FFmpeg error: {result.stderr[-1000:]}")
                raise ReelComposerError(
                    f"FFmpeg failed for '{description}': {result.stderr[-500:]}"
                )

            return result

        except subprocess.TimeoutExpired:
            raise ReelComposerError(f"FFmpeg timed out for '{description}'")

    def _download_video(
        self,
        url: str,
        output_path: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """Download video from URL to local file.

        Args:
            url: Video URL to download.
            output_path: Optional output path. Auto-generated if not provided.
            timeout: Download timeout in seconds.

        Returns:
            Path to downloaded video file.

        Raises:
            ReelComposerError: If download fails.
        """
        if output_path is None:
            ext = url.split('.')[-1].split('?')[0] or 'mp4'
            output_path = os.path.join(
                self.temp_dir,
                f"clip_{uuid.uuid4().hex[:8]}.{ext}"
            )

        log_info(f"Downloading video from: {url[:80]}...")

        try:
            response = requests.get(url, stream=True, timeout=timeout)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            file_size = os.path.getsize(output_path)
            log_info(f"Downloaded video: {output_path} ({file_size / 1024 / 1024:.2f} MB)")

            return output_path

        except requests.RequestException as e:
            raise ReelComposerError(f"Failed to download video from {url}: {e}")

    def _get_video_duration(self, video_path: str) -> float:
        """Get video duration using FFprobe.

        Args:
            video_path: Path to video file.

        Returns:
            Duration in seconds.
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                log_warning(f"FFprobe failed: {result.stderr}")
                return 0.0

            import json
            data = json.loads(result.stdout)
            return float(data.get('format', {}).get('duration', 0))

        except Exception as e:
            log_warning(f"Could not get video duration: {e}")
            return 0.0

    def _scale_and_pad_video(
        self,
        input_path: str,
        output_path: str,
    ) -> str:
        """Scale and pad video to 9:16 format.

        Args:
            input_path: Path to input video.
            output_path: Path for output video.

        Returns:
            Path to scaled/padded video.
        """
        # Scale to fit width, then pad to correct height maintaining aspect ratio
        filter_complex = (
            f"scale={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={self.OUTPUT_WIDTH}:{self.OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1"
        )

        args = [
            '-i', input_path,
            '-vf', filter_complex,
            '-c:v', self.VIDEO_CODEC,
            '-pix_fmt', self.PIXEL_FORMAT,
            '-r', str(self.FRAME_RATE),
            '-c:a', self.AUDIO_CODEC,
            '-ar', '48000',
            output_path
        ]

        self._run_ffmpeg(args, "Scaling video to 9:16")
        return output_path

    def _concatenate_videos(
        self,
        video_paths: List[str],
        output_path: str,
    ) -> str:
        """Concatenate multiple videos into one.

        Args:
            video_paths: List of video file paths to concatenate.
            output_path: Path for output concatenated video.

        Returns:
            Path to concatenated video.

        Raises:
            ReelComposerError: If concatenation fails.
        """
        if not video_paths:
            raise ReelComposerError("No videos provided for concatenation")

        # Create concat list file
        concat_list_path = os.path.join(self.temp_dir, f"concat_{uuid.uuid4().hex[:8]}.txt")

        with open(concat_list_path, 'w') as f:
            for video_path in video_paths:
                # Escape single quotes in path
                escaped_path = video_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        log_info(f"Concatenating {len(video_paths)} videos...")

        args = [
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c', 'copy',
            output_path
        ]

        try:
            self._run_ffmpeg(args, f"Concatenating {len(video_paths)} videos")
        finally:
            # Clean up concat list
            if os.path.exists(concat_list_path):
                os.remove(concat_list_path)

        return output_path

    def _add_music(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        volume: float = DEFAULT_MUSIC_VOLUME,
        fade_duration: float = DEFAULT_FADE_DURATION,
    ) -> str:
        """Add background music to video with fade-out.

        Args:
            video_path: Path to input video.
            music_path: Path to music file.
            output_path: Path for output video.
            volume: Music volume (0.0 to 1.0). Defaults to 0.2 (20%).
            fade_duration: Fade-out duration in seconds. Defaults to 3.0.

        Returns:
            Path to video with music.

        Raises:
            ReelComposerError: If adding music fails.
        """
        if not os.path.exists(music_path):
            raise ReelComposerError(f"Music file not found: {music_path}")

        # Get video duration for fade calculation
        video_duration = self._get_video_duration(video_path)
        if video_duration <= 0:
            # Default to 30 seconds if we can't determine duration
            video_duration = 30.0

        fade_start = max(0, video_duration - fade_duration)

        log_info(f"Adding music at {volume * 100:.0f}% volume with {fade_duration}s fade-out")

        # Filter complex: adjust volume and add fade-out to music
        filter_complex = (
            f"[1:a]volume={volume},"
            f"afade=t=out:st={fade_start}:d={fade_duration}[music];"
            f"[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )

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
        return output_path

    def _add_music_to_silent_video(
        self,
        video_path: str,
        music_path: str,
        output_path: str,
        volume: float = DEFAULT_MUSIC_VOLUME,
        fade_duration: float = DEFAULT_FADE_DURATION,
    ) -> str:
        """Add background music to a video that has no audio track.

        Args:
            video_path: Path to input video (silent).
            music_path: Path to music file.
            output_path: Path for output video.
            volume: Music volume (0.0 to 1.0). Defaults to 0.2 (20%).
            fade_duration: Fade-out duration in seconds. Defaults to 3.0.

        Returns:
            Path to video with music.
        """
        video_duration = self._get_video_duration(video_path)
        if video_duration <= 0:
            video_duration = 30.0

        fade_start = max(0, video_duration - fade_duration)

        log_info(f"Adding music to silent video at {volume * 100:.0f}% volume")

        filter_complex = (
            f"[1:a]volume={volume},"
            f"afade=t=out:st={fade_start}:d={fade_duration}[aout]"
        )

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

        self._run_ffmpeg(args, "Adding music to silent video")
        return output_path

    def _escape_text_for_ffmpeg(self, text: str) -> str:
        """Escape text for FFmpeg drawtext filter.

        Args:
            text: Text to escape.

        Returns:
            Escaped text safe for FFmpeg.
        """
        # Escape special characters for FFmpeg drawtext
        text = text.replace("\\", "\\\\")
        text = text.replace("'", "\\'")
        text = text.replace(":", "\\:")
        text = text.replace("[", "\\[")
        text = text.replace("]", "\\]")
        text = text.replace(",", "\\,")
        text = text.replace(";", "\\;")
        return text

    def add_text_overlay(
        self,
        video_path: str,
        overlays: List[Dict],
        output_path: Optional[str] = None,
    ) -> str:
        """Add text overlays to video at specified timestamps.

        Args:
            video_path: Path to input video.
            overlays: List of overlay specifications. Each overlay dict contains:
                - text: Text to display
                - start_time: Start time in seconds
                - duration: Duration in seconds
                - position: 'center', 'bottom_third', or 'top'
                - style: 'hook', 'point', or 'cta'
            output_path: Optional output path. Auto-generated if not provided.

        Returns:
            Path to video with text overlays.

        Raises:
            ReelComposerError: If adding overlays fails.
        """
        if not overlays:
            log_warning("No text overlays provided, returning original video")
            return video_path

        if output_path is None:
            output_path = os.path.join(
                self.temp_dir,
                f"overlay_{uuid.uuid4().hex[:8]}.mp4"
            )

        log_info(f"Adding {len(overlays)} text overlays")

        # Build drawtext filter chain
        drawtext_filters = []

        for i, overlay in enumerate(overlays):
            text = overlay.get('text', '')
            if not text:
                continue

            start_time = overlay.get('start_time', 0)
            duration = overlay.get('duration', 3)
            end_time = start_time + duration
            position = overlay.get('position', 'center')
            style_name = overlay.get('style', 'point')

            # Get style settings
            style = self.TEXT_STYLES.get(style_name, self.TEXT_STYLES['point'])

            # Get position settings
            pos = self.POSITION_PRESETS.get(position, self.POSITION_PRESETS['center'])

            # Escape text for FFmpeg
            escaped_text = self._escape_text_for_ffmpeg(text)

            # Build drawtext filter
            filter_parts = [
                f"drawtext=text='{escaped_text}'",
                f"fontfile='{self.font_path}'",
                f"fontsize={style['fontsize']}",
                f"fontcolor={style['fontcolor']}",
                f"x={pos['x']}",
                f"y={pos['y']}",
                f"enable='between(t,{start_time},{end_time})'",
            ]

            # Add shadow for hook style
            if style.get('shadowcolor'):
                filter_parts.append(f"shadowcolor={style['shadowcolor']}")
                filter_parts.append(f"shadowx={style.get('shadowx', 2)}")
                filter_parts.append(f"shadowy={style.get('shadowy', 2)}")

            # Add box background for point/cta styles
            if style.get('box'):
                filter_parts.append(f"box={style['box']}")
                filter_parts.append(f"boxcolor={style['boxcolor']}")
                filter_parts.append(f"boxborderw={style.get('boxborderw', 10)}")

            drawtext_filters.append(":".join(filter_parts))

        if not drawtext_filters:
            log_warning("No valid text overlays found")
            return video_path

        # Chain all drawtext filters with commas
        video_filter = ",".join(drawtext_filters)

        args = [
            '-i', video_path,
            '-vf', video_filter,
            '-c:v', self.VIDEO_CODEC,
            '-pix_fmt', self.PIXEL_FORMAT,
            '-c:a', 'copy',
            output_path
        ]

        self._run_ffmpeg(args, f"Adding {len(drawtext_filters)} text overlays")
        return output_path

    def _check_video_has_audio(self, video_path: str) -> bool:
        """Check if video has an audio stream.

        Args:
            video_path: Path to video file.

        Returns:
            True if video has audio, False otherwise.
        """
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_streams',
            video_path
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return False

            import json
            data = json.loads(result.stdout)
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'audio':
                    return True
            return False

        except Exception:
            return False

    def compose_reel(
        self,
        video_urls: List[str],
        text_overlays: List[Dict],
        music_path: str,
        output_filename: Optional[str] = None,
        music_volume: float = DEFAULT_MUSIC_VOLUME,
        fade_duration: float = DEFAULT_FADE_DURATION,
    ) -> str:
        """Compose a reel from video clips with music and text overlays.

        Downloads video clips, concatenates them, adds background music at
        specified volume with fade-out, and applies text overlays.

        Args:
            video_urls: List of video URLs to download and combine.
                Expected: 6 clips of ~5 seconds each for a 30-second reel.
            text_overlays: List of text overlay specifications. Each dict contains:
                - text: Text to display
                - start_time: Start time in seconds
                - duration: Duration in seconds
                - position: 'center', 'bottom_third', or 'top'
                - style: 'hook' (bold, large), 'point' (medium with background),
                         or 'cta' (bold with brand purple background)
            music_path: Path to background music file.
            output_filename: Optional output filename. Auto-generated if not provided.
            music_volume: Music volume from 0.0 to 1.0. Defaults to 0.2 (20%).
            fade_duration: Fade-out duration in seconds. Defaults to 3.0.

        Returns:
            Path to the final composed video file.

        Raises:
            ReelComposerError: If composition fails at any step.

        Example:
            composer = ReelComposer()

            video_urls = [
                "https://example.com/clip1.mp4",
                "https://example.com/clip2.mp4",
                # ... 6 clips total
            ]

            text_overlays = [
                {
                    "text": "The #1 mistake trainers make",
                    "start_time": 0,
                    "duration": 4,
                    "position": "center",
                    "style": "hook"
                },
                {
                    "text": "Here's how to fix it",
                    "start_time": 10,
                    "duration": 3,
                    "position": "bottom_third",
                    "style": "point"
                },
                {
                    "text": "Follow for more tips!",
                    "start_time": 27,
                    "duration": 3,
                    "position": "center",
                    "style": "cta"
                }
            ]

            result = composer.compose_reel(
                video_urls=video_urls,
                text_overlays=text_overlays,
                music_path="/path/to/music.mp3"
            )
        """
        if not video_urls:
            raise ReelComposerError("No video URLs provided")

        if not music_path or not os.path.exists(music_path):
            raise ReelComposerError(f"Music file not found: {music_path}")

        log_info(f"Starting reel composition with {len(video_urls)} clips")

        # Generate unique session ID for temp files
        session_id = uuid.uuid4().hex[:8]
        session_dir = os.path.join(self.temp_dir, f"session_{session_id}")
        os.makedirs(session_dir, exist_ok=True)

        try:
            # Step 1: Download all video clips
            log_info("Step 1: Downloading video clips...")
            downloaded_clips = []

            for i, url in enumerate(video_urls):
                try:
                    clip_path = os.path.join(session_dir, f"clip_{i:02d}.mp4")
                    self._download_video(url, clip_path)
                    downloaded_clips.append(clip_path)
                except ReelComposerError as e:
                    log_error(f"Failed to download clip {i + 1}: {e}")
                    # Continue with remaining clips
                    continue

            if not downloaded_clips:
                raise ReelComposerError("All video downloads failed")

            log_info(f"Downloaded {len(downloaded_clips)}/{len(video_urls)} clips")

            # Step 2: Scale and normalize all clips to 9:16
            log_info("Step 2: Scaling clips to 9:16 format...")
            scaled_clips = []

            for i, clip_path in enumerate(downloaded_clips):
                scaled_path = os.path.join(session_dir, f"scaled_{i:02d}.mp4")
                self._scale_and_pad_video(clip_path, scaled_path)
                scaled_clips.append(scaled_path)

            # Step 3: Concatenate all clips
            log_info("Step 3: Concatenating clips...")
            concat_path = os.path.join(session_dir, "concatenated.mp4")
            self._concatenate_videos(scaled_clips, concat_path)

            # Step 4: Add text overlays
            log_info("Step 4: Adding text overlays...")
            if text_overlays:
                overlay_path = os.path.join(session_dir, "with_overlays.mp4")
                self.add_text_overlay(concat_path, text_overlays, overlay_path)
            else:
                overlay_path = concat_path

            # Step 5: Add background music
            log_info("Step 5: Adding background music...")

            # Generate output filename if not provided
            if output_filename is None:
                output_filename = f"reel_{session_id}.mp4"

            final_output_path = os.path.join(self.output_dir, output_filename)

            # Check if video has audio
            has_audio = self._check_video_has_audio(overlay_path)

            if has_audio:
                self._add_music(
                    overlay_path,
                    music_path,
                    final_output_path,
                    volume=music_volume,
                    fade_duration=fade_duration
                )
            else:
                self._add_music_to_silent_video(
                    overlay_path,
                    music_path,
                    final_output_path,
                    volume=music_volume,
                    fade_duration=fade_duration
                )

            final_size = os.path.getsize(final_output_path)
            log_info(
                f"Reel composition complete: {final_output_path} "
                f"({final_size / 1024 / 1024:.2f} MB)"
            )

            return final_output_path

        except Exception as e:
            log_error(f"Reel composition failed: {e}")
            raise ReelComposerError(f"Failed to compose reel: {e}")

        finally:
            # Clean up session directory
            try:
                shutil.rmtree(session_dir)
                log_debug(f"Cleaned up session directory: {session_dir}")
            except Exception as e:
                log_warning(f"Could not clean up session directory: {e}")

    def cleanup_temp_files(self) -> None:
        """Clean up all temporary files in the temp directory."""
        try:
            if os.path.exists(self.temp_dir):
                for item in os.listdir(self.temp_dir):
                    item_path = os.path.join(self.temp_dir, item)
                    try:
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    except Exception as e:
                        log_warning(f"Could not remove {item_path}: {e}")
                log_info("Cleaned up temporary files")
        except Exception as e:
            log_warning(f"Error cleaning up temp files: {e}")
