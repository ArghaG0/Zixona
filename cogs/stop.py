# cogs/stop.py

import discord
from discord.ext import commands
import asyncio

# Import the core music player cog
from .core_music_player import MusicPlayer

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='stop', help='Stops the current song and clears the queue.')
    async def stop(self, ctx):
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            error_embed = discord.Embed(
                title="Error",
                description="Music player core not loaded. Please contact bot owner.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed)

        if ctx.voice_client:
            if player.music_task:
                player.music_task.cancel()
                player.music_task = None
            player.queue.clear()
            player.is_playing = False
            player.current_song = None
            ctx.voice_client.stop()
            embed = discord.Embed(
                title="🛑 Music Stopped",
                description="Music playback stopped and queue cleared.",
                color=discord.Color.from_rgb(255, 99, 71) # Tomato Red
            )
            await ctx.send(embed=embed)
            # Re-start the player task to handle future additions, but it will be idle
            player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))
        else:
            embed = discord.Embed(
                title="Not Playing",
                description="I'm not currently playing music or in a voice channel.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Stop(bot))
