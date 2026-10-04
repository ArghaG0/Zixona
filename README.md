# **Zixona \- Your Discord Music Bot**

Zixona is a feature-rich Discord music bot designed to bring high-quality audio playback and seamless music management to your Discord server. Built with discord.py, yt-dlp, and ffmpeg, Zixona offers a smooth and interactive music experience, including live progress updates and a paginated queue.

## **Features**

* **High-Quality Audio:** Plays music from YouTube and other supported platforms.  
* **Queue Management:** Add multiple songs to a queue for continuous playback.  
* **Live Progress Bar:** See the current song's progress directly in the "Now Playing" embed.  
* **Interactive Pagination:** Navigate through large music queues using "Previous" and "Next" buttons.  
* **Playback Controls:** Pause, resume, skip, and stop commands.  
* **Vote Skip:** Allow server members to vote to skip the current song.  
* **Modular Design:** Built with discord.py cogs for easy extension and maintenance.

## Setup with uv

Requires Python **3.13**, [uv](https://docs.astral.sh/uv/getting-started/installation/),
FFmpeg on PATH, and **Node.js 22+** on PATH for yt-dlp's JavaScript challenges.
The tested local versions are Python 3.13.5 and Node.js 22.18.0.

From the cloned repository, install the locked dependencies:

```powershell
uv sync --locked
```

uv manages `.venv` automatically. `pyproject.toml` declares discord.py with voice
support (including DAVE), yt-dlp with EJS, python-dotenv, and PyNaCl. `uv.lock`
locks the complete dependency graph. No separate pip install is needed.

Create `.env` in the project root:

```dotenv
DISCORD_BOT_TOKEN="YOUR_BOT_TOKEN"
# Optional: absolute executable path; omit entirely when FFmpeg is on PATH.
FFMPEG_PATH="C:/path/to/ffmpeg/bin/ffmpeg.exe"
```

Enable Message Content Intent in the Discord Developer Portal. Invite the bot
with Connect, Speak, Send Messages, Embed Links, and Read Message History permissions.
Run:

```powershell
uv run main.py
```

Stop an existing bot process before syncing dependencies or starting another copy.

## Docker

Install Docker with Linux container support. The image includes Python 3.13.5,
Node.js 22.18.0, FFmpeg, and locked Python dependencies. It runs as a non-root user.
The build excludes `.env`, local environments, Git data, and tests.

With your token in `.env`, run:

```powershell
docker compose up --build -d
docker compose logs -f bot
```

Compose reads `.env` at runtime and overrides `FFMPEG_PATH` with
`/usr/bin/ffmpeg`, so a Windows path in your local `.env` does not affect the
container. No ports or volumes are required. Do not run the local bot and the
container simultaneously with the same token.

Stop the container:

```powershell
docker compose down
```

Startup verification should show a Discord connection and `MusicCog loaded
successfully.` Real voice playback inside Docker must be tested manually in a
Discord voice channel; a successful startup does not establish audio playback.

## **Bot Commands**

Zixona uses the prefix zix (note the space after zix).

* zix play \<URL or search term\>: Plays a song from YouTube or adds it to the queue. Supports direct URLs and search queries.  
  * Example: zix play despacito  
  * Example: zix play https://www.youtube.com/watch?v=kJQP7kiw5Fk  
  * Example: zix play https://youtube.com/playlist?list=YOUR\_PLAYLIST\_ID  
* zix pause: Pauses the currently playing song.  
* zix resume: Resumes a paused song.  
* zix skip: Skips the current song. If multiple users are in VC, a vote will be initiated.  
* zix stop: Stops playback, clears the entire queue, and disconnects the bot from the voice channel.  
* zix queue: Displays the current music queue with interactive pagination buttons.  
* zix help: Shows this help message with all available commands.

## **Custom Emojis**

Zixona uses custom emojis to enhance its responses. If you wish to use these specific emojis, you will need to upload them to your Discord server and ensure the bot has permission to use external emojis.

* **EMOJI\_PLAYING**: \<a:MusicalHearts:1393976474888966308\>  
* **EMOJI\_PAUSED**: \<:Spotify\_Pause:1393976498179936317\>  
* **EMOJI\_ADDED**: \<:pinkcheckmark:1393976477262807100\>  
* **EMOJI\_SKIPPED**: \<:Skip:1393976495155839099\>  
* **EMOJI\_STOPPED**: ⏹️  
* **EMOJI\_JOINED**: \<:screenshare\_volume\_max:1393976485643030661\>  
* **EMOJI\_DISCONNECTED**: \<:SilverMute:1393976492261769247\>  
* **EMOJI\_ERROR**: \<:pinkcrossmark:1393976480014401586\>  
* **EMOJI\_FETCHING**: \<:SearchCloud:1393976489564700712\>  
* **EMOJI\_QUEUE**: \<:Spotify\_Queue:1393976501090783283\>  
* **EMOJI\_VOTE**: \<:downvote:1393976467196481678\>  
* **EMOJI\_HELP**: \<:pinkquestionmark:1393976483118055475\>  
* **EMOJI\_PLAYLIST**: \<:list:1393976471193784352\>

## **License**

This project is licensed under the MIT License \- see the [LICENSE](https://www.google.com/search?q=LICENSE) file for details.