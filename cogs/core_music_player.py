# cogs/core_music_player.py

import discord
from discord.ext import commands
import os
import yt_dlp
import asyncio
import functools
import collections
import logging # Import logging module

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- yt-dlp options for audio extraction ---
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

# --- FFmpeg options for playing audio ---
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# --- Song Class to represent a song in the queue ---
class Song:
    def __init__(self, source, title, url, requester):
        self.source = source
        self.title = title
        self.url = url
        self.requester = requester

    def __str__(self):
        return f"**[{self.title}]({self.url})**"

# --- MusicPlayer Cog (Core Logic - No Commands Here) ---
class MusicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = collections.deque()
        self.current_song = None
        self.voice_client = None
        self.is_playing = False
        self.music_task = None

        self.yt_dlp = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    async def audio_player_task(self, ctx):
        logging.info("Audio player task started.")
        while True:
            self.is_playing = False
            self.current_song = None

            try:
                if not self.queue:
                    logging.info("Queue is empty, waiting for next song.")
                    await asyncio.sleep(1)
                    continue

                song = self.queue.popleft()
                self.current_song = song
                logging.info(f"Pulled song from queue: {song.title}")

            except asyncio.CancelledError:
                logging.info("Audio player task cancelled gracefully.")
                break
            except Exception as e:
                logging.error(f"Error getting song from queue: {e}", exc_info=True)
                break

            self.is_playing = True
            
            logging.info(f"Attempting to create FFmpegPCMAudio source for: {self.current_song.source}")
            logging.info(f"FFmpeg Options: {FFMPEG_OPTIONS}")
            
            # Get FFMPEG_PATH from the bot object (set in main.py)
            ffmpeg_executable_path = os.path.join(self.bot.ffmpeg_path, "ffmpeg.exe") if self.bot.ffmpeg_path else "ffmpeg"
            logging.info(f"Using FFmpeg executable path: {ffmpeg_executable_path}")

            try:
                # Explicitly provide the path to the ffmpeg executable
                source = discord.FFmpegPCMAudio(self.current_song.source, executable=ffmpeg_executable_path, **FFMPEG_OPTIONS)
                logging.info("FFmpegPCMAudio source created successfully.")
            except Exception as e:
                logging.error(f"Failed to create FFmpegPCMAudio source: {e}", exc_info=True)
                error_embed = discord.Embed(
                    title="Playback Error",
                    description=f"Could not prepare audio for **{self.current_song.title}**: FFmpeg issue. Error: `{e}`\n"
                                f"Please ensure FFmpeg is correctly installed and the `FFMPEG_PATH` environment variable is set to your FFmpeg `bin` folder.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                self.is_playing = False
                self.current_song = None
                continue # Try next song in queue

            try:
                logging.info(f"Playing audio for {self.current_song.title} in voice client.")
                ctx.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next_song_event.set) if e is None else logging.error(f'Player error in after callback: {e}', exc_info=True))

                embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"{self.current_song}",
                    color=discord.Color.from_rgb(112, 161, 255)
                )
                embed.set_footer(text=f"Requested by {self.current_song.requester.display_name}", icon_url=self.current_song.requester.avatar.url if self.current_song.requester.avatar else discord.Embed.Empty)
                await ctx.send(embed=embed)
                logging.info(f"Sent 'Now Playing' embed for {self.current_song.title}.")

            except Exception as e:
                logging.error(f"Error during voice client play operation: {e}", exc_info=True)
                error_embed = discord.Embed(
                    title="Playback Error",
                    description=f"Could not play **{self.current_song.title}** in voice channel. Error: `{e}`",
                    color=discord.Color.red()
                )
                await ctx.send(embed=error_embed)
                self.is_playing = False
                self.current_song = None
                continue

            self.next_song_event = asyncio.Event()
            logging.info(f"Waiting for {self.current_song.title} to finish.")
            await self.next_song_event.wait()
            logging.info(f"Finished waiting for {self.current_song.title}.")


        logging.info("Audio player task loop finished.")
        if ctx.voice_client and not self.is_playing and not self.queue:
            logging.info("Queue empty and bot idle. Waiting 5 minutes before disconnecting.")
            await asyncio.sleep(300)
            if ctx.voice_client and not self.is_playing and not self.queue:
                logging.info("Disconnecting due to inactivity.")
                await ctx.voice_client.disconnect()
                self.voice_client = None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and before.channel is not None and after.channel is None:
            logging.info("Bot detected disconnection from voice channel via on_voice_state_update.")
            if self.music_task:
                self.music_task.cancel()
                self.music_task = None
            self.queue.clear()
            self.is_playing = False
            self.current_song = None
            self.voice_client = None

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(MusicPlayer(bot))
