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

## **Setup and Installation**

Follow these steps to get Zixona running on your server.

### **Prerequisites**

Before you begin, ensure you have the following installed:

* **Python 3.8+**: [Download Python](https://www.python.org/downloads/)  
* **FFmpeg**: This is crucial for audio processing.  
  * **Windows**: [Download from here](https://www.google.com/search?q=https://ffmpeg.org/download.html%23build-windows). Extract it and add the bin folder to your system's PATH, or note its full path for the .env file.  
  * **Linux/macOS**: Install via your package manager (e.g., sudo apt install ffmpeg on Debian/Ubuntu, brew install ffmpeg on macOS).  
* **Discord Bot Token**: Create a bot application and get your token from the [Discord Developer Portal](https://discord.com/developers/applications). Make sure to enable the Message Content Intent and Voice States in your bot's settings.  
* **Bot Permissions**: Invite your bot to your server with necessary permissions (e.g., Connect, Speak, Send Messages, Read Message History).

### **Installation Steps**

1. **Clone the Repository:**  
   git clone https://github.com/your-username/zixona-bot.git  
   cd zixona-bot

   *(Replace your-username/zixona-bot.git with your actual repository URL once created)*  
2. **Create a Virtual Environment (Recommended):**  
   python \-m venv venv  
   \# On Windows:  
   .\\venv\\Scripts\\activate  
   \# On macOS/Linux:  
   source venv/bin/activate

3. **Install Dependencies:**  
   pip install \-r requirements.txt

   If you don't have a requirements.txt yet, create one with these contents:  
   discord.py\[voice\]  
   yt-dlp  
   python-dotenv

4. Create .env File:  
   In the root directory of your bot (zixona-bot/), create a file named .env and add your bot token and FFmpeg path:  
   DISCORD\_BOT\_TOKEN="YOUR\_DISCORD\_BOT\_TOKEN\_HERE"  
   FFMPEG\_PATH="C:/path/to/ffmpeg/bin/ffmpeg.exe" \# Example for Windows, adjust for your OS  
   \# For Linux/macOS, if ffmpeg is in your PATH, you can often leave this empty or set to just "ffmpeg"  
   \# FFMPEG\_PATH="ffmpeg"

   Replace YOUR\_DISCORD\_BOT\_TOKEN\_HERE with your actual bot token.  
   Adjust FFMPEG\_PATH to the correct path for your FFmpeg executable. If FFmpeg is in your system's PATH, you might not need to specify the full path, but it's safer to do so.  
5. **Run the Bot:**  
   python main.py

   Your bot should now come online in your Discord server\!

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