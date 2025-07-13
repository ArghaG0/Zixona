import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import os
import dotenv # Import the dotenv library
import collections # Import collections for deque
import datetime # For formatting song duration

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

# --- Global Emoji Variables ---
EMOJI_PLAYING = "🎶"
EMOJI_PAUSED = "⏸️"
EMOJI_ADDED = "✅"
EMOJI_SKIPPED = "⏭️"
EMOJI_STOPPED = "⏹️"
EMOJI_JOINED = "🔊"
EMOJI_DISCONNECTED = "🔇"
EMOJI_ERROR = "❌"
EMOJI_FETCHING = "🔎"
EMOJI_QUEUE = "📜"
EMOJI_VOTE = "🗳️"
EMOJI_HELP = "❓" # New emoji for help command
EMOJI_PLAYLIST = "📋" # New emoji for playlists

# --- Helper Function for Duration Formatting ---
def format_duration(seconds):
    """Formats duration in seconds to HH:MM:SS or MM:SS."""
    if seconds is None:
        return "N/A"
    
    # Use timedelta for robust formatting
    td = datetime.timedelta(seconds=int(seconds))
    
    # Extract hours, minutes, seconds
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

# --- Bot Setup ---
# Define intents for your bot.
# MESSAGE_CONTENT is required to read messages for commands.
# VOICE_STATES is required for voice channel operations.
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Initialize the bot with a command prefix and intents.
bot = commands.Bot(command_prefix='zix ', intents=intents, help_command=None)

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
        self.is_playing = False # Flag to indicate if a song is actively playing (not paused)
        self.skip_votes = {} # To handle skip votes in multi-user scenarios
        self.skip_required = 0 # Number of votes required to skip

        # YTDL options for downloading audio
        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True, # Set to False when processing a playlist explicitly
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'source_address': '0.0.0.0' # For IPv4 addresses
        }

        # FFmpeg options for playing audio
        # --- FIX: Added reconnection options for FFmpeg ---
        self.FFMPEG_OPTIONS = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5' # Crucial for stream stability
        }
        # --- END FIX ---

        if FFMPEG_PATH:
            # Normalize path to handle different OS path separators
            normalized_ffmpeg_path = os.path.normpath(FFMPEG_PATH)

            # Check if the provided path is a directory
            if os.path.isdir(normalized_ffmpeg_path):
                # If it's a directory, assume ffmpeg.exe (for Windows) or ffmpeg (for Linux/macOS) is inside it
                ffmpeg_executable_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg' # Check OS for executable name
                ffmpeg_executable_path = os.path.join(normalized_ffmpeg_path, ffmpeg_executable_name)
                
                if not os.path.exists(ffmpeg_executable_path):
                    print(f"Warning: FFmpeg executable '{ffmpeg_executable_name}' not found in '{normalized_ffmpeg_path}'.")
                    print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
                    self.FFMPEG_OPTIONS['executable'] = None
                else:
                    self.FFMPEG_OPTIONS['executable'] = ffmpeg_executable_path
                    print(f"FFmpeg executable path adjusted to: {self.FFMPEG_OPTIONS['executable']}")
            else:
                self.FFMPEG_OPTIONS['executable'] = normalized_ffmpeg_path
            
            if self.FFMPEG_OPTIONS.get('executable') and not os.path.exists(self.FFMPEG_OPTIONS['executable']):
                print(f"Warning: FFmpeg executable not found at '{self.FFMPEG_OPTIONS['executable']}'.")
                print("Please ensure FFMPEG_PATH in your .env file points directly to ffmpeg.exe or its containing directory.")
                self.FFMPEG_OPTIONS['executable'] = None
        else:
            print("FFMPEG_PATH not set in .env. Assuming ffmpeg is in system PATH.")


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
            # Wait for current song to finish or be explicitly stopped/skipped
            while self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                await asyncio.sleep(1)

            self.current_song = None
            self.is_playing = False

            try:
                song = await self.queue.get()
                # Remove song from display queue as it starts playing
                if self.song_queue_list and self.song_queue_list[0]['webpage_url'] == song['webpage_url']:
                    self.song_queue_list.popleft()
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"Error getting song from queue: {e}")
                continue

            self.current_song = song
            self.skip_votes = {}

            if self.voice_client and self.voice_client.is_connected():
                try:
                    if self.FFMPEG_OPTIONS.get('executable') is None and FFMPEG_PATH is not None:
                        print("FFmpeg executable path is invalid. Cannot play audio.")
                        embed = discord.Embed(
                            title=f"{EMOJI_ERROR} Error",
                            description="FFmpeg executable not found. Please check your FFMPEG_PATH in the .env file.",
                            color=EMBED_COLOR
                        )
                        await self.current_song['channel'].send(embed=embed)
                        self.play_next_song(None)
                        continue
                    
                    if self.voice_client.is_playing() or self.voice_client.is_paused():
                        self.voice_client.stop()
                        while self.voice_client.is_playing() or self.voice_client.is_paused():
                            await asyncio.sleep(0.1)
                        await asyncio.sleep(0.2)

                    await self.current_song['channel'].send(embed=discord.Embed(
                        title=f"{EMOJI_FETCHING} Fetching Song...",
                        description=f"Getting ready to play **[{song['title']}]({song['webpage_url']})**...",
                        color=EMBED_COLOR
                    ))
                    
                    # Re-extract the direct stream URL for fresh playback
                    fresh_data = await self.bot.loop.run_in_executor(
                        None, lambda: self.yt_dlp.extract_info(song['webpage_url'], download=False)
                    )
                    fresh_audio_url = fresh_data.get('url')

                    if not fresh_audio_url:
                        raise ValueError(f"Could not get fresh audio URL for {song['title']}")

                    source = discord.FFmpegPCMAudio(fresh_audio_url, **self.FFMPEG_OPTIONS)
                    self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next_song, e))
                    self.is_playing = True
                    print(f"Now playing: {song['title']}")
                    
                    duration_str = format_duration(song.get('duration'))
                    embed = discord.Embed(
                        title=f"{EMOJI_PLAYING} Now Playing",
                        description=f"**[{song['title']}]({song['webpage_url']})**\nDuration: `{duration_str}` (Requested by {song['requester'].mention})",
                        color=EMBED_COLOR
                    )
                    await song['channel'].send(embed=embed)
                except Exception as e:
                    print(f"Error playing song: {e}")
                    embed = discord.Embed(
                        title=f"{EMOJI_ERROR} Playback Error",
                        description=f"Error playing **{song['title']}**: `{e}`. Skipping to next song.",
                        color=EMBED_COLOR
                    )
                    await self.current_song['channel'].send(embed=embed)
                    self.play_next_song(e)
            else:
                print("Voice client not connected, skipping song.")
                self.play_next_song(None)

    def play_next_song(self, error):
        """
        Callback function called after a song finishes or an error occurs.
        This function is called by discord.py when the current audio source finishes.
        """
        if error:
            print(f"Player error in play_next_song: {error}")
        self.is_playing = False
        print(f"Song finished or errored, is_playing set to False.")
        self.bot.loop.call_soon_threadsafe(self.queue.task_done)

    async def add_to_queue(self, ctx, url):
        """
        Adds a song or playlist to the queue.
        This function always adds the song(s) to the queue and does NOT interrupt current playback.
        """
        try:
            # Set noplaylist to False to allow playlist extraction
            ytdl_options_with_playlist = self.YTDL_OPTIONS.copy()
            ytdl_options_with_playlist['noplaylist'] = False

            # Create a new YoutubeDL instance for this specific call to allow playlist extraction
            yt_dlp_playlist_enabled = youtube_dl.YoutubeDL(ytdl_options_with_playlist)

            # Use run_in_executor to prevent blocking the event loop
            data = await self.bot.loop.run_in_executor(None, lambda: yt_dlp_playlist_enabled.extract_info(url, download=False))

            songs_to_add = []
            if 'entries' in data: # It's a playlist or search result with multiple entries
                playlist_title = data.get('title', 'Unknown Playlist')
                for entry in data['entries']:
                    if entry: # Ensure entry is not None (can happen with private/deleted videos in playlists)
                        songs_to_add.append({
                            'title': entry.get('title', 'Unknown Title'),
                            'webpage_url': entry.get('webpage_url'),
                            'duration': entry.get('duration'), # Store duration
                            'channel': ctx.channel,
                            'requester': ctx.author
                        })
                embed = discord.Embed(
                    title=f"{EMOJI_PLAYLIST} Playlist Added!",
                    description=f"Added **{len(songs_to_add)}** songs from playlist **[{playlist_title}]({url})** to the queue.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
            else: # Single song
                songs_to_add.append({
                    'title': data.get('title', 'Unknown Title'),
                    'webpage_url': data.get('webpage_url'),
                    'duration': data.get('duration'), # Store duration
                    'channel': ctx.channel,
                    'requester': ctx.author
                })
                # Determine if a song is currently being played/paused OR if there are already songs waiting in the queue.
                is_currently_active_or_has_queue = (self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused())) or not self.queue.empty()

                if is_currently_active_or_has_queue:
                    embed = discord.Embed(
                        title=f"{EMOJI_ADDED} Added to Queue!",
                        description=f"**[{songs_to_add[0]['title']}]({songs_to_add[0]['webpage_url']})** has been added to the queue.",
                        color=EMBED_COLOR
                    )
                else:
                    embed = discord.Embed(
                        title=f"{EMOJI_PLAYING} Starting Playback!",
                        description=f"**[{songs_to_add[0]['title']}]({songs_to_add[0]['webpage_url']})** will start playing shortly.",
                        color=EMBED_COLOR
                    )
                await ctx.send(embed=embed)

            # Add all collected songs to both queues
            for song_info in songs_to_add:
                if song_info['webpage_url']: # Ensure URL is valid before adding
                    await self.queue.put(song_info)
                    self.song_queue_list.append(song_info)
                else:
                    print(f"Skipping invalid song entry: {song_info.get('title', 'Unknown Title')}")

        except youtube_dl.DownloadError as e:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Download Error",
                description=f"Could not download/extract info for `{url}`: `{e}`. This might be a private video or unsupported link.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Error",
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
            return False
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
            self.song_queue_list.clear()
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
    bot.music_player = MusicPlayer(bot)

