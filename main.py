import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import dotenv # Import the dotenv library
import collections # Import collections for deque

# --- Configuration ---
# Load environment variables from a .env file
dotenv.load_dotenv()

# Get your bot token from Discord Developer Portal.
# It's highly recommended to use environment variables for sensitive information.
# For example, create a .env file and use a library like `dotenv` to load it.
# Make sure to set the DISCORD_BOT_TOKEN environment variable in your .env file.
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Ensure ffmpeg is in your system's PATH or specify its path here.
# It's recommended to set this in your .env file as FFMPEG_PATH="C:/path/to/ffmpeg/bin/ffmpeg.exe"
FFMPEG_PATH = os.getenv('FFMPEG_PATH') # Now loading FFMPEG_PATH from .env

# Custom embed color (FFB6C1 - Light Pink)
EMBED_COLOR = discord.Color(0xFFB6C1)

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
        # self.queue is used by the audio_player_loop to fetch the next song
        self.queue = asyncio.Queue()
        # self.song_queue_list is used to store song info for display in the !queue command
        self.song_queue_list = collections.deque() 
        self.current_song = None
        self.voice_client = None
        self.is_playing = False # Flag to indicate if a song is actively playing
        self.skip_votes = {} # To handle skip votes in multi-user scenarios
        self.skip_required = 0 # Number of votes required to skip

        # YTDL options for downloading audio
        # We'll use 'url' for the direct stream and 'webpage_url' for re-fetching.
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
            # Normalize path to handle different OS path separators
            normalized_ffmpeg_path = os.path.normpath(FFMPEG_PATH)

            # Check if the provided path is a directory
            if os.path.isdir(normalized_ffmpeg_path):
                # If it's a directory, assume ffmpeg.exe (for Windows) or ffmpeg (for Linux/macOS) is inside it
                # For robustness, we'll try to append the executable name
                ffmpeg_executable_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg' # Check OS for executable name
                ffmpeg_executable_path = os.path.join(normalized_ffmpeg_path, ffmpeg_executable_name)
                
                if not os.path.exists(ffmpeg_executable_path):
                    print(f"Warning: FFmpeg executable '{ffmpeg_executable_name}' not found in '{normalized_ffmpeg_path}'.")
                    print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
                    self.FFMPEG_OPTIONS['executable'] = None # Disable ffmpeg if not found
                else:
                    self.FFMPEG_OPTIONS['executable'] = ffmpeg_executable_path
                    print(f"FFmpeg executable path adjusted to: {self.FFMPEG_OPTIONS['executable']}")
            else:
                # If it's not a directory, assume it's already the full path to the executable
                self.FFMPEG_OPTIONS['executable'] = normalized_ffmpeg_path
            
            # Final check to ensure the executable exists at the determined path
            if self.FFMPEG_OPTIONS.get('executable') and not os.path.exists(self.FFMPEG_OPTIONS['executable']):
                print(f"Warning: FFmpeg executable not found at '{self.FFMPEG_OPTIONS['executable']}'.")
                print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
                self.FFMPEG_OPTIONS['executable'] = None # Disable ffmpeg if not found
        else:
            print("FFMPEG_PATH not set in .env. Assuming ffmpeg is in system PATH.")
            # If FFMPEG_PATH is not set, discord.py will look for 'ffmpeg' in system PATH.
            # No need to set 'executable' explicitly if it's expected to be in PATH.


        self.yt_dlp = youtube_dl.YoutubeDL(self.YTDL_OPTIONS)
        self.audio_player_task = bot.loop.create_task(self.audio_player_loop())

    async def audio_player_loop(self):
        """
        Main loop for playing songs from the queue.
        This loop continuously fetches songs from `self.queue` and plays them.
        It handles transitions between songs.
        """
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            # --- CRITICAL FIX: Wait for current song to finish before getting next from queue ---
            # This ensures that new songs added via !play do NOT interrupt the current one.
            # The loop will only proceed to fetch a new song when `self.is_playing` is False.
            while self.is_playing:
                await asyncio.sleep(1) # Wait for 1 second intervals if a song is playing
            # --- END CRITICAL FIX ---

            self.current_song = None # Clear current song before fetching new one
            self.is_playing = False # Ensure this is False before attempting to get a new song

            try:
                # This will block until a song is available in the queue
                song = await self.queue.get()
                # --- FIX: Remove song from display queue as it starts playing ---
                # This ensures the display queue only shows truly upcoming songs.
                # Only pop if the deque is not empty and the song matches (safety check for edge cases)
                if self.song_queue_list and self.song_queue_list[0]['webpage_url'] == song['webpage_url']:
                    self.song_queue_list.popleft()
                # --- END FIX ---
            except asyncio.CancelledError:
                # Task was cancelled, exit loop
                return
            except Exception as e:
                print(f"Error getting song from queue: {e}")
                continue

            self.current_song = song
            self.skip_votes = {} # Reset skip votes for the new song

            if self.voice_client and self.voice_client.is_connected():
                try:
                    # Ensure FFmpeg executable is set before playing
                    if self.FFMPEG_OPTIONS.get('executable') is None and FFMPEG_PATH is not None:
                        print("FFmpeg executable path is invalid. Cannot play audio.")
                        embed = discord.Embed(
                            title="Error",
                            description="FFmpeg executable not found. Please check your FFMPEG_PATH in the .env file.",
                            color=EMBED_COLOR
                        )
                        await self.current_song['channel'].send(embed=embed)
                        self.play_next_song(None) # Move to next song if ffmpeg is not found
                        continue
                    
                    # --- Robustly stop current playback for a clean transition ---
                    # This is crucial to prevent "Already playing audio" errors when discord.py
                    # attempts to play a new source while the previous one is still being managed internally.
                    # This only happens when the loop is *ready* to play a new song, not when a user requests one.
                    if self.voice_client.is_playing() or self.voice_client.is_paused():
                        self.voice_client.stop()
                        # Wait until the voice client confirms it's no longer playing
                        # This is more robust than a fixed sleep
                        while self.voice_client.is_playing() or self.voice_client.is_paused():
                            await asyncio.sleep(0.1) # Small sleep to avoid busy-waiting
                        # Add a small, fixed delay after the loop to ensure state fully clears
                        await asyncio.sleep(0.2) # Increased from 0.1 for more robustness
                    # --- END Robust Stop ---

                    # Re-extract the direct stream URL for fresh playback
                    # This is crucial to prevent URL expiration issues, especially for songs that have been in queue for a while.
                    await self.current_song['channel'].send(embed=discord.Embed(
                        title="Fetching Song...",
                        description=f"Getting ready to play **[{song['title']}]({song['webpage_url']})**...",
                        color=EMBED_COLOR
                    ))
                    
                    fresh_data = await self.bot.loop.run_in_executor(
                        None, lambda: self.yt_dlp.extract_info(song['webpage_url'], download=False)
                    )
                    fresh_audio_url = fresh_data.get('url')

                    if not fresh_audio_url:
                        raise ValueError(f"Could not get fresh audio URL for {song['title']}")

                    source = discord.FFmpegPCMAudio(fresh_audio_url, **self.FFMPEG_OPTIONS)
                    self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next_song, e))
                    self.is_playing = True # Set flag to True when playback starts
                    print(f"Now playing: {song['title']}")
                    
                    embed = discord.Embed(
                        title="Now Playing 🎶",
                        description=f"**[{song['title']}]({song['webpage_url']})** (Requested by {song['requester'].mention})",
                        color=EMBED_COLOR
                    )
                    await song['channel'].send(embed=embed)
                except Exception as e:
                    print(f"Error playing song: {e}")
                    embed = discord.Embed(
                        title="Playback Error",
                        description=f"Error playing **{song['title']}**: `{e}`. Skipping to next song.",
                        color=EMBED_COLOR
                    )
                    await self.current_song['channel'].send(embed=embed)
                    # If an error occurs, try to play the next song
                    self.play_next_song(e)
            else:
                print("Voice client not connected, skipping song.")
                self.play_next_song(None) # Move to the next song if not connected

    def play_next_song(self, error):
        """
        Callback function called after a song finishes or an error occurs.
        This function is called by discord.py when the current audio source finishes.
        """
        if error:
            print(f"Player error in play_next_song: {error}")
        self.is_playing = False # Set flag to False when song finishes
        print(f"Song finished or errored, is_playing set to False.")
        self.bot.loop.call_soon_threadsafe(self.queue.task_done) # Mark task as done in asyncio.Queue
        # The audio_player_loop will automatically fetch the next song from self.queue.

    async def add_to_queue(self, ctx, url):
        """
        Adds a song to the queue.
        This function always adds the song to the queue and does NOT interrupt current playback.
        """
        try:
            # Use run_in_executor to prevent blocking the event loop
            # We only need webpage_url and title at this stage.
            initial_data = await self.bot.loop.run_in_executor(None, lambda: self.yt_dlp.extract_info(url, download=False))

            if 'entries' in initial_data:
                song_meta = initial_data['entries'][0]
            else:
                song_meta = initial_data

            song_info = {
                'title': song_meta.get('title', 'Unknown Title'),
                'webpage_url': song_meta.get('webpage_url'), # Store the original URL for re-fetching
                'channel': ctx.channel, # Store the channel to send messages
                'requester': ctx.author # Store the requester
            }

            if not song_info['webpage_url']:
                embed = discord.Embed(
                    title="Error",
                    description=f"Could not find a valid URL for `{url}`.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
                return

            # --- FIX: Refined feedback logic ---
            # Check if a song is currently playing OR if there are already songs waiting in the queue.
            # This ensures "Added to Queue!" is sent if something is already playing or queued.
            # The `is_playing` flag is crucial here.
            is_currently_playing_or_has_queue = self.is_playing or not self.queue.empty()
            # --- END FIX ---

            # Add to both the internal queue for playback and the list for display
            await self.queue.put(song_info) # Add to asyncio.Queue for playback loop
            self.song_queue_list.append(song_info) # Add to deque for display

            if is_currently_playing_or_has_queue:
                embed = discord.Embed(
                    title="Added to Queue!",
                    description=f"**[{song_info['title']}]({song_info['webpage_url']})** has been added to the queue.",
                    color=EMBED_COLOR
                )
            else:
                # This branch is only taken if the bot was completely idle (no song playing, no songs in queue)
                embed = discord.Embed(
                    title="Starting Playback!",
                    description=f"**[{song_info['title']}]({song_info['webpage_url']})** will start playing shortly.",
                    color=EMBED_COLOR
                )
            await ctx.send(embed=embed)

        except youtube_dl.DownloadError as e:
            embed = discord.Embed(
                title="Download Error",
                description=f"Could not download/extract info for `{url}`: `{e}`",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title="Error",
                description=f"An error occurred while processing your request: `{e}`",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
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
            # Clear both queues
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.song_queue_list.clear() # Clear the display queue
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
        embed = discord.Embed(
            title="Command Not Found",
            description="Sorry, that command doesn't exist. Use `!help` to see available commands.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="Missing Argument",
            description=f"Missing arguments. Please provide all required information. Usage: `{ctx.command.usage}`",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.NoPrivateMessage):
        embed = discord.Embed(
            title="Private Message Not Allowed",
            description="This command cannot be used in private messages.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="Bad Argument",
            description="Invalid argument provided. Please check your input.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    elif isinstance(error, commands.CommandInvokeError):
        # This catches errors that happen inside the command's code
        original = error.original
        if isinstance(original, discord.Forbidden):
            embed = discord.Embed(
                title="Permission Denied",
                description="I don't have permission to do that in this channel.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Internal Error",
                description=f"An internal error occurred: `{original}`",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            print(f"CommandInvokeError: {original}")
    else:
        embed = discord.Embed(
            title="Unexpected Error",
            description=f"An unexpected error occurred: `{error}`",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
        print(f"Unhandled error: {error}")

# --- Bot Commands ---

@bot.command(name='join', help='Makes the bot join your current voice channel.')
async def join(ctx):
    """
    Connects the bot to the voice channel of the command invoker.
    """
    if not ctx.author.voice:
        embed = discord.Embed(
            title="Voice Channel Required",
            description="You are not in a voice channel.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    channel = ctx.author.voice.channel
    if await bot.music_player.connect_to_voice(channel):
        embed = discord.Embed(
            title="Joined Voice Channel",
            description=f"Joined voice channel: **{channel.name}**",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Already Connected",
            description=f"I am already in voice channel: **{channel.name}**",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

@bot.command(name='leave', help='Makes the bot leave the voice channel.')
async def leave(ctx):
    """
    Disconnects the bot from the voice channel.
    """
    if await bot.music_player.disconnect_from_voice():
        embed = discord.Embed(
            title="Disconnected",
            description="Disconnected from voice channel.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="Not Connected",
            description="I am not currently in a voice channel.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

@bot.command(name='play', help='Plays a song from YouTube. Usage: !play <URL or search term>')
async def play(ctx, *, url):
    """
    Plays a song. If a song is already playing, it adds it to the queue.
    Supports YouTube URLs or search terms.
    """
    if not ctx.author.voice:
        embed = discord.Embed(
            title="Voice Channel Required",
            description="You need to be in a voice channel to play music.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    # Ensure bot is in the same voice channel as the user
    if bot.music_player.voice_client is None or bot.music_player.voice_client.channel != ctx.author.voice.channel:
        await join(ctx) # Automatically join if not in channel or wrong channel

    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title="Connection Error",
            description="I could not connect to a voice channel. Please try again.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    await bot.music_player.add_to_queue(ctx, url)

@bot.command(name='skip', help='Skips the current song.')
async def skip(ctx):
    """
    Skips the current song.
    """
    if not bot.music_player.is_playing and bot.music_player.queue.empty(): # Check both playing status and queue
        embed = discord.Embed(
            title="No Song Playing",
            description="No song is currently playing or in the queue to skip.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title="Not Connected",
            description="I am not in a voice channel.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    # Implement a simple voting system for skipping if multiple users are present
    members_in_vc = [m for m in bot.music_player.voice_client.channel.members if not m.bot]
    if len(members_in_vc) > 1: # If more than one human user
        if ctx.author.id not in bot.music_player.skip_votes:
            bot.music_player.skip_votes[ctx.author.id] = True
            bot.music_player.skip_required = len(members_in_vc) // 2 + 1 # Majority vote
            current_votes = len(bot.music_player.skip_votes)
            embed = discord.Embed(
                title="Skip Vote",
                description=f"Skip vote added by {ctx.author.display_name}. {current_votes}/{bot.music_player.skip_required} votes to skip.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            if current_votes >= bot.music_player.skip_required:
                bot.music_player.voice_client.stop() # This will trigger play_next_song
                embed = discord.Embed(
                    title="Song Skipped!",
                    description="The song has been skipped by popular vote.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Vote Already Cast",
                description="You have already voted to skip this song.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
    else: # Only one user or bot is present, no vote needed
        bot.music_player.voice_client.stop() # This will trigger play_next_song
        embed = discord.Embed(
            title="Song Skipped!",
            description="The song has been skipped.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

@bot.command(name='stop', help='Stops the current song and clears the queue.')
async def stop(ctx):
    """
    Stops the current song and clears the entire queue.
    """
    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title="Not Playing",
            description="I am not currently playing anything.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    if bot.music_player.voice_client.is_playing():
        bot.music_player.voice_client.stop()
        embed = discord.Embed(
            title="Playback Stopped",
            description="Playback stopped.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    # Clear both queues
    while not bot.music_player.queue.empty():
        try:
            bot.music_player.queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    bot.music_player.song_queue_list.clear() # Clear the display queue
    bot.music_player.current_song = None
    embed = discord.Embed(
        title="Queue Cleared",
        description="The music queue has been cleared.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)

@bot.command(name='queue', help='Shows the current music queue.')
async def show_queue(ctx):
    """
    Displays the current songs in the queue.
    """
    queue_display = []

    if bot.music_player.current_song:
        queue_display.append(f"**Now Playing:** [{bot.music_player.current_song['title']}]({bot.music_player.current_song['webpage_url']}) (Requested by {bot.music_player.current_song['requester'].mention})")

    if bot.music_player.song_queue_list:
        queue_display.append("\n**Up Next:**")
        for i, song in enumerate(bot.music_player.song_queue_list):
            # Limit the number of songs displayed to prevent overly long embeds
            if i >= 10: # Display up to 10 upcoming songs
                queue_display.append(f"...and {len(bot.music_player.song_queue_list) - i} more!")
                break
            queue_display.append(f"{i+1}. [{song['title']}]({song['webpage_url']}) (Requested by {song['requester'].mention})")
    
    if not queue_display: # If both current song and queue are empty
        embed = discord.Embed(
            title="Music Queue",
            description="The queue is empty.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    embed = discord.Embed(title="Music Queue", description="\n".join(queue_display), color=EMBED_COLOR)
    await ctx.send(embed=embed)


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
