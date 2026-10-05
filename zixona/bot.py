import discord
from discord.ext import commands
from zixona.config import load_settings
from zixona.presentation import EMBED_COLOR, EMOJI_ERROR

# Define intents for your bot.
# MESSAGE_CONTENT is required to read messages for commands.
# VOICE_STATES is required for voice channel operations.
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Initialize the bot with a command prefix and intents.
bot = commands.Bot(command_prefix='zix ', intents=intents, help_command=None)

@bot.event
async def on_ready():
    """
    Called when the bot successfully connects to Discord.
    Loads the music cog.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    try:
        # Load the packaged music extension
        await bot.load_extension('zixona.cogs.music')
        print("MusicCog loaded successfully.")
    except commands.ExtensionAlreadyLoaded:
        print("MusicCog was already loaded (this might happen during hot-reloads).")
    except commands.ExtensionFailed as e:
        print(f"Failed to load MusicCog: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while loading MusicCog: {e}")

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for bot commands.
    This handles errors that occur across all commands, regardless of cog.
    """
    if isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Command Not Found",
            description=f"Sorry, that command doesn't exist. Use `{bot.command_prefix}help` to see available commands.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Missing Argument",
            description=f"Missing arguments. Please provide all required information. Usage: `{bot.command_prefix}{ctx.command.name} {ctx.command.usage or ''}`",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.NoPrivateMessage):
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Private Message Not Allowed",
            description="This command cannot be used in private messages.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Bad Argument",
            description="Invalid argument provided. Please check your input.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandInvokeError):
        original = error.original
        if isinstance(original, discord.Forbidden):
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Permission Denied",
                description="I don't have permission to do that in this channel.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Internal Error",
                description=f"An internal error occurred: `{original}`",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            print(f"CommandInvokeError: {original}")
    else:
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Unexpected Error",
            description=f"An unexpected error occurred: `{error}`",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        print(f"Unhandled error: {error}")

# --- Run the Bot ---
def main():
    DISCORD_BOT_TOKEN = load_settings()
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set.")
        print("Please create a .env file in the project root with the following content:")
        print("DISCORD_BOT_TOKEN=\"YOUR_BOT_TOKEN_HERE\"")
        print("FFMPEG_PATH=\"C:/path/to/ffmpeg/bin/ffmpeg.exe\" (or your actual ffmpeg executable path)")
        print("Replace YOUR_BOT_TOKEN_HERE with your actual bot token.")
    else:
        try:
            bot.run(DISCORD_BOT_TOKEN)
        except discord.LoginFailure:
            print("Error: Invalid Discord bot token. Please check your DISCORD_BOT_TOKEN in the .env file.")
        except Exception as e:
            print(f"An unexpected error occurred during bot startup: {e}")

