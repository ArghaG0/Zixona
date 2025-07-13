import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import dotenv # Import the dotenv library

# --- Configuration ---
# Load environment variables from a .env file
dotenv.load_dotenv()

# Get your bot token from Discord Developer Portal.
# It's highly recommended to use environment variables for sensitive information.
# For example, create a .env file and use a library like `dotenv` to load it.
# Make sure to set the DISCORD_BOT_TOKEN environment variable in your .env file.
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Ensure ffmpeg is in your system's PATH or specify its path here.
# It's recommended to set this in your .env file as FFMPEG_PATH="C:/path/to/ffmpeg/bin"
FFMPEG_PATH = os.getenv('FFMPEG_PATH') # Now loading FFMPEG_PATH from .env

# --- Bot Setup ---
# Define intents for your bot.
# MESSAGE_CONTENT is required to read messages for commands.
# VOICE_STATES is required for voice channel operations.
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Initialize the bot with a command prefix and intents.
# The prefix is what you type before your command (e.g., !play).
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Audio Player Class ---
# This class will manage the music queue and playback.
class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue() # The queue for songs
        self.current_song = None
        self.voice_client = None
        self.is_playing = False
        self.skip_votes = {} # To handle skip votes in multi-user scenarios
        self.skip_required = 0 # Number of votes required to skip

        # YTDL options for downloading audio
        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0' # For IPv4 addresses
        }

        # FFmpeg options for playing audio
        self.FFMPEG_OPTIONS = {
            'options': '-vn' # No video
        }
        if FFMPEG_PATH:
            # Ensure the executable path is correctly set if FFMPEG_PATH is provided
            # It should point directly to the ffmpeg executable, not just the directory.
            # We assume the user provides the full path to the executable in the .env file.
            self.FFMPEG_OPTIONS['executable'] = FFMPEG_PATH

        self.yt_dlp = youtube_dl.YoutubeDL(self.YTDL_OPTIONS)
        self.audio_player_task = bot.loop.create_task(self.audio_player_loop())

    async def audio_player_loop(self):
        """
        Main loop for playing songs from the queue.
        """
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            self.is_playing = False
            self.current_song = None

            try:
                # Wait for the next song in the queue
                song = await self.queue.get()
            except asyncio.CancelledError:
                # Task was cancelled, exit loop
                return
            except Exception as e:
                print(f"Error getting song from queue: {e}")
                continue

            self.is_playing = True
            self.current_song = song
            self.skip_votes = {} # Reset skip votes for the new song

            if self.voice_client and self.voice_client.is_connected():
                try:
                    # Create FFmpeg audio source
                    source = discord.FFmpegPCMAudio(song['url'], **self.FFMPEG_OPTIONS)
                    self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next_song, e))
                    print(f"Now playing: {song['title']}")
                    # Optional: Send a message to the channel where the command was issued
                    # await song['channel'].send(f"Now playing: **{song['title']}**")
                except Exception as e:
                    print(f"Error playing song: {e}")
                    # If an error occurs, try to play the next song
                    self.play_next_song(e)
            else:
                print("Voice client not connected, skipping song.")
                self.play_next_song(None) # Move to the next song if not connected

    def play_next_song(self, error):
        """
        Callback function called after a song finishes or an error occurs.
        """
        if error:
            print(f"Player error: {error}")
        self.bot.loop.call_soon_threadsafe(self.queue.task_done) # Mark task as done
        # The audio_player_loop will automatically fetch the next song from the queue.

    async def add_to_queue(self, ctx, url):
        """
        Adds a song to the queue.
        """
        await ctx.send(f"Searching for `{url}`...")
        try:
            # Use run_in_executor to prevent blocking the event loop
            data = await self.bot.loop.run_in_executor(None, lambda: self.yt_dlp.extract_info(url, download=False))

            if 'entries' in data:
                # If it's a playlist or search result with multiple entries, take the first one
                song = data['entries'][0]
            else:
                song = data

            song_info = {
                'title': song.get('title', 'Unknown Title'),
                'url': song.get('url'), # This is the direct audio URL from yt-dlp
                'webpage_url': song.get('webpage_url'), # The original YouTube URL
                'channel': ctx.channel, # Store the channel to send messages
                'requester': ctx.author # Store the requester
            }

            if not song_info['url']:
                await ctx.send(f"Could not find audio for `{url}`.")
                return

            await self.queue.put(song_info)
            await ctx.send(f"Added **{song_info['title']}** to the queue.")

        except youtube_dl.DownloadError as e:
            await ctx.send(f"Could not download/extract info for `{url}`: {e}")
        except Exception as e:
            await ctx.send(f"An error occurred while processing your request: {e}")
            print(f"Error in add_to_queue: {e}")

    async def connect_to_voice(self, channel):
        """
        Connects the bot to a voice channel.
        """
        if self.voice_client:
            if self.voice_client.channel != channel:
                await self.voice_client.move_to(channel)
                return True
            return False # Already in the channel
        else:
            self.voice_client = await channel.connect()
            return True

    async def disconnect_from_voice(self):
        """
        Disconnects the bot from the voice channel.
        """
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
            self.is_playing = False
            # Clear the queue
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.current_song = None
            return True
        return False

