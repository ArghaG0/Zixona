# main.py

import discord
from discord.ext import commands
import os
import yt_dlp # For downloading/extracting audio from YouTube and other sites
import asyncio # For managing asynchronous tasks and the event loop

# --- Configuration ---
# Load the bot token from environment variables for security.
# You will set this in your hosting platform's (e.g., Replit's) Secrets/Environment Variables.
TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    print("Error: BOT_TOKEN environment variable not set. Please set it in your hosting environment.")
    exit(1) # Exit if no token is found, as the bot cannot run without it.

# Define bot intents. These are crucial for Discord.py v2.0+ to function correctly.
# Intents tell Discord which events your bot wants to receive.
intents = discord.Intents.default()
intents.message_content = True # Required to read message content (e.g., for commands like !play song name)
intents.members = True         # Recommended for member-related operations (e.g., checking who is in a voice channel)
intents.voice_states = True    # CRITICAL: Required to detect voice channel changes and manage voice connections

# Initialize the bot.
# We'll use a simple prefix '!' for commands.
bot = commands.Bot(command_prefix='!', intents=intents)

# --- yt-dlp options for audio extraction ---
# These options configure yt-dlp to extract only the best audio stream
# and save it in a format suitable for ffmpeg to play.
YTDL_OPTIONS = {
    'format': 'bestaudio/best', # Prioritize best audio quality
    'extractaudio': True,       # Ensure only audio is extracted
    'audioformat': 'mp3',       # Convert audio to mp3 format
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s', # Output file naming template
    'restrictfilenames': True,  # Keep filenames simple and safe
    'noplaylist': True,         # Do not download entire playlists by default
    'nocheckcertificate': True, # Ignore SSL certificate verification (can be useful but less secure)
    'ignoreerrors': False,      # Stop if an error occurs during extraction
    'logtostderr': False,       # Do not log yt-dlp output to standard error
    'quiet': True,              # Suppress most console output from yt-dlp
    'no_warnings': True,        # Suppress warnings from yt-dlp
    'default_search': 'auto',   # Automatically search for best match if URL is not direct
    'source_address': '0.0.0.0',# Bind to IPv4 (important for some network configurations)
    'postprocessors': [{        # Post-processing steps after download
        'key': 'FFmpegExtractAudio', # Use FFmpeg to extract and convert audio
        'preferredcodec': 'mp3',     # Preferred audio codec
        'preferredquality': '192',   # Preferred audio quality (kbps)
    }],
}

# --- FFmpeg options for playing audio ---
# These options are passed to ffmpeg when discord.py uses it to play audio.
FFMPEG_OPTIONS = {
    # 'before_options' are arguments passed to ffmpeg before the input file.
    # -reconnect 1: Enables reconnection for broken streams.
    # -reconnect_streamed 1: Enables reconnection for streamed data.
    # -reconnect_delay_max 5: Max delay in seconds between reconnect attempts.
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    # 'options' are arguments passed to ffmpeg after the input file.
    # -vn: Disables video recording (only process audio).
    'options': '-vn'
}

# --- Bot Events ---

@bot.event
async def on_ready():
    """Event that fires when the bot successfully connects to Discord."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Prefix: {bot.command_prefix}')
    print('Ready to play music!')
    # In a real bot, you might also sync slash commands here if you have them
    # try:
    #     await bot.tree.sync()
    #     print("Slash commands synced!")
    # except Exception as e:
    #     print(f"Failed to sync slash commands: {e}")


# --- Basic Music Commands ---

@bot.command(name='join', help='Tells the bot to join the voice channel you are in.')
async def join(ctx):
    """
    Connects the bot to the voice channel of the command invoker.
    """
    # Check if the user is in a voice channel
    if not ctx.message.author.voice:
        await ctx.send(f"{ctx.message.author.name}, you are not connected to a voice channel.")
        return

    # Get the voice channel the user is in
    channel = ctx.message.author.voice.channel

    # Check if the bot is already in a voice channel in this guild
    if ctx.voice_client:
        # If bot is in a different channel, move to the user's channel
        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
            await ctx.send(f"Moved to voice channel: {channel.name}")
        else:
            await ctx.send(f"I am already in voice channel: {channel.name}")
    else:
        # Connect to the voice channel
        await channel.connect()
        await ctx.send(f"Joined voice channel: {channel.name}")

@bot.command(name='leave', help='Makes the bot leave the voice channel.')
async def leave(ctx):
    """
    Disconnects the bot from the current voice channel.
    """
    # Check if the bot is in a voice channel
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from voice channel.")
    else:
        await ctx.send("I'm not in a voice channel.")

# --- Run the bot ---
if __name__ == "__main__":
    # The bot will attempt to get the TOKEN from os.environ.get("BOT_TOKEN").
    # For local testing, ensure your BOT_TOKEN is set in your environment
    # (e.g., via a .env file and python-dotenv, or directly in your terminal).
    # For deployment, set it in your hosting platform's environment variables.
    bot.run(TOKEN)