@bot.event
async def on_command_error(ctx, error):
    """
    Global error handler for bot commands.
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

# --- Bot Commands ---

@bot.command(name='play', help=f'Plays a song from YouTube (or other platforms). If a song is playing, it adds to queue. Usage: `{bot.command_prefix}play <URL or search term>`')
async def play(ctx, *, url):
    """
    Plays a song. If a song is already playing, it adds it to the queue.
    Supports YouTube URLs, playlists, or search terms. Automatically joins VC.
    """
    if not ctx.author.voice:
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Voice Channel Required",
            description="You are not in a voice channel. Please join one first.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    channel = ctx.author.voice.channel
    if bot.music_player.voice_client is None or bot.music_player.voice_client.channel != channel:
        try:
            await bot.music_player.connect_to_voice(channel)
            embed = discord.Embed(
                title=f"{EMOJI_JOINED} Joined Voice Channel",
                description=f"Joined voice channel: **{channel.name}**",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Connection Error",
                description=f"Could not connect to voice channel: `{e}`",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Connection Error",
            description="I could not connect to a voice channel. Please try again.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    await bot.music_player.add_to_queue(ctx, url)

@bot.command(name='pause', help=f'Pauses the current song. Usage: `{bot.command_prefix}pause`')
async def pause(ctx):
    """
    Pauses the currently playing song.
    """
    if not bot.music_player.voice_client or not bot.music_player.voice_client.is_playing():
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Nothing Playing",
            description="No song is currently playing to pause.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)
    
    if bot.music_player.voice_client.is_paused():
        embed = discord.Embed(
            title=f"{EMOJI_PAUSED} Already Paused",
            description="The song is already paused.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    bot.music_player.voice_client.pause()
    bot.music_player.is_playing = False # Update state
    embed = discord.Embed(
        title=f"{EMOJI_PAUSED} Playback Paused",
        description="The current song has been paused.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)

@bot.command(name='resume', help=f'Resumes the paused song. Usage: `{bot.command_prefix}resume`')
async def resume(ctx):
    """
    Resumes the currently paused song.
    """
    if not bot.music_player.voice_client or not bot.music_player.voice_client.is_paused():
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Nothing Paused",
            description="No song is currently paused to resume.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    bot.music_player.voice_client.resume()
    bot.music_player.is_playing = True # Update state
    embed = discord.Embed(
        title=f"{EMOJI_PLAYING} Playback Resumed",
        description="The song has been resumed.",
        color=EMBED_COLOR
    )
    await ctx.send(embed=embed)

@bot.command(name='skip', help=f'Skips the current song. Usage: `{bot.command_prefix}skip`')
async def skip(ctx):
    """
    Skips the current song.
    """
    if not bot.music_player.is_playing and bot.music_player.queue.empty():
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} No Song Playing",
            description="No song is currently playing or in the queue to skip.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Not Connected",
            description="I am not in a voice channel.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    members_in_vc = [m for m in bot.music_player.voice_client.channel.members if not m.bot]
    if len(members_in_vc) > 1:
        if ctx.author.id not in bot.music_player.skip_votes:
            bot.music_player.skip_votes[ctx.author.id] = True
            bot.music_player.skip_required = len(members_in_vc) // 2 + 1
            current_votes = len(bot.music_player.skip_votes)
            embed = discord.Embed(
                title=f"{EMOJI_VOTE} Skip Vote",
                description=f"Skip vote added by {ctx.author.display_name}. {current_votes}/{bot.music_player.skip_required} votes to skip.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            if current_votes >= bot.music_player.skip_required:
                bot.music_player.voice_client.stop()
                embed = discord.Embed(
                    title=f"{EMOJI_SKIPPED} Song Skipped!",
                    description="The song has been skipped by popular vote.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Vote Already Cast",
                description="You have already voted to skip this song.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
    else:
        bot.music_player.voice_client.stop()
        embed = discord.Embed(
            title=f"{EMOJI_SKIPPED} Song Skipped!",
            description="The song has been skipped.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

@bot.command(name='stop', help=f'Stops the current song, clears the queue, and leaves the voice channel. Usage: `{bot.command_prefix}stop`')
async def stop(ctx):
    """
    Stops the current song, clears the entire queue, and leaves the voice channel.
    """
    if not bot.music_player.voice_client:
        embed = discord.Embed(
            title=f"{EMOJI_ERROR} Not Playing",
            description="I am not currently playing anything or in a voice channel.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    if bot.music_player.voice_client.is_playing() or bot.music_player.voice_client.is_paused():
        bot.music_player.voice_client.stop()
        embed = discord.Embed(
            title=f"{EMOJI_STOPPED} Playback Stopped",
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
    bot.music_player.song_queue_list.clear()
    bot.music_player.current_song = None
    
    # Disconnect after stopping and clearing queue
    if await bot.music_player.disconnect_from_voice():
        embed = discord.Embed(
            title=f"{EMOJI_STOPPED} Disconnected",
            description="The music queue has been cleared and I have left the voice channel.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title=f"{EMOJI_STOPPED} Stopped",
            description="The music queue has been cleared.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)


@bot.command(name='queue', help=f'Shows the current music queue. Usage: `{bot.command_prefix}queue`')
async def show_queue(ctx):
    """
    Displays the current songs in the queue.
    """
    queue_display = []

    if bot.music_player.current_song:
        duration_str = format_duration(bot.music_player.current_song.get('duration'))
        queue_display.append(f"**Now Playing:** [{bot.music_player.current_song['title']}]({bot.music_player.current_song['webpage_url']}) (`{duration_str}`) (Requested by {bot.music_player.current_song['requester'].mention})")

    if bot.music_player.song_queue_list:
        queue_display.append("\n**Up Next:**")
        for i, song in enumerate(bot.music_player.song_queue_list):
            if i >= 10:
                queue_display.append(f"...and {len(bot.music_player.song_queue_list) - i} more!")
                break
            duration_str = format_duration(song.get('duration'))
            queue_display.append(f"{i+1}. [{song['title']}]({song['webpage_url']}) (`{duration_str}`) (Requested by {song['requester'].mention})")
    
    if not queue_display:
        embed = discord.Embed(
            title=f"{EMOJI_QUEUE} Music Queue",
            description="The queue is empty.",
            color=EMBED_COLOR
        )
        return await ctx.send(embed=embed)

    embed = discord.Embed(title=f"{EMOJI_QUEUE} Music Queue", description="\n".join(queue_display), color=EMBED_COLOR)
    await ctx.send(embed=embed)

@bot.command(name='help', help=f'Displays all available commands. Usage: `{bot.command_prefix}help`')
async def help_command(ctx):
    """
    Displays all available commands and their descriptions.
    """
    embed = discord.Embed(
        title=f"{EMOJI_HELP} Bot Commands",
        description="Here are all the commands you can use:",
        color=EMBED_COLOR
    )

    for command in bot.commands:
        if command.hidden:
            continue
        embed.add_field(name=f"`{bot.command_prefix}{command.name}`", value=command.help or "No description provided.", inline=False)
    
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
