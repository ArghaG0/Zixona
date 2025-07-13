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
        # Get the MusicPlayer instance
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if ctx.voice_client:
            if player.music_task:
                player.music_task.cancel() # Cancel the music playing task
                player.music_task = None
            player.queue.clear() # Clear the deque
            player.is_playing = False
            player.current_song = None
            ctx.voice_client.stop() # Stop current playback
            await ctx.voice_client.disconnect()
            player.voice_client = None # Reset voice client reference in player
            await ctx.send("Disconnected from voice channel and queue cleared.")
        else:
            await ctx.send("I'm not in a voice channel.")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Leave(bot))
