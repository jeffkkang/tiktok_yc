# TikTok Analyzer — Quick Start

A minimal pipeline to fetch TikTok metadata, download the video, optionally scrape comments, and transcribe audio.

## Prerequisites
- Python 3.9+
- FFmpeg installed and on PATH
  - macOS: `brew install ffmpeg`
  - Windows (PowerShell/Admin): `choco install ffmpeg` or use the official build
  - Linux: `apt-get install ffmpeg` (or your distro’s package manager)

## Setup (Virtual Environment)
- macOS/Linux:
  - `python3 -m venv .venv`
  - `source .venv/bin/activate`
- Windows (PowerShell):
  - `py -3 -m venv .venv`
  - `.\.venv\Scripts\activate`

Upgrade pip and install dependencies:
- `python -m pip install -U pip setuptools wheel`
- Core deps:
  - `pip install -r requirements.txt`
- Transcription (optional, disabled by default):
  - If you want Whisper/Google STT features, additionally install:
    - Whisper + PyTorch: `pip install openai-whisper` and follow PyTorch install guidance for your platform
    - Google STT: `pip install SpeechRecognition`
- Third‑party comment scraper deps (optional, used when `--comments`):
  - `pip install -r thirdparty/tiktok-comment-scrapper/requirements.txt`

## Basic Commands
- Quick all‑in‑one run (metadata + comments + download + transcription):
  - `python -m src.default_runner "https://www.tiktok.com/@USER/video/VIDEO_ID"`

- Full pipeline with options:
  - `python -m src.pipeline --url "https://www.tiktok.com/@USER/video/VIDEO_ID" --comments`
  - Only analyze local MP4: `python -m src.pipeline --mp4 path/to/video.mp4 --transcribe`
  - Audio only (MP3 extract): `python -m src.pipeline --url "..." --extract-audio-only`
  - Skip metadata: `python -m src.pipeline --url "..." --skip-metadata`

## Metadata Only
- Save fast metadata summary to the run folder:
  - `python -m src.scrapers.tiktok_video_metadata_scraper "https://www.tiktok.com/@USER/video/VIDEO_ID"`
- Read quick fields (loads `<base>_summary.json` if present):
  - `python -m src.utils.meta_summary runs/<created_folder>/@USER_video_VIDEO_ID_metadata.json`

## Comments Only
- Run bundled third‑party scraper and normalize outputs to `runs/...`:
  - `python -m src.scrapers.thirdparty_tpcs_runner "https://www.tiktok.com/@USER/video/VIDEO_ID" --out runs/<created_folder> --size 500`
- Normalize an existing JSON/CSV/XLSX of comments:
  - `python -m src.scrapers.comments_ingest thirdparty.json --url "..." --out runs/<created_folder>`

## Transcription (Optional)
- Disabled by default. To enable, install the optional deps above and run:
  - Whisper: `python -m src.transcribers.tiktok_video_to_text path/to/video.mp4 -m openai`
  - Google STT: `python -m src.transcribers.tiktok_video_to_text path/to/video.mp4 -m google`

## Outputs
- Run directory: `runs/<uploader>_<videoId>_<YYYYMMDD_HHMMSS>/`
  - Video file (from `yt-dlp`): `<uploader>_<id>.mp4`
  - Metadata summary: `@USER_video_VIDEO_ID_metadata_summary.json`
  - Comments (when enabled): `<base>_comments.json` and `<base>_comments.jsonl`
  - Transcription (when enabled): `<base>.json` with `{"text": ...}`

## Keyword Search → Creator Profile Exporter (NEW)

**NEW**: Search TikTok by keyword and export creator profiles to CSV!

```bash
# Search by keyword and collect creator profiles
python tiktok_keyword_scraper.py --keyword "K뷰티" --limit 50 --out creators.csv

# With browser mode (for CAPTCHA)
python tiktok_keyword_scraper.py --keyword "skincare routine" --limit 100 --out skincare.csv --use-browser
```

**Features**:
- Keyword-based video search
- Auto-sort by view count
- Extract creator profiles (email, followers)
- CSV output with video links
- Reuses existing `tiktok-profile-scraper` code

**Documentation**: See `KEYWORD_SCRAPER_GUIDE.md` for full details.

### Manual Cookie Update

If the scraper is not finding results, you may need to update cookies manually:

1. Open TikTok in your browser (Chrome/Edge) and log in
2. Open Developer Console (F12 or Cmd+Option+I)
3. Go to the **Console** tab
4. Paste and run this code:

```javascript
copy(JSON.stringify(document.cookie.split('; ').map(c => {
  const [name, ...valueParts] = c.split('=');
  return {
    name: name,
    value: valueParts.join('='),
    domain: '.tiktok.com',
    path: '/',
    secure: true,
    httpOnly: false
  };
}), null, 2));
```

5. The cookies are now copied to your clipboard
6. Create or update `cookies.json` in the project root:

```bash
# Paste the clipboard contents into cookies.json
pbpaste > cookies.json  # macOS
# or manually create cookies.json and paste the content
```

7. Run the scraper again with the updated cookies

## Notes & Tips
- URL format: This repo expects `https://www.tiktok.com/@USER/video/VIDEO_ID`. Other forms may still work, but the run folder name may fall back to `tiktok_run_<timestamp>`.
- Update `yt-dlp` if downloads fail: `pip install -U yt-dlp`
- FFmpeg is required for audio extraction and Whisper; ensure `ffmpeg` is on PATH.
- Whisper CPU can be slow; consider GPU if you enable it.
