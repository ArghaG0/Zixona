# cogs/skip.py

import discord
from discord.ext import commands

# Import the core music player cog
from .core_music_player import MusicPlayer

class Skip(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='skip', help='Skips the current song.')
    async def skip(self, ctx):
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            error_embed = discord.Embed(
                title="Error",
                description="Music player core not loaded. Please contact bot owner.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed)

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop() # This will stop current playback and trigger the `after` callback
            embed = discord.Embed(
                title="⏩ Song Skipped",
                description="Skipped current song. Playing next song in queue...",
                color=discord.Color.from_rgb(112, 161, 255)
            )
            await ctx.send(embed=embed)
        elif not player.queue:
            embed = discord.Embed(
                title="No Song to Skip",
                description="No song is currently playing and the queue is empty.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="No Song Playing",
                description="No song is currently playing. Use `zix play` to start.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Skip(bot))
