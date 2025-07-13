import discord
import yt_dlp as youtube_dl
import asyncio
import collections
import datetime
import time
import os

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
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
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

        self.yt_dlp = youtube_dl.YoutubeDL(self.YTDL_OPTIONS)
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
                    
                    ytdl_single_video = youtube_dl.YoutubeDL(self.YTDL_OPTIONS.copy())
                    full_song_data = await self.bot.loop.run_in_executor(
                        None, lambda: ytdl_single_video.extract_info(song['webpage_url'], download=False)
                    )
                    
                    self.current_song['title'] = full_song_data.get('title', self.current_song.get('title', 'Unknown Title'))
                    self.current_song['duration'] = full_song_data.get('duration')
                    fresh_audio_url = full_song_data.get('url')

                    if not fresh_audio_url:
                        raise ValueError(f"Could not get fresh audio URL for {self.current_song['title']}")

                    source = discord.FFmpegPCMAudio(fresh_audio_url, **self.FFMPEG_OPTIONS)
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
                    print(f"Error playing song: {e}")
                    embed = discord.Embed(
                        title=f"{EMOJI_ERROR} Playback Error",
                        description=f"Error playing **{self.current_song.get('title', 'a song')}**: `{e}`. Skipping to next song.",
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
        print(f"DEBUG: add_to_queue called with URL: {url}")
        try:
            ytdl_options_for_playlist_info = self.YTDL_OPTIONS.copy()
            ytdl_options_for_playlist_info['noplaylist'] = False
            ytdl_options_for_playlist_info['extract_flat'] = True
            if 'postprocessors' in ytdl_options_for_playlist_info:
                del ytdl_options_for_playlist_info['postprocessors']

            yt_dlp_instance_for_playlist = youtube_dl.YoutubeDL(ytdl_options_for_playlist_info)

            try:
                data = await asyncio.wait_for(
                    self.bot.loop.run_in_executor(None, lambda: yt_dlp_instance_for_playlist.extract_info(url, download=False)),
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
                            'webpage_url': entry['url'],
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
                    'webpage_url': data.get('webpage_url'),
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
            if self.progress_update_task and not self.progress_update_task.done():
                self.progress_update_task.cancel()
                self.progress_update_task = None
                self.now_playing_message = None
            self.playback_start_time = 0
            self.paused_at_time = 0
            return True
        return False

