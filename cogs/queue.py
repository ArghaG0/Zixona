# cogs/queue.py

import discord
from discord.ext import commands

# Import the core music player cog
from .core_music_player import MusicPlayer

class ShowQueue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='queue', help='Shows the current song queue.')
    async def show_queue(self, ctx):
        # Get the MusicPlayer instance
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if not player.queue and not player.current_song:
            await ctx.send("The queue is empty. No songs are playing.")
            return

        queue_list = []
        if player.current_song:
            queue_list.append(f"Now Playing: {player.current_song.title} (Requested by {player.current_song.requester.display_name})")

        if player.queue:
            for i, song in enumerate(player.queue):
                queue_list.append(f"{i+1}. {song.title} (Requested by {song.requester.display_name})")

        if queue_list:
            response = "Current Music Queue:\n" + "\n".join(queue_list)
            if len(response) > 2000:
                await ctx.send("The queue is too long to display. Showing first few songs:\n" + "\n".join(queue_list[:10]) + "\n...")
            else:
                await ctx.send(response)
        else:
            await ctx.send("The queue is empty. No songs are playing.")

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(ShowQueue(bot))
