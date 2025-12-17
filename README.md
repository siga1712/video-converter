# AudioExtract - Video to MP3 Converter

A Flask web application that converts videos to MP3 with metadata editing support.

## Features

- 🔗 Download audio from YouTube, Vimeo, Twitter, TikTok, and 1000+ sites
- 📁 Upload local video/audio files
- ✂️ Trim audio with start/end times
- 🏷️ Edit ID3 tags (Title, Artist, Album, Genre, Year, Track, Comment)
- 🎨 Beautiful dark mode UI

## Local Development

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Visit http://localhost:5000

## Deploy to Render.com (Free)

### Step 1: Push to GitHub

```bash
# Initialize git repo (if not already)
git init
git add .
git commit -m "Initial commit"

# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/video-converter.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Render

1. Go to [render.com](https://render.com) and sign up/login
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account and select your repo
4. Configure:
   - **Name**: `audioextract` (or any name)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Runtime**: `Docker`
   - **Plan**: `Free`
5. Click **"Create Web Service"**

The build will take 5-10 minutes. Once done, you'll get a URL like `https://audioextract.onrender.com`

### Important Notes

- **Free tier spins down** after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- 750 free hours/month (enough for personal use)
- For always-on, upgrade to paid tier ($7/month)

## Tech Stack

- **Backend**: Flask (Python)
- **Audio Processing**: FFmpeg, yt-dlp
- **ID3 Tags**: Mutagen
- **Deployment**: Docker, Gunicorn

## License

MIT
