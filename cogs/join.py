# cogs/join.py

import discord
from discord.ext import commands
import asyncio

# Import the core music player cog
from .core_music_player import MusicPlayer

class Join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='join', help='Tells the bot to join the voice channel you are in.')
    async def join(self, ctx):
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            error_embed = discord.Embed(
                title="Error",
                description="Music player core not loaded. Please contact bot owner.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=error_embed)

        if not ctx.message.author.voice:
            error_embed = discord.Embed(
                title="Voice Channel Required",
                description=f"{ctx.message.author.name}, you are not connected to a voice channel.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=error_embed)

        channel = ctx.message.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)
                player.voice_client = ctx.voice_client
                embed = discord.Embed(
                    title="🔊 Moved Voice Channel",
                    description=f"Moved to voice channel: **{channel.name}**",
                    color=discord.Color.from_rgb(112, 161, 255)
                )
                await ctx.send(embed=embed)
            else:
                embed = discord.Embed(
                    title="Already Connected",
                    description=f"I am already in voice channel: **{channel.name}**",
                    color=discord.Color.light_grey()
                )
                await ctx.send(embed=embed)
        else:
            player.voice_client = await channel.connect()
            embed = discord.Embed(
                title="✅ Joined Voice Channel",
                description=f"Joined voice channel: **{channel.name}**",
                color=discord.Color.from_rgb(112, 161, 255)
            )
            await ctx.send(embed=embed)

        if not player.music_task or player.music_task.done():
            player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Join(bot))
