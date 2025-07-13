# main.py

import discord
from discord.ext import commands
import os
from dotenv import load_dotenv # For loading environment variables from .env

# Load environment variables from .env file (for local development)
load_dotenv()

# --- Configuration ---
TOKEN = os.environ.get("BOT_TOKEN")
# NEW: Load FFMPEG_PATH from environment variables
FFMPEG_PATH = os.environ.get("FFMPEG_PATH")

if not TOKEN:
    print("Error: BOT_TOKEN environment variable not set. Please set it in your hosting environment.")
    exit(1)

if not FFMPEG_PATH:
    print("Warning: FFMPEG_PATH environment variable not set. FFmpeg may not be found. Please set it in your .env or hosting environment.")
    # We won't exit here, as it might still work if ffmpeg is in system PATH,
    # but it's better to explicitly set it.

# Define bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True # CRITICAL for music bot

# Initialize the bot
# Prefix is "zix " (with a space)
bot = commands.Bot(command_prefix='zix ', intents=intents)

# Store FFMPEG_PATH on the bot object so cogs can access it
bot.ffmpeg_path = FFMPEG_PATH

# --- Cog Loading Function ---
async def load_extensions():
    """Loads all cogs (extensions) from the 'cogs' directory."""
    # It's crucial to load core_music_player first as other music cogs depend on it
    try:
        await bot.load_extension("cogs.core_music_player")
        print("Loaded core cog: core_music_player")
    except Exception as e:
        print(f"Failed to load core cog core_music_player: {e}")
        # If core cog fails, other music cogs will likely fail too, so exit or handle carefully
        return

    # Load other cogs dynamically
    # We explicitly list them to control load order and ensure core is first
    cogs_to_load = [
        "general", # For !ping
        "join",
        "leave",
        "play",
        "skip",
        "stop",
        "queue"
    ]

    for cog_name in cogs_to_load:
        try:
            await bot.load_extension(f"cogs.{cog_name}")
            print(f"Loaded cog: {cog_name}")
        except Exception as e:
            print(f"Failed to load cog {cog_name}: {e}")

# --- Bot Events ---
@bot.event
async def on_ready():
    """Event that fires when the bot successfully connects to Discord."""
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot ID: {bot.user.id}')
    print(f'Prefix: "{bot.command_prefix}"') # Print with quotes to show the space
    print('Bot is ready and online!')

    # Load all cogs when the bot is ready
    await load_extensions()
    print('All cogs loaded!')

    # Sync slash commands (if you add them later)
    try:
        await bot.tree.sync()
        print("Slash commands synced globally!")
    except Exception as e:
        print(f"Failed to sync slash commands: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands."""
    if isinstance(error, commands.CommandNotFound):
        pass
    else:
        print(f"An unhandled error occurred: {error}")
        await ctx.send(f"An error occurred: {error}")

# --- Run the bot ---
if __name__ == "__main__":
    bot.run(TOKEN)
