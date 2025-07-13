# cogs/join.py

import discord
from discord.ext import commands
import asyncio

# Import the core music player cog
from .core_music_player import MusicPlayer # Note the relative import

class Join(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='join', help='Tells the bot to join the voice channel you are in.')
    async def join(self, ctx):
        # Get the MusicPlayer instance
        # It's important that 'MusicPlayer' cog is loaded before this one
        player = self.bot.get_cog('MusicPlayer')
        if not player:
            return await ctx.send("Music player core not loaded. Please contact bot owner.")

        if not ctx.message.author.voice:
            await ctx.send(f"{ctx.message.author.name}, you are not connected to a voice channel.")
            return

        channel = ctx.message.author.voice.channel

        if ctx.voice_client:
            if ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)
                player.voice_client = ctx.voice_client # Update voice client reference in player
                await ctx.send(f"Moved to voice channel: {channel.name}")
            else:
                await ctx.send(f"I am already in voice channel: {channel.name}")
        else:
            player.voice_client = await channel.connect()
            await ctx.send(f"Joined voice channel: {channel.name}")

        # Start the audio player task if it's not already running or has finished
        if not player.music_task or player.music_task.done():
            # Pass the ctx from the command to the player task for sending messages
            player.music_task = self.bot.loop.create_task(player.audio_player_task(ctx))

# --- Setup function for the cog ---
async def setup(bot):
    await bot.add_cog(Join(bot))
