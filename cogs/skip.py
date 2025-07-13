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
        # Get the MusicPlayer instance
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop() # This will stop current playback and trigger the `after` callback
            await ctx.send("Skipped current song. Playing next song in queue...")
        elif not player.queue:
            await ctx.send("No song is currently playing and the queue is empty.")
        else:
            await ctx.send("No song is currently playing. Use `zix play` to start.")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Skip(bot))
