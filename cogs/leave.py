# cogs/leave.py

import discord
from discord.ext import commands
import asyncio

# Import the core music player cog
from .core_music_player import MusicPlayer

class Leave(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='leave', help='Makes the bot leave the voice channel.')
    async def leave(self, ctx):
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
            await ctx.voice_client.disconnect()
            player.voice_client = None
            embed = discord.Embed(
                title="👋 Disconnected",
                description="Disconnected from voice channel and queue cleared.",
                color=discord.Color.from_rgb(112, 161, 255)
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Not Connected",
                description="I'm not in a voice channel.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Leave(bot))
