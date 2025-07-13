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
        # Get the MusicPlayer instance
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if ctx.voice_client:
            if player.music_task:
                player.music_task.cancel()
                player.music_task = None
            player.queue.clear()
            player.is_playing = False
            player.current_song = None
            ctx.voice_client.stop()
            await ctx.send("Music stopped and queue cleared.")
            # Re-start the player task to handle future additions, but it will be idle
            # Pass the ctx from the command to the player task for sending messages
            player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))
        else:
            await ctx.send("I'm not in a voice channel.")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Stop(bot))

