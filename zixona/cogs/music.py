import discord
from discord.ext import commands
import asyncio
import time
from zixona.player import MusicPlayer
from zixona.presentation import format_duration, EMBED_COLOR, EMOJI_ERROR, EMOJI_PLAYING, EMOJI_PAUSED, EMOJI_ADDED, EMOJI_SKIPPED, EMOJI_STOPPED, EMOJI_JOINED, EMOJI_DISCONNECTED, EMOJI_FETCHING, EMOJI_QUEUE, EMOJI_VOTE, EMOJI_HELP, EMOJI_PLAYLIST


# --- Queue View for Pagination ---
class QueueView(discord.ui.View):
    def __init__(self, ctx, player, total_pages, current_page=0):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.player = player
        self.total_pages = total_pages
        self.current_page = current_page
        self.update_buttons()

    def _generate_embed(self):
        start_index = self.current_page * 10
        end_index = start_index + 10
        
        queue_display = []

        if self.current_page == 0 and self.player.current_song:
            elapsed_time = 0
            if self.player.voice_client and self.player.current_song:
                if self.player.voice_client.is_playing():
                    elapsed_time = time.time() - self.player.playback_start_time
                elif self.player.voice_client.is_paused():
                    elapsed_time = self.player.paused_at_time
            
            total_duration = self.player.current_song.get('duration')
            duration_str = format_duration(total_duration)
            elapsed_str = format_duration(elapsed_time)
            
            if total_duration and total_duration > 0:
                bar_length = 10
                current_elapsed_for_bar = min(elapsed_time, total_duration)
                filled_blocks = int((current_elapsed_for_bar / total_duration) * bar_length)
                progress_bar = "█" * filled_blocks + "─" * (bar_length - filled_blocks)
                queue_display.append(f"**Now Playing:** [{self.player.current_song['title']}]({self.player.current_song['webpage_url']})\n`{elapsed_str} {progress_bar} {duration_str}` (Requested by {self.player.current_song['requester'].mention})")
            else:
                queue_display.append(f"**Now Playing:** [{self.player.current_song['title']}]({self.player.current_song['webpage_url']}) (`{duration_str}`) (Requested by {self.player.current_song['requester'].mention})")
            
            queue_display.append("\n**Up Next:**")

        songs_on_page = list(self.player.song_queue_list)[start_index:end_index]

        if not songs_on_page and not (self.current_page == 0 and self.player.current_song):
            return discord.Embed(
                title=f"{EMOJI_QUEUE} Music Queue",
                description="The queue is empty.",
                color=EMBED_COLOR
            )

        for i, song in enumerate(songs_on_page):
            display_index = start_index + i + 1
            duration_str = format_duration(song.get('duration'))
            queue_display.append(f"{display_index}. [{song['title']}]({song['webpage_url']}) (`{duration_str}`) (Requested by {song['requester'].mention})")

        embed = discord.Embed(
            title=f"{EMOJI_QUEUE} Music Queue (Page {self.current_page + 1}/{self.total_pages})",
            description="\n".join(queue_display),
            color=EMBED_COLOR
        )
        return embed

    def update_buttons(self):
        self.clear_items()
        if self.current_page > 0:
            self.add_item(self.previous_button)
        if self.current_page < self.total_pages - 1:
            self.add_item(self.next_button)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.blurple, emoji="◀️")
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You can't control this queue view.", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self._generate_embed(), view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.blurple, emoji="▶️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You can't control this queue view.", ephemeral=True)
            return
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self._generate_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("You can't control this queue view.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass

# --- Music Cog Class ---
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Retain one player per guild until this cog unloads. Replacing players
        # on stop would race with in-flight extraction and audio callbacks.
        self.players: dict[int, MusicPlayer] = {}

    def get_player(self, ctx):
        """Resolve guild ownership before accessing any playback state."""
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        guild_id = ctx.guild.id
        # No await between lookup and insertion: concurrent commands in the
        # event loop cannot create two players for the same guild here.
        if guild_id not in self.players:
            self.players[guild_id] = MusicPlayer(self.bot)
        return self.players[guild_id]

    async def check_voice_access(self, ctx, player, *, allow_join=False):
        """Shared guard for commands that modify playback; no moderator bypass."""
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        user_voice = getattr(ctx.author, 'voice', None)
        user_channel = user_voice.channel if user_voice else None
        voice = player.voice_client
        connected = voice is not None and voice.is_connected()
        if user_channel is None:
            message = "Join my voice channel to control playback." if connected else "Join a voice channel first."
        elif connected and user_channel != voice.channel:
            message = ("I'm busy in another voice channel. Join that channel to add music."
                       if allow_join else "You must be in my voice channel to control playback.")
        elif not connected and not allow_join:
            message = "I'm not connected to a voice channel. Use `zix play` to start a session."
        else:
            return True
        await ctx.send(embed=discord.Embed(
            title=f"{EMOJI_ERROR} Voice Channel Required",
            description=message, color=EMBED_COLOR))
        return False

    async def cog_unload(self):
        players = list(self.players.values())
        self.players.clear()
        tasks = [task for player in players
                 for task in (player.audio_player_task, player.progress_update_task)
                 if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.gather(*(player.disconnect_from_voice() for player in players))

    @commands.command(name='play', usage='<YouTube URL or search term>', help='Plays a song from YouTube. If a song is playing, it adds to queue.')
    async def play(self, ctx, *, url):
        """
        Plays a song. If a song is already playing, it adds it to the queue.
        Supports YouTube URLs, playlists, or search terms. Automatically joins VC.
        """
        player = self.get_player(ctx)
        async with player.voice_connection_lock:
            if not await self.check_voice_access(ctx, player, allow_join=True):
                return
            channel = ctx.author.voice.channel
            if player.voice_client is None or player.voice_client.channel != channel:
                try:
                    await player.connect_to_voice(channel)
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

            if not player.voice_client:
                embed = discord.Embed(
                    title=f"{EMOJI_ERROR} Connection Error",
                    description="I could not connect to a voice channel. Please try again.",
                    color=EMBED_COLOR
                )
                return await ctx.send(embed=embed)

        await player.add_to_queue(ctx, url)

    @commands.command(name='pause', help='Pauses the current song.')
    async def pause(self, ctx):
        """
        Pauses the currently playing song.
        """
        player = self.get_player(ctx)
        if not await self.check_voice_access(ctx, player):
            return
        if not player.voice_client or not player.voice_client.is_playing():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Nothing Playing",
                description="No song is currently playing to pause.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)
        
        if player.voice_client.is_paused():
            embed = discord.Embed(
                title=f"{EMOJI_PAUSED} Already Paused",
                description="The song is already paused.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        player.voice_client.pause()
        player.is_playing = False
        if player.playback_start_time != 0:
            player.paused_at_time = time.time() - player.playback_start_time
        if player.progress_update_task and not player.progress_update_task.done():
            player.progress_update_task.cancel()
            player.progress_update_task = None
        embed = discord.Embed(
            title=f"{EMOJI_PAUSED} Playback Paused",
            description="The current song has been paused.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name='resume', help='Resumes the paused song.')
    async def resume(self, ctx):
        """
        Resumes the currently paused song.
        """
        player = self.get_player(ctx)
        if not await self.check_voice_access(ctx, player):
            return
        if not player.voice_client or not player.voice_client.is_paused():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Nothing Paused",
                description="No song is currently paused to resume.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        player.voice_client.resume()
        player.is_playing = True
        player.playback_start_time = time.time() - player.paused_at_time
        if player.current_song and player.now_playing_message and player.progress_update_task is None:
            if player.current_song.get('duration') is not None and player.current_song.get('duration') > 0:
                print(f"DEBUG: Restarting progress update task for {player.current_song['title']}.")
                player.progress_update_task = self.bot.loop.create_task(
                    player._update_now_playing_progress(player.current_song, player.now_playing_message)
                )
            else:
                print(f"DEBUG: Not restarting progress update task for {player.current_song['title']} due to missing/zero duration.")

        embed = discord.Embed(
            title=f"{EMOJI_PLAYING} Playback Resumed",
            description="The song has been resumed.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name='skip', help='Skips the current song.')
    async def skip(self, ctx):
        """
        Skips the current song.
        """
        player = self.get_player(ctx)
        if not await self.check_voice_access(ctx, player):
            return
        if not player.is_playing and player.queue.empty():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} No Song Playing",
                description="No song is currently playing or in the queue to skip.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        if not player.voice_client:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Not Connected",
                description="I am not in a voice channel.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        members_in_vc = [m for m in player.voice_client.channel.members if not m.bot]
        if len(members_in_vc) > 1:
            if ctx.author.id not in player.skip_votes:
                player.skip_votes[ctx.author.id] = True
                player.skip_required = len(members_in_vc) // 2 + 1
                current_votes = len(player.skip_votes)
                embed = discord.Embed(
                    title=f"{EMOJI_VOTE} Skip Vote",
                    description=f"Skip vote added by {ctx.author.display_name}. {current_votes}/{player.skip_required} votes to skip.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
                if current_votes >= player.skip_required:
                    player.stop_audio()
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
            player.stop_audio()
            embed = discord.Embed(
                title=f"{EMOJI_SKIPPED} Song Skipped!",
                description="The song has been skipped.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)

    @commands.command(name='stop', help='Stops the current song, clears the queue, and leaves the voice channel.')
    async def stop(self, ctx):
        """
        Stops the current song, clears the entire queue, and leaves the voice channel.
        """
        player = self.get_player(ctx)
        if not await self.check_voice_access(ctx, player):
            return
        if not player.voice_client:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Not Playing",
                description="I am not currently playing anything or in a voice channel.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        player.invalidate_session()
        if player.voice_client.is_playing() or player.voice_client.is_paused():
            player.stop_audio()
            embed = discord.Embed(
                title=f"{EMOJI_STOPPED} Playback Stopped",
                description="Playback stopped.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)

        while not player.queue.empty():
            try:
                player.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        player.song_queue_list.clear()
        player.current_song = None
        
        if await player.disconnect_from_voice():
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

    @commands.command(name='queue', help='Shows the current music queue.')
    async def show_queue(self, ctx):
        """
        Displays the current songs in the queue with pagination.
        """
        player = self.get_player(ctx)
        total_queue_items = len(player.song_queue_list)
        
        if player.current_song:
            if total_queue_items == 0:
                total_pages = 1
            else:
                remaining_songs = max(0, total_queue_items - 9)
                total_pages = 1 + (remaining_songs + 9) // 10
        else:
            total_pages = (total_queue_items + 9) // 10

        if total_pages == 0:
            embed = discord.Embed(
                title=f"{EMOJI_QUEUE} Music Queue",
                description="The queue is empty.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        view = QueueView(ctx, player, total_pages)
        view.message = await ctx.send(embed=view._generate_embed(), view=view)

    @commands.command(name='help', help='Displays all available commands.')
    async def help_command(self, ctx):
        """
        Displays all available commands and their descriptions.
        """
        embed = discord.Embed(
            title=f"{EMOJI_HELP} Bot Commands",
            description="Here are all the commands you can use:",
            color=EMBED_COLOR
        )

        for command in self.bot.commands:
            if command.hidden:
                continue
            syntax = f"{self.bot.command_prefix}{command.qualified_name} {command.signature}".rstrip()
            embed.add_field(name=f"`{syntax}`", value=command.help or "No description provided.", inline=False)
        
        await ctx.send(embed=embed)

# --- Setup function for the Cog ---
async def setup(bot):
    """
    Adds the MusicCog to the bot.
    """
    await bot.add_cog(MusicCog(bot))

