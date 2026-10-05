"""Environment loading and FFmpeg configuration; no secrets loaded on import."""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_settings():
    """Load the project-root .env, preserving explicitly supplied environment values."""
    load_dotenv(Path(__file__).resolve().parent.parent / '.env')
    return os.getenv('DISCORD_BOT_TOKEN')


def ffmpeg_path_is_configured():
    return os.getenv('FFMPEG_PATH') is not None


def ffmpeg_options():
    """Return fresh per-player options, accepting an executable or directory."""
    # FFmpeg options for playing audio
    options = {
        'options': '-vn',
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
    }

    # Get FFMPEG_PATH from environment variables
    ffmpeg_path = os.getenv('FFMPEG_PATH')
    if ffmpeg_path:
        normalized_ffmpeg_path = os.path.normpath(ffmpeg_path)
        if os.path.isdir(normalized_ffmpeg_path):
            ffmpeg_executable_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
            ffmpeg_executable_path = os.path.join(normalized_ffmpeg_path, ffmpeg_executable_name)
            if not os.path.exists(ffmpeg_executable_path):
                print(f"Warning: FFmpeg executable '{ffmpeg_executable_name}' not found in '{normalized_ffmpeg_path}'.")
                print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
                options['executable'] = None
            else:
                options['executable'] = ffmpeg_executable_path
                print(f"FFmpeg executable path adjusted to: {options['executable']}")
        else:
            options['executable'] = normalized_ffmpeg_path

        if options.get('executable') and not os.path.exists(options['executable']):
            print(f"Warning: FFmpeg executable not found at '{options['executable']}'.")
            print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
            options['executable'] = None
    else:
        print("FFMPEG_PATH not set in .env. Assuming ffmpeg is in system PATH.")

    return options
