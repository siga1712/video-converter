import os
import re
import json
from flask import Flask, render_template, request, send_file, jsonify, session
from werkzeug.utils import secure_filename
import subprocess
import tempfile
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TCON, TRCK, TDRC, COMM, ID3NoHeaderError

app = Flask(__name__)
app.secret_key = 'video-converter-secret-key-2024'

# Configure upload folder - use system temp directory for cleaner handling
UPLOAD_FOLDER = tempfile.gettempdir()

def parse_time_to_seconds(time_str):
    """Convert HH:MM:SS or MM:SS or SS to seconds"""
    if not time_str or time_str.strip() == '':
        return None
    
    time_str = time_str.strip()
    parts = time_str.split(':')
    
    try:
        if len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        else:  # SS
            return float(parts[0])
    except ValueError:
        return None

def format_duration(seconds):
    """Format seconds as HH:MM:SS"""
    if not seconds:
        return "00:00:00"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def sanitize_filename(title):
    """Create a safe filename from video title"""
    # Remove invalid characters
    clean = re.sub(r'[^\w\s-]', '', title)
    clean = re.sub(r'[-\s]+', '_', clean)
    return clean[:50]  # Limit length

def get_video_info(url):
    """Fetch video information without downloading"""
    import yt_dlp
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Try to extract artist from uploader or channel
            artist = info.get('artist', '') or info.get('uploader', '') or info.get('channel', '')
            
            # Try to parse title for artist - title format (common in music videos)
            title = info.get('title', '')
            if ' - ' in title and not info.get('artist'):
                parts = title.split(' - ', 1)
                artist = parts[0].strip()
                title = parts[1].strip()
            
            return {
                'title': title,
                'artist': artist,
                'album': info.get('album', ''),
                'duration': info.get('duration', 0),
                'duration_formatted': format_duration(info.get('duration', 0)),
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', ''),
                'upload_date': info.get('upload_date', ''),
                'year': info.get('upload_date', '')[:4] if info.get('upload_date') else '',
            }
    except Exception as e:
        raise Exception(f"Failed to fetch video info: {str(e)}")

def download_video_audio(url, output_dir):
    """Download audio from any supported site using yt-dlp Python library"""
    import yt_dlp
    
    try:
        # Generate a unique temp filename
        temp_base = os.path.join(output_dir, f"temp_audio_{os.getpid()}")
        
        # Configure yt-dlp options with better settings to avoid blocks
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{temp_base}.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            # Better headers to avoid 403 errors
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
            },
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            },
        }
        
        title = "downloaded_audio"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first to get title
            info = ydl.extract_info(url, download=True)
            if info:
                title = info.get('title', 'downloaded_audio')
        
        # Find the output file
        output_file = f"{temp_base}.mp3"
        if not os.path.exists(output_file):
            # Sometimes the extension differs
            for ext in ['mp3', 'm4a', 'webm', 'opus']:
                check_file = f"{temp_base}.{ext}"
                if os.path.exists(check_file):
                    output_file = check_file
                    break
        
        if not os.path.exists(output_file):
            raise Exception("Download completed but output file not found")
        
        return output_file, sanitize_filename(title)
        
    except Exception as e:
        error_msg = str(e)
        if '403' in error_msg:
            raise Exception("YouTube is blocking the download. Try a different video or try again later.")
        raise Exception(f"Download failed: {error_msg}")

