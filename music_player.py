import discord
import yt_dlp as youtube_dl
import asyncio
import collections
import datetime
import time
import os
import shlex
import ipaddress
import re
import socket
import urllib.request
from urllib.parse import urlsplit, urlunsplit
from yt_dlp.networking._urllib import UrllibRH


YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com',
                 'music.youtube.com', 'youtu.be'}
YOUTUBE_INPUT_ERROR = 'Only YouTube links and plain search terms are supported.'


def youtube_url(value):
    """Validate a watch/playlist URL before it is handed to an extractor."""
    try:
        parts = urlsplit(value)
        if (parts.scheme not in ('http', 'https') or parts.hostname not in YOUTUBE_HOSTS
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 80, 443) or '\\' in value
                or any(ord(c) < 32 for c in value)):
            raise ValueError(YOUTUBE_INPUT_ERROR)
        # Upgrade input to HTTPS; never follow a user-supplied insecure URL.
        return urlunsplit(('https', parts.hostname, parts.path, parts.query, ''))
    except ValueError:
        raise ValueError(YOUTUBE_INPUT_ERROR) from None


def normalize_youtube_input(value):
    value = value.strip()
    if value.startswith('<') and value.endswith('>'):
        value = value[1:-1]
    if not value or any(ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError(YOUTUBE_INPUT_ERROR)
    if value.startswith('//'):
        return youtube_url('https:' + value)
    if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', value):
        return youtube_url(value)
    first = value.split('/', 1)[0].split('?', 1)[0]
    if first in YOUTUBE_HOSTS:
        return youtube_url('https://' + value)
    # Treat URL-looking text as a URL, never as an implicit extractor directive.
    if (re.match(r'^[^\s/]+\.[^\s/]+(?:[/?]|$)', value)
            or re.match(r'^(?:localhost|\[)[^\s]*', value, re.I)):
        raise ValueError(YOUTUBE_INPUT_ERROR)
    return 'ytsearch1:' + value


def validate_public_destination(url):
    """Check every extraction request/redirect, including YouTube CDN requests."""
    parts = urlsplit(url)
    host = parts.hostname or ''
    trusted = (host in YOUTUBE_HOSTS or host == 'youtubei.googleapis.com'
               or any(host == domain or host.endswith('.' + domain)
                      for domain in ('youtube.com', 'googlevideo.com', 'ytimg.com')))
    if (parts.scheme != 'https' or not trusted or parts.port not in (None, 443)
            or parts.username is not None or parts.password is not None):
        raise ValueError('Blocked a request outside YouTube and its media services.')
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as error:
        raise ValueError('Could not resolve the YouTube server. Please try again.') from error
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Blocked a YouTube server resolving to a private/internal address.')


class _PublicYouTubeRequests(urllib.request.BaseHandler):
    def https_request(self, request):
        validate_public_destination(request.full_url)
        return request

    http_request = https_request


class _YouTubeUrllibRH(UrllibRH):
    def _create_instance(self, *args, **kwargs):
        opener = super()._create_instance(*args, **kwargs)
        # urllib runs request processors again on redirect destinations.
        opener.add_handler(_PublicYouTubeRequests())
        return opener

    def _send(self, request):
        validate_public_destination(request.url)
        return super()._send(request)


class YouTubeDL(youtube_dl.YoutubeDL):
    def build_request_director(self, handlers, preferences=None):
        # Do not allow an alternate transport to bypass the redirect guard.
        return super().build_request_director([_YouTubeUrllibRH])


def extract_youtube_info(extractor, query):
    if not query.startswith('ytsearch1:'):
        query = youtube_url(query)
        validate_public_destination(query)
    return extractor.extract_info(query, download=False)

# --- Global Constants for MusicPlayer (can be shared with cog if needed) ---
EMBED_COLOR = discord.Color(0xFFB6C1) # Light Pink

EMOJI_PLAYING = "<a:MusicalHearts:1393976474888966308>"
EMOJI_PAUSED = "<:Spotify_Pause:1393976498179936317>"
EMOJI_ADDED = "<:pinkcheckmark:1393976477262807100>"
EMOJI_SKIPPED = "<:Skip:1393976495155839099>"
EMOJI_STOPPED = "⏹️"
EMOJI_JOINED = "<:screenshare_volume_max:1393976485643030661>"
EMOJI_DISCONNECTED = "<:SilverMute:1393976492261769247>"
EMOJI_ERROR = "<:pinkcrossmark:1393976480014401586>"
EMOJI_FETCHING = "<:SearchCloud:1393976489564700712>"
EMOJI_QUEUE = "<:Spotify_Queue:1393976501090783283>"
EMOJI_VOTE = "<:downvote:1393976467196481678>"
EMOJI_HELP = "<:pinkquestionmark:1393976483118055475>"
EMOJI_PLAYLIST = "<:list:1393976471193784352>"

# --- Helper Function for Duration Formatting ---
def format_duration(seconds):
    """Formats duration in seconds to HH:MM:SS or MM:SS."""
    if seconds is None:
        return "N/A"
    
    td = datetime.timedelta(seconds=int(seconds))
    
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

# --- Audio Player Class ---
class MusicPlayer:
    def __init__(self, bot):
        self.bot = bot
        self.queue = asyncio.Queue()
        self.song_queue_list = collections.deque() 
        self.current_song = None
        self.voice_client = None
        self.voice_connection_lock = asyncio.Lock()
        self.is_playing = False
        self.skip_votes = {}
        self.skip_required = 0
        self.now_playing_message = None
        self.progress_update_task = None
        self.playback_start_time = 0
        self.paused_at_time = 0

        # YTDL options for downloading audio (general options, will be modified for playlist extraction)
        self.YTDL_OPTIONS = {
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'error',
            'allowed_extractors': ['youtube.*'],
            'proxy': '',
            # Node is opt-in in yt-dlp; keep Deno available where installed.
            'js_runtimes': {'deno': {}, 'node': {}},
            'source_address': '0.0.0.0',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

        # FFmpeg options for playing audio
        self.FFMPEG_OPTIONS = {
            'options': '-vn',
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
        }

        # Get FFMPEG_PATH from environment variables
        ffmpeg_path = os.getenv('FFMPEG_PATH')
        if ffmpeg_path:
            normalized_ffmpeg_path = os.path.normpath(ffmpeg_path)
            if os.path.isdir(normalized_ffmpeg_path):
                ffmpeg_executable_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
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

        self.yt_dlp = YouTubeDL(self.YTDL_OPTIONS)
        self.audio_player_task = bot.loop.create_task(self.audio_player_loop())

    async def _update_now_playing_progress(self, song_info, message):
        """
        Updates the 'Now Playing' message with live song progress.
        """
        total_duration = song_info.get('duration')
        if total_duration is None or total_duration == 0:
            return

        while self.voice_client and self.current_song == song_info and self.voice_client.is_connected():
            if self.voice_client.is_playing():
                elapsed_time = time.time() - self.playback_start_time
            elif self.voice_client.is_paused():
                elapsed_time = self.paused_at_time
            else:
                break

            if elapsed_time > total_duration:
                elapsed_time = total_duration

            elapsed_str = format_duration(elapsed_time)
            total_str = format_duration(total_duration)

            bar_length = 20
            if total_duration > 0:
                filled_blocks = int((elapsed_time / total_duration) * bar_length)
            else:
                filled_blocks = 0
            progress_bar = "█" * filled_blocks + "─" * (bar_length - filled_blocks)

            new_description = (
                f"**[{song_info['title']}]({song_info['webpage_url']})** "
                f"(Requested by {song_info['requester'].mention})\n"
                f"`{elapsed_str} {progress_bar} {total_str}`"
            )
            try:
                fetched_message = await message.channel.fetch_message(message.id)
                if fetched_message:
                    updated_embed = discord.Embed(
                        title=f"{EMOJI_PLAYING} Now Playing",
                        description=new_description,
                        color=EMBED_COLOR
                    )
                    await message.edit(embed=updated_embed)
            except discord.NotFound:
                break
            except Exception as e:
                print(f"DEBUG: Error updating live progress message: {e}")
                break

            await asyncio.sleep(5)

        if self.current_song == song_info and message:
            try:
                fetched_message = await message.channel.fetch_message(message.id)
                if fetched_message:
                    final_description = (
                        f"**[{song_info['title']}]({song_info['webpage_url']})**\n"
                        f"Duration: `{format_duration(total_duration)}` (Requested by {song_info['requester'].mention})"
                    )
                    final_embed = discord.Embed(
                        title=f"{EMOJI_PLAYING} Now Playing (Finished)",
                        description=final_description,
                        color=EMBED_COLOR
                    )
                    await message.edit(embed=final_embed)
            except discord.NotFound:
                pass
            except Exception as e:
                print(f"DEBUG: Error finalizing Now Playing message: {e}")

    async def audio_player_loop(self):
        """
        Main loop for playing songs from the queue.
        """
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            while True:
                if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                    await asyncio.sleep(1)
                elif not self.queue.empty():
                    break
                else:
                    await asyncio.sleep(1)

            if self.progress_update_task and not self.progress_update_task.done():
                self.progress_update_task.cancel()
                try:
                    await self.progress_update_task
                except asyncio.CancelledError:
                    pass
                self.progress_update_task = None
                self.now_playing_message = None

            self.current_song = None
            self.is_playing = False
            self.playback_start_time = 0
            self.paused_at_time = 0

            try:
                song = await self.queue.get()
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"Error getting song from queue: {e}")
                continue

            self.current_song = song
            self.skip_votes = {}

            if self.voice_client and self.voice_client.is_connected():
                try:
                    if self.FFMPEG_OPTIONS.get('executable') is None and os.getenv('FFMPEG_PATH') is not None:
                        print("FFmpeg executable path is invalid. Cannot play audio.")
                        embed = discord.Embed(
                            title=f"{EMOJI_ERROR} Error",
                            description="FFMpeg executable not found. Please check your FFMPEG_PATH in the .env file.",
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
                        title=f"{EMOJI_FETCHING} Fetching Song Details...",
                        description=f"Getting details for **[{song.get('title', 'a song')}]({song['webpage_url']})**...",
                        color=EMBED_COLOR
                    ))
                    
                    ytdl_single_video = YouTubeDL(self.YTDL_OPTIONS.copy())
                    full_song_data = await self.bot.loop.run_in_executor(
                        None, lambda: extract_youtube_info(ytdl_single_video, song['webpage_url'])
                    )

                    # stop() can clear the current song while the executor runs.
                    # Threads cannot be safely cancelled: discard the stale result
                    # and finish this queue item without starting any audio.
                    if self.current_song is not song:
                        self.queue.task_done()
                        continue
                    
                    self.current_song['title'] = full_song_data.get('title', self.current_song.get('title', 'Unknown Title'))
                    self.current_song['duration'] = full_song_data.get('duration')
                    fresh_audio_url = full_song_data.get('url')

                    if not fresh_audio_url:
                        raise ValueError(f"Could not get fresh audio URL for {self.current_song['title']}")

                    ffmpeg_options = self.FFMPEG_OPTIONS.copy()
                    headers = full_song_data.get('http_headers') or {}
                    if headers:
                        # discord.py parses before_options with shlex.split,
                        # including on Windows. Keep the CRLF header block as
                        # one argument, preserving spaces and quotes in values.
                        header_block = ''.join(f'{name}: {value}\r\n'
                                               for name, value in headers.items())
                        ffmpeg_options['before_options'] += f' -headers {shlex.quote(header_block)}'
                    source = discord.FFmpegPCMAudio(fresh_audio_url, **ffmpeg_options)
                    self.voice_client.play(source, after=lambda e: self.bot.loop.call_soon_threadsafe(self.play_next_song, e))
                    self.is_playing = True
                    self.playback_start_time = time.time()
                    print(f"Now playing: {self.current_song['title']}")
                    
                    initial_duration_str = format_duration(self.current_song.get('duration'))
                    initial_embed = discord.Embed(
                        title=f"{EMOJI_PLAYING} Now Playing",
                        description=f"**[{self.current_song['title']}]({self.current_song['webpage_url']})**\nDuration: `{initial_duration_str}` (Requested by {self.current_song['requester'].mention})",
                        color=EMBED_COLOR
                    )
                    self.now_playing_message = await self.current_song['channel'].send(embed=initial_embed)
                    
                    if self.current_song.get('duration') is not None and self.current_song.get('duration') > 0:
                        print(f"Starting progress update task for {self.current_song['title']} (Duration: {self.current_song['duration']}).")
                        self.progress_update_task = self.bot.loop.create_task(
                            self._update_now_playing_progress(self.current_song, self.now_playing_message)
                        )
                    else:
                        print(f"Not starting progress update task for {self.current_song['title']} due to missing/zero duration.")

                except Exception as e:
                    # Extraction may also fail after stop(); do not dereference
                    # cleared state or report an error for a cancelled song.
                    if self.current_song is not song:
                        self.queue.task_done()
                        continue
                    print(f"Error playing song: {e}")
                    embed = discord.Embed(
                        title=f"{EMOJI_ERROR} Playback Error",
                        description=f"Error playing **{song.get('title', 'a song')}**: `{e}`. Skipping to next song.",
                        color=EMBED_COLOR
                    )
                    await song['channel'].send(embed=embed)
                    self.play_next_song(e)
            else:
                print("Voice client not connected, skipping song.")
                self.play_next_song(None)

    def play_next_song(self, error):
        """
        Callback function called after a song finishes or an error occurs.
        """
        if error:
            print(f"Player error in play_next_song: {error}")
        self.is_playing = False
        print(f"Song finished or errored, is_playing set to False.")
        self.bot.loop.call_soon_threadsafe(self.queue.task_done)
        if self.progress_update_task and not self.progress_update_task.done():
            self.progress_update_task.cancel()
            self.progress_update_task = None
            self.now_playing_message = None
        self.playback_start_time = 0
        self.paused_at_time = 0

    async def add_to_queue(self, ctx, url):
        """
        Adds a song or playlist to the queue.
        """
        try:
            query = normalize_youtube_input(url)
        except ValueError as error:
            await ctx.send(embed=discord.Embed(title=f"{EMOJI_ERROR} Unsupported Link",
                                              description=str(error), color=EMBED_COLOR))
            return
        try:
            ytdl_options_for_playlist_info = self.YTDL_OPTIONS.copy()
            ytdl_options_for_playlist_info['noplaylist'] = False
            ytdl_options_for_playlist_info['extract_flat'] = True
            if 'postprocessors' in ytdl_options_for_playlist_info:
                del ytdl_options_for_playlist_info['postprocessors']

            yt_dlp_instance_for_playlist = YouTubeDL(ytdl_options_for_playlist_info)

            try:
                data = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, lambda: extract_youtube_info(yt_dlp_instance_for_playlist, query)),
                    timeout=180
                )
            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title=f"{EMOJI_ERROR} Extraction Timeout",
                    description=f"Failed to extract information from `{url}` within 180 seconds. The link might be too large or problematic.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
                print(f"DEBUG: Extraction Timeout for URL: {url}")
                return

            print(f"DEBUG: Raw data extracted by yt-dlp: {data.keys() if isinstance(data, dict) else data}")

            songs_to_add = []
            if 'entries' in data:
                playlist_title = data.get('title', 'Unknown Playlist')
                print(f"DEBUG: Processing playlist '{playlist_title}' with {len(data.get('entries', []))} entries.")
                for i, entry in enumerate(data['entries']):
                    if entry and entry.get('url'):
                        song_info = {
                            'title': entry.get('title', f"Song {i+1} (Fetching...)"),
                            'webpage_url': youtube_url(entry['url']),
                            'duration': None,
                            'channel': ctx.channel,
                            'requester': ctx.author
                        }
                        songs_to_add.append(song_info)
                        print(f"DEBUG: Added playlist entry {i+1}: {song_info['webpage_url']}")
                    else:
                        print(f"DEBUG: Skipping invalid playlist entry at index {i} (entry is None or missing URL).")
                
                if not songs_to_add:
                    embed = discord.Embed(
                        title=f"{EMOJI_ERROR} Playlist Empty or Invalid",
                        description=f"No valid songs could be extracted from the playlist: **[{playlist_title}]({url})**.",
                        color=EMBED_COLOR
                    )
                    await ctx.send(embed=embed)
                    return

                embed = discord.Embed(
                    title=f"{EMOJI_PLAYLIST} Playlist Added!",
                    description=f"Added **{len(songs_to_add)}** songs from playlist **[{playlist_title}]({url})** to the queue.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
            elif data:
                song_info = {
                    'title': data.get('title', 'Unknown Title'),
                    'webpage_url': youtube_url(data.get('webpage_url') or ''),
                    'duration': data.get('duration'),
                    'channel': ctx.channel,
                    'requester': ctx.author
                }
                songs_to_add.append(song_info)
                print(f"DEBUG: Added single song: {song_info['title']}")
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
            else:
                embed = discord.Embed(
                    title=f"{EMOJI_ERROR} Extraction Error",
                    description=f"Could not extract any information from the provided URL: `{url}`. It might be invalid or unsupported.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
                print(f"DEBUG: No data extracted from URL: {url}")
                return

            for song_info in songs_to_add:
                if song_info['webpage_url']:
                    await self.queue.put(song_info)
                    self.song_queue_list.append(song_info)
                    print(f"DEBUG: Successfully put '{song_info['title']}' into internal queues.")
                else:
                    print(f"DEBUG: Skipping invalid song entry: {song_info.get('title', 'Unknown Title')} (Missing webpage_url).")

        except youtube_dl.DownloadError as e:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Download Error",
                description=f"Could not download/extract info for `{url}`: `{e}`. This might be a private video or unsupported link.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            print(f"DEBUG: DownloadError in add_to_queue: {e}")
        except Exception as e:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Error",
                description=f"An error occurred while processing your request: `{e}`",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)
            print(f"DEBUG: General Error in add_to_queue: {e}")

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
            while not self.queue.empty():
                try:
                    self.queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.song_queue_list.clear()
            self.current_song = None
            self.skip_votes.clear()
            self.skip_required = 0
            self.now_playing_message = None
            if self.progress_update_task and not self.progress_update_task.done():
                self.progress_update_task.cancel()
                self.progress_update_task = None
                self.now_playing_message = None
            self.playback_start_time = 0
            self.paused_at_time = 0
            return True
        return False

