# cogs/general.py

import discord
from discord.ext import commands

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping', help='Checks the bot\'s latency.')
    async def ping(self, ctx):
        """
        Responds with the bot's latency to Discord.
        """
        latency_ms = round(self.bot.latency * 1000)
        await ctx.send(f'Pong! {latency_ms}ms')

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(General(bot))
