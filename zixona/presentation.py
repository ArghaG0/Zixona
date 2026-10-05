"""Shared embed styling and duration formatting."""
import datetime
import discord

# --- Global Constants for MusicPlayer (can be shared with cog if needed) ---
EMBED_COLOR = discord.Color(0xFFB6C1) # Light Pink

EMOJI_PLAYING = "<a:MusicalHearts:1393976474888966308>"
EMOJI_PAUSED = "<:Spotify_Pause:1393976498179936317>"
EMOJI_ADDED = "<:pinkcheckmark:1393976477262807100>"
EMOJI_SKIPPED = "<:Skip:1393976495155839099>"
EMOJI_STOPPED = "⏹️"
EMOJI_JOINED = "<:screenshare_volume_max:1393976485643030661>"
EMOJI_DISCONNECTED = "<:SilverMute:1393976492261769247>"
EMOJI_ERROR = "<:pinkcrossmark:1393976480014401586>"
EMOJI_FETCHING = "<:SearchCloud:1393976489564700712>"
EMOJI_QUEUE = "<:Spotify_Queue:1393976501090783283>"
EMOJI_VOTE = "<:downvote:1393976467196481678>"
EMOJI_HELP = "<:pinkquestionmark:1393976483118055475>"
EMOJI_PLAYLIST = "<:list:1393976471193784352>"

# --- Helper Function for Duration Formatting ---
def format_duration(seconds):
    """Formats duration in seconds to HH:MM:SS or MM:SS."""
    if seconds is None:
        return "N/A"
    
    td = datetime.timedelta(seconds=int(seconds))
    
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

