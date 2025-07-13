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
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            error_embed = discord.Embed(
                title="Error",
                description="Music player core not loaded. Please contact bot owner.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed)

        if not player.queue and not player.current_song:
            embed = discord.Embed(
                title="Empty Queue",
                description="The music queue is currently empty. Add songs using `zix play <song name>`!",
                color=discord.Color.light_grey()
            )
            return await ctx.send(embed=embed)

        queue_description = []
        if player.current_song:
            queue_description.append(f"**Now Playing:** {player.current_song} (Requested by {player.current_song.requester.display_name})")
            queue_description.append("\n**Upcoming:**")

        if player.queue:
            # Limit the display to a reasonable number of songs
            for i, song in enumerate(list(player.queue)[:10]): # Show first 10 upcoming songs
                queue_description.append(f"**{i+1}.** {song} (Requested by {song.requester.display_name})")
            if len(player.queue) > 10:
                queue_description.append(f"**...and {len(player.queue) - 10} more songs.**")
        else:
            if not player.current_song: # Should not happen if previous check passed
                queue_description.append("No songs in queue.")


        embed = discord.Embed(
            title="🎵 Music Queue",
            description="\n".join(queue_description),
            color=discord.Color.from_rgb(112, 161, 255)
        )
        embed.set_footer(text=f"Total songs in queue: {len(player.queue) + (1 if player.current_song else 0)}")
        await ctx.send(embed=embed)

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(ShowQueue(bot))