def add_id3_tags(mp3_path, title=None, artist=None, album=None, genre=None, track=None, year=None, comment=None):
    """Add ID3 tags to MP3 file"""
    try:
        # Try to load existing tags
        try:
            audio = MP3(mp3_path, ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
        except ID3NoHeaderError:
            audio = MP3(mp3_path)
            audio.add_tags()
        
        tags = audio.tags
        
        if title:
            tags.add(TIT2(encoding=3, text=title))
        if artist:
            tags.add(TPE1(encoding=3, text=artist))
        if album:
            tags.add(TALB(encoding=3, text=album))
        if genre:
            tags.add(TCON(encoding=3, text=genre))
        if track:
            tags.add(TRCK(encoding=3, text=str(track)))
        if year:
            tags.add(TDRC(encoding=3, text=str(year)))
        if comment:
            tags.add(COMM(encoding=3, lang='eng', desc='', text=comment))
        
        audio.save()
        return True
    except Exception as e:
        print(f"Error adding ID3 tags: {e}")
        return False

def convert_to_mp3_ffmpeg(input_path, output_path, start_time=None, end_time=None):
    """Convert audio/video to MP3 with optional trimming using ffmpeg"""
    cmd = ['ffmpeg', '-y', '-i', input_path]
    
    # Add trimming options
    if start_time is not None:
        cmd.extend(['-ss', str(start_time)])
    if end_time is not None:
        if start_time is not None:
            # Duration instead of end time
            duration = end_time - start_time
            cmd.extend(['-t', str(duration)])
        else:
            cmd.extend(['-to', str(end_time)])
    
    # Output options - extract audio, convert to mp3
    cmd.extend(['-vn', '-acodec', 'libmp3lame', '-q:a', '2', output_path])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    
    if result.returncode != 0:
        raise Exception(f"Conversion failed: {result.stderr}")
    
    return True

def convert_to_mp3_moviepy(input_path, output_path, start_time=None, end_time=None):
    """Fallback conversion using moviepy for video files"""
    from moviepy import VideoFileClip
    
    clip = VideoFileClip(input_path)
    audio = clip.audio
    
    if audio is None:
        raise Exception("No audio track found in video")
    
    # Apply trimming if specified
    if start_time is not None or end_time is not None:
        start = start_time if start_time is not None else 0
        end = end_time if end_time is not None else audio.duration
        
        # Ensure valid range
        start = max(0, min(start, audio.duration))
        end = max(start, min(end, audio.duration))
        
        audio = audio.subclipped(start, end)
    
    audio.write_audiofile(output_path)
    audio.close()
    clip.close()
    
    return True

def convert_to_mp3(input_path, output_path, start_time=None, end_time=None):
    """Convert to MP3, trying ffmpeg first, then moviepy"""
    try:
        return convert_to_mp3_ffmpeg(input_path, output_path, start_time, end_time)
    except FileNotFoundError:
        # ffmpeg not installed, try moviepy
        return convert_to_mp3_moviepy(input_path, output_path, start_time, end_time)
    except Exception as e:
        # ffmpeg failed, try moviepy as fallback
        try:
            return convert_to_mp3_moviepy(input_path, output_path, start_time, end_time)
        except:
            # If moviepy also fails, raise original error
            raise e

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/fetch-info', methods=['POST'])
def fetch_info():
    """Fetch video info for metadata editing"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please enter a video URL'}), 400
        
        info = get_video_info(url)
        return jsonify(info)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/convert', methods=['POST'])
def convert():
    """Convert video to MP3 with metadata"""
    temp_file = None
    audio_path = None
    
    try:
        input_type = request.form.get('input_type', 'file')
        start_time = parse_time_to_seconds(request.form.get('start_time', ''))
        end_time = parse_time_to_seconds(request.form.get('end_time', ''))
        
        # Metadata fields
        meta_title = request.form.get('meta_title', '').strip()
        meta_artist = request.form.get('meta_artist', '').strip()
        meta_album = request.form.get('meta_album', '').strip()
        meta_genre = request.form.get('meta_genre', '').strip()
        meta_track = request.form.get('meta_track', '').strip()
        meta_year = request.form.get('meta_year', '').strip()
        meta_comment = request.form.get('meta_comment', '').strip()
        
        if input_type == 'url':
            # Handle URL input
            video_url = request.form.get('video_url', '').strip()
            
            if not video_url:
                return jsonify({'error': 'Please enter a video URL'}), 400
            
            # Download and convert using yt-dlp
            temp_file, title = download_video_audio(video_url, UPLOAD_FOLDER)
            
            # Use metadata title for filename if provided
            if meta_title:
                title = sanitize_filename(meta_title)
            
            # If trimming is needed, process with ffmpeg
            if start_time is not None or end_time is not None:
                audio_path = os.path.join(UPLOAD_FOLDER, f"{title}_trimmed.mp3")
                convert_to_mp3(temp_file, audio_path, start_time, end_time)
            else:
                audio_path = temp_file
                temp_file = None  # Don't delete since we're using it directly
            
            download_filename = f"{title}.mp3"
            
        else:
            # Handle file upload
            video_file = request.files.get('video')
            
            if not video_file or video_file.filename == '':
                return jsonify({'error': 'Please select a video file'}), 400
            
            filename = secure_filename(video_file.filename)
            temp_file = os.path.join(UPLOAD_FOLDER, filename)
            video_file.save(temp_file)
            base_name = os.path.splitext(filename)[0]
            
            # Use metadata title for filename if provided
            if meta_title:
                base_name = sanitize_filename(meta_title)
            
            # Define output path
            audio_path = os.path.join(UPLOAD_FOLDER, f"{base_name}.mp3")
            
            # Convert to MP3 with optional trimming
            convert_to_mp3(temp_file, audio_path, start_time, end_time)
            
            download_filename = f"{base_name}.mp3"
        
        # Add ID3 tags if any metadata provided
        if any([meta_title, meta_artist, meta_album, meta_genre, meta_track, meta_year, meta_comment]):
            add_id3_tags(
                audio_path,
                title=meta_title,
                artist=meta_artist,
                album=meta_album,
                genre=meta_genre,
                track=meta_track,
                year=meta_year,
                comment=meta_comment
            )
        
        # Send the file to user with proper filename
        return send_file(
            audio_path, 
            as_attachment=True, 
            download_name=download_filename,
            mimetype='audio/mpeg'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    
    finally:
        # Cleanup temp files
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

if __name__ == '__main__':
    app.run(debug=True)
