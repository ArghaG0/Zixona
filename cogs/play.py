# cogs/play.py

import discord
from discord.ext import commands
import asyncio
import functools
import yt_dlp

# Import the core music player cog and Song class, and YTDL options
from .core_music_player import MusicPlayer, Song, YTDL_OPTIONS

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # We'll use the yt_dlp instance from the MusicPlayer cog
        # self.yt_dlp = yt_dlp.YoutubeDL(YTDL_OPTIONS) # No need for a separate instance here

    @commands.command(name='play', help='Plays a song from YouTube or adds it to the queue. Usage: zix play <song name or URL>')
    async def play(self, ctx, *, search_query: str):
        # Get the MusicPlayer instance
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if not ctx.voice_client:
            # If not in a voice channel, try to join the requester's channel
            if not ctx.message.author.voice:
                return await ctx.send(f"{ctx.message.author.name}, you are not connected to a voice channel. Use `zix join` first or join a channel.")

            # Manually connect here as !join is a separate cog
            channel = ctx.message.author.voice.channel
            player.voice_client = await channel.connect()
            await ctx.send(f"Joined voice channel: {channel.name}")

            # Start the audio player task if it's not already running or has finished
            if not player.music_task or player.music_task.done():
                player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))


        await ctx.send(f"Searching for '{search_query}'...")

        try:
            # Use the yt_dlp instance from the MusicPlayer cog
            func = functools.partial(player.yt_dlp.extract_info, search_query, download=False)
            info = await self.bot.loop.run_in_executor(None, func)

            if 'entries' in info:
                info = info['entries'][0]

            audio_url = info['url']
            title = info.get('title', 'Unknown Title')
            original_url = info.get('webpage_url', 'N/A')

            song = Song(audio_url, title, original_url, ctx.author)
            player.queue.append(song)

            await ctx.send(f"Added to queue: {song.title} (Requested by {ctx.author.mention})")

            # If the bot is not currently playing, trigger the player task
            if not player.is_playing and player.music_task and not player.music_task.done():
                if hasattr(player, 'next_song_event') and not player.next_song_event.is_set():
                    player.next_song_event.set() # Signal to play next

        except yt_dlp.utils.DownloadError as e:
            await ctx.send(f"Could not find or play that song. Error: {e}")
            print(f"yt-dlp error: {e}")
        except Exception as e:
            await ctx.send(f"An unexpected error occurred: {e}")
            print(f"General play error: {e}")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Play(bot))