# --- Bot Events ---
@bot.event
async def on_ready():
    """
    Called when the bot successfully connects to Discord.
    """
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')
    # Initialize the music player when the bot is ready
    bot.music_player = MusicPlayer(bot)

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for bot commands.
    """
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Sorry, that command doesn't exist. Use `!help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing arguments. Please provide all required information. Usage: `{ctx.command.usage}`")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("This command cannot be used in private messages.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Invalid argument provided. Please check your input.")
    elif isinstance(error, commands.CommandInvokeError):
        # This catches errors that happen inside the command's code
        original = error.original
        if isinstance(original, discord.Forbidden):
            await ctx.send("I don't have permission to do that in this channel.")
        else:
            await ctx.send(f"An internal error occurred: {original}")
            print(f"CommandInvokeError: {original}")
    else:
        await ctx.send(f"An unexpected error occurred: {error}")
        print(f"Unhandled error: {e}")

# --- Bot Commands ---

@bot.command(name='join', help='Makes the bot join your current voice channel.')
async def join(ctx):
    """
    Connects the bot to the voice channel of the command invoker.
    """
    if not ctx.author.voice:
        return await ctx.send("You are not in a voice channel.")

    channel = ctx.author.voice.channel
    if await bot.music_player.connect_to_voice(channel):
        await ctx.send(f"Joined voice channel: **{channel.name}**")
    else:
        await ctx.send(f"I am already in voice channel: **{channel.name}**")

@bot.command(name='leave', help='Makes the bot leave the voice channel.')
async def leave(ctx):
    """
    Disconnects the bot from the voice channel.
    """
    if await bot.music_player.disconnect_from_voice():
        await ctx.send("Disconnected from voice channel.")
    else:
        await ctx.send("I am not currently in a voice channel.")

@bot.command(name='play', help='Plays a song from YouTube. Usage: !play <URL or search term>')
async def play(ctx, *, url):
    """
    Plays a song. If a song is already playing, it adds it to the queue.
    Supports YouTube URLs or search terms.
    """
    if not ctx.author.voice:
        return await ctx.send("You need to be in a voice channel to play music.")

    # Ensure bot is in the same voice channel as the user
    if bot.music_player.voice_client is None or bot.music_player.voice_client.channel != ctx.author.voice.channel:
        await join(ctx) # Automatically join if not in channel or wrong channel

    if not bot.music_player.voice_client:
        return await ctx.send("I could not connect to a voice channel. Please try again.")

    await bot.music_player.add_to_queue(ctx, url)

@bot.command(name='skip', help='Skips the current song.')
async def skip(ctx):
    """
    Skips the current song.
    """
    if not bot.music_player.is_playing:
        return await ctx.send("No song is currently playing.")

    if not bot.music_player.voice_client:
        return await ctx.send("I am not in a voice channel.")

    # Implement a simple voting system for skipping if multiple users are present
    members_in_vc = [m for m in bot.music_player.voice_client.channel.members if not m.bot]
    if len(members_in_vc) > 1: # If more than one human user
        if ctx.author.id not in bot.music_player.skip_votes:
            bot.music_player.skip_votes[ctx.author.id] = True
            bot.music_player.skip_required = len(members_in_vc) // 2 + 1 # Majority vote
            current_votes = len(bot.music_player.skip_votes)
            await ctx.send(f"Skip vote added by {ctx.author.display_name}. {current_votes}/{bot.music_player.skip_required} votes to skip.")
            if current_votes >= bot.music_player.skip_required:
                bot.music_player.voice_client.stop()
                await ctx.send("Song skipped!")
        else:
            await ctx.send("You have already voted to skip this song.")
    else: # Only one user or bot is present, no vote needed
        bot.music_player.voice_client.stop()
        await ctx.send("Song skipped!")

@bot.command(name='stop', help='Stops the current song and clears the queue.')
async def stop(ctx):
    """
    Stops the current song and clears the entire queue.
    """
    if not bot.music_player.voice_client:
        return await ctx.send("I am not currently playing anything.")

    if bot.music_player.voice_client.is_playing():
        bot.music_player.voice_client.stop()
        await ctx.send("Playback stopped.")

    # Clear the queue
    while not bot.music_player.queue.empty():
        try:
            bot.music_player.queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    bot.music_player.current_song = None
    await ctx.send("Queue cleared.")

@bot.command(name='queue', help='Shows the current music queue.')
async def show_queue(ctx):
    """
    Displays the current songs in the queue.
    """
    if bot.music_player.queue.empty() and not bot.music_player.current_song:
        return await ctx.send("The queue is empty.")

    queue_list = []
    if bot.music_player.current_song:
        queue_list.append(f"**Now Playing:** {bot.music_player.current_song['title']} (Requested by {bot.music_player.current_song['requester'].display_name})")

    # Get items from the queue without removing them
    # This is a bit tricky with asyncio.Queue. A simple way is to iterate over its internal list if accessible,
    # or create a temporary list. For simplicity, we'll just show what's currently in the queue.
    # For a more robust solution, you might want to manage the queue as a simple list in MusicPlayer.
    temp_queue_list = []
    # Peek at the queue items (this is not a standard Queue method, so we'll simulate)
    # A better approach for showing queue would be to store songs in a list and manage that list
    # For now, we'll just show the next few items if available.
    if not bot.music_player.queue.empty():
        # This is a workaround to peek into the queue. Not ideal for large queues.
        # For a proper queue display, consider implementing your own queue with a list.
        # For demonstration, we'll just show the current song and mention if there are more.
        queue_size = bot.music_player.queue.qsize()
        if queue_size > 0:
            queue_list.append(f"**Next up ({queue_size} songs):**")
            # This part is complex with asyncio.Queue. A simple list for queue management is better for display.
            # For now, we'll just state the number of songs.
            # Example of how you *would* show items if queue was a list:
            # for i, song in enumerate(self.queue_list[1:]): # Assuming 0 is current song
            #    queue_list.append(f"{i+1}. {song['title']}")
            pass # We'll just show the count for now.

    if len(queue_list) > 0:
        embed = discord.Embed(title="Music Queue", description="\n".join(queue_list), color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        await ctx.send("The queue is empty.")


# --- Run the Bot ---
if __name__ == '__main__':
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set.")
        print("Please create a .env file in the same directory as your bot script with the following content:")
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

