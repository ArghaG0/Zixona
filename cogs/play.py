# cogs/play.py

import discord
from discord.ext import commands
import asyncio
import functools
import yt_dlp

# Import the core music player cog and Song class, and YTDL options
from .core_music_player import MusicPlayer, Song, YTDL_OPTIONS # YTDL_OPTIONS is imported but not used directly here

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help='Plays a song from YouTube or adds it to the queue. Usage: zix play <song name or URL>')
    async def play(self, ctx, *, search_query: str):
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            error_embed = discord.Embed(
                title="Error",
                description="Music player core not loaded. Please contact bot owner.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed)

        if not ctx.voice_client:
            if not ctx.message.author.voice:
                error_embed = discord.Embed(
                    title="Voice Channel Required",
                    description=f"{ctx.message.author.name}, you are not connected to a voice channel. Please join one first.",
                    color=discord.Color.orange()
                )
                return await ctx.send(embed=error_embed)

            channel = ctx.message.author.voice.channel
            player.voice_client = await channel.connect()
            join_embed = discord.Embed(
                title="✅ Joined Voice Channel",
                description=f"Joined voice channel: **{channel.name}**",
                color=discord.Color.from_rgb(112, 161, 255)
            )
            await ctx.send(embed=join_embed)

            if not player.music_task or player.music_task.done():
                player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))

        searching_embed = discord.Embed(
            description=f"Searching for `{search_query}`...",
            color=discord.Color.light_grey()
        )
        await ctx.send(embed=searching_embed)

        try:
            func = functools.partial(player.yt_dlp.extract_info, search_query, download=False)
            info = await self.bot.loop.run_in_executor(None, func)

            if 'entries' in info:
                info = info['entries'][0]

            audio_url = info['url']
            title = info.get('title', 'Unknown Title')
            original_url = info.get('webpage_url', 'N/A')

            song = Song(audio_url, title, original_url, ctx.author)
            player.queue.append(song)

            added_embed = discord.Embed(
                title="➕ Added to Queue",
                description=f"{song}", # Uses __str__ method of Song
                color=discord.Color.from_rgb(112, 161, 255)
            )
            added_embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else discord.Embed.Empty)
            await ctx.send(embed=added_embed)

            # If the bot is not currently playing, trigger the player task
            if not player.is_playing and player.music_task and not player.music_task.done():
                if hasattr(player, 'next_song_event') and not player.next_song_event.is_set():
                    player.next_song_event.set() # Signal to play next

        except yt_dlp.utils.DownloadError as e:
            error_embed = discord.Embed(
                title="Search Error",
                description=f"Could not find or process that song. Please try a different search term or URL.\nError: `{e}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            print(f"yt-dlp error: {e}")
        except Exception as e:
            error_embed = discord.Embed(
                title="An Unexpected Error Occurred",
                description=f"Please try again. If the issue persists, contact the bot owner.\nError: `{e}`",
                color=discord.Color.red()
            )
            await ctx.send(embed=error_embed)
            print(f"General play error: {e}")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Play(bot))
