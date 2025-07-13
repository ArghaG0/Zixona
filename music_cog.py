import discord
from discord.ext import commands
import asyncio
import time
# Import the MusicPlayer class and format_duration function from the new music_player.py file
from music_player import MusicPlayer, format_duration, EMBED_COLOR, EMOJI_ERROR, EMOJI_PLAYING, EMOJI_PAUSED, EMOJI_ADDED, EMOJI_SKIPPED, EMOJI_STOPPED, EMOJI_JOINED, EMOJI_DISCONNECTED, EMOJI_FETCHING, EMOJI_QUEUE, EMOJI_VOTE, EMOJI_HELP, EMOJI_PLAYLIST


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
        # Initialize the MusicPlayer instance
        self.player = MusicPlayer(bot)

    @commands.command(name='play', help=f'Plays a song from YouTube (or other platforms). If a song is playing, it adds to queue. Usage: `zixplay <URL or search term>`')
    async def play(self, ctx, *, url):
        """
        Plays a song. If a song is already playing, it adds it to the queue.
        Supports YouTube URLs, playlists, or search terms. Automatically joins VC.
        """
        print(f"DEBUG: 'zixplay' command received with URL/search: {url}")
        if not ctx.author.voice:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Voice Channel Required",
                description="You are not in a voice channel. Please join one first.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        channel = ctx.author.voice.channel
        if self.player.voice_client is None or self.player.voice_client.channel != channel:
            try:
                await self.player.connect_to_voice(channel)
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

        if not self.player.voice_client:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Connection Error",
                description="I could not connect to a voice channel. Please try again.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        await self.player.add_to_queue(ctx, url)

    @commands.command(name='pause', help=f'Pauses the current song. Usage: `zixpause`')
    async def pause(self, ctx):
        """
        Pauses the currently playing song.
        """
        if not self.player.voice_client or not self.player.voice_client.is_playing():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Nothing Playing",
                description="No song is currently playing to pause.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)
        
        if self.player.voice_client.is_paused():
            embed = discord.Embed(
                title=f"{EMOJI_PAUSED} Already Paused",
                description="The song is already paused.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        self.player.voice_client.pause()
        self.player.is_playing = False
        if self.player.playback_start_time != 0:
            self.player.paused_at_time = time.time() - self.player.playback_start_time
        if self.player.progress_update_task and not self.player.progress_update_task.done():
            self.player.progress_update_task.cancel()
            self.player.progress_update_task = None
        embed = discord.Embed(
            title=f"{EMOJI_PAUSED} Playback Paused",
            description="The current song has been paused.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name='resume', help=f'Resumes the paused song. Usage: `zixresume`')
    async def resume(self, ctx):
        """
        Resumes the currently paused song.
        """
        if not self.player.voice_client or not self.player.voice_client.is_paused():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Nothing Paused",
                description="No song is currently paused to resume.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        self.player.voice_client.resume()
        self.player.is_playing = True
        self.player.playback_start_time = time.time() - self.player.paused_at_time
        if self.player.current_song and self.player.now_playing_message and self.player.progress_update_task is None:
            if self.player.current_song.get('duration') is not None and self.player.current_song.get('duration') > 0:
                print(f"DEBUG: Restarting progress update task for {self.player.current_song['title']}.")
                self.player.progress_update_task = self.bot.loop.create_task(
                    self.player._update_now_playing_progress(self.player.current_song, self.player.now_playing_message)
                )
            else:
                print(f"DEBUG: Not restarting progress update task for {self.player.current_song['title']} due to missing/zero duration.")

        embed = discord.Embed(
            title=f"{EMOJI_PLAYING} Playback Resumed",
            description="The song has been resumed.",
            color=EMBED_COLOR
        )
        await ctx.send(embed=embed)

    @commands.command(name='skip', help=f'Skips the current song. Usage: `zixskip`')
    async def skip(self, ctx):
        """
        Skips the current song.
        """
        if not self.player.is_playing and self.player.queue.empty():
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} No Song Playing",
                description="No song is currently playing or in the queue to skip.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        if not self.player.voice_client:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Not Connected",
                description="I am not in a voice channel.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        members_in_vc = [m for m in self.player.voice_client.channel.members if not m.bot]
        if len(members_in_vc) > 1:
            if ctx.author.id not in self.player.skip_votes:
                self.player.skip_votes[ctx.author.id] = True
                self.player.skip_required = len(members_in_vc) // 2 + 1
                current_votes = len(self.player.skip_votes)
                embed = discord.Embed(
                    title=f"{EMOJI_VOTE} Skip Vote",
                    description=f"Skip vote added by {ctx.author.display_name}. {current_votes}/{self.player.skip_required} votes to skip.",
                    color=EMBED_COLOR
                )
                await ctx.send(embed=embed)
                if current_votes >= self.player.skip_required:
                    self.player.voice_client.stop()
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
            self.player.voice_client.stop()
            embed = discord.Embed(
                title=f"{EMOJI_SKIPPED} Song Skipped!",
                description="The song has been skipped.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)

    @commands.command(name='stop', help=f'Stops the current song, clears the queue, and leaves the voice channel. Usage: `zixstop`')
    async def stop(self, ctx):
        """
        Stops the current song, clears the entire queue, and leaves the voice channel.
        """
        if not self.player.voice_client:
            embed = discord.Embed(
                title=f"{EMOJI_ERROR} Not Playing",
                description="I am not currently playing anything or in a voice channel.",
                color=EMBED_COLOR
            )
            return await ctx.send(embed=embed)

        if self.player.voice_client.is_playing() or self.player.voice_client.is_paused():
            self.player.voice_client.stop()
            embed = discord.Embed(
                title=f"{EMOJI_STOPPED} Playback Stopped",
                description="Playback stopped.",
                color=EMBED_COLOR
            )
            await ctx.send(embed=embed)

        while not self.player.queue.empty():
            try:
                self.player.queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.player.song_queue_list.clear()
        self.player.current_song = None
        
        if await self.player.disconnect_from_voice():
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

    @commands.command(name='queue', help=f'Shows the current music queue. Usage: `zixqueue`')
    async def show_queue(self, ctx):
        """
        Displays the current songs in the queue with pagination.
        """
        total_queue_items = len(self.player.song_queue_list)
        
        if self.player.current_song:
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

        view = QueueView(ctx, self.player, total_pages)
        view.message = await ctx.send(embed=view._generate_embed(), view=view)

    @commands.command(name='help', help=f'Displays all available commands. Usage: `zixhelp`')
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
            embed.add_field(name=f"`{self.bot.command_prefix}{command.name}`", value=command.help or "No description provided.", inline=False)
        
        await ctx.send(embed=embed)

# --- Setup function for the Cog ---
async def setup(bot):
    """
    Adds the MusicCog to the bot.
    """
    await bot.add_cog(MusicCog(bot))

