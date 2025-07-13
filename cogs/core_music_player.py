# cogs/core_music_player.py

import discord
from discord.ext import commands
import os
import yt_dlp
import asyncio
import functools
import collections

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
        return f"**{self.title}** (Requested by {self.requester.mention})"

# --- MusicPlayer Cog (Core Logic - No Commands Here) ---
class MusicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = collections.deque() # Use deque for efficient queue operations
        self.current_song = None
        self.voice_client = None     # Discord VoiceClient instance for the guild
        self.is_playing = False
        self.music_task = None       # Task for playing music

        self.yt_dlp = yt_dlp.YoutubeDL(YTDL_OPTIONS)

    # This task continuously plays songs from the queue
    async def audio_player_task(self, ctx):
        # We need a way to get the ctx for sending messages from this task
        # It's best to pass the ctx from the command that initiated the playback
        # or store a reference to a text channel for sending messages.
        # For simplicity, we'll assume ctx is passed from the initial play command
        # and remains valid for sending messages.
        # A more robust solution might store ctx.channel.id and fetch it.

        while True:
            self.is_playing = False
            self.current_song = None

            try:
                # Wait for the next song in the queue
                if not self.queue:
                    # If queue is empty, wait for a new song to be added
                    await asyncio.sleep(1) # Small sleep to prevent busy-waiting
                    continue # Check again

                song = self.queue.popleft() # Get the next song from the left side of the deque
                self.current_song = song

            except asyncio.CancelledError:
                print("Music player task cancelled.")
                break
            except Exception as e:
                print(f"Error getting song from queue: {e}")
                break

            self.is_playing = True
            source = discord.FFmpegPCMAudio(self.current_song.source, **FFMPEG_OPTIONS)

            try:
                # Play the audio. The 'after' callback is called when the audio finishes.
                ctx.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next_song_event.set) if e is None else print(f'Player error: {e}'))
                await ctx.send(f"Now playing: {self.current_song}")
            except Exception as e:
                await ctx.send(f"Error playing song: {self.current_song.title} - {e}")
                print(f"Error playing song: {e}")
                self.is_playing = False
                self.current_song = None
                continue # Try to play the next song if there's an error with the current one

            # Wait until the current song finishes playing (signaled by the 'after' callback)
            self.next_song_event = asyncio.Event()
            await self.next_song_event.wait()

        # If queue is empty and bot is still in voice channel, disconnect after a delay
        # This block executes when the while loop breaks (e.g., queue is empty and no new songs are added)
        if ctx.voice_client and not self.is_playing and not self.queue:
            await asyncio.sleep(300) # Wait 5 minutes for inactivity
            if ctx.voice_client and not self.is_playing and not self.queue: # Re-check in case a song was added during sleep
                await ctx.voice_client.disconnect()
                # await ctx.send("Queue finished and I've left the voice channel due to inactivity.") # Cannot use ctx here after disconnect
                self.voice_client = None # Reset voice client reference

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # This listener handles cleanup if the bot is manually disconnected from voice
        if member == self.bot.user and before.channel is not None and after.channel is None:
            print("Bot disconnected from voice channel.")
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
