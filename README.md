# TikTok Keyword Scraper

Search TikTok by keyword and export creator profiles to CSV with email addresses and follower counts.

## Features

- 🔍 Keyword-based video search on TikTok
- 📊 Auto-sort results by view count
- 👤 Extract creator profiles (username, email, followers)
- 📧 Multiple email extraction methods (bio, profile API)
- 📁 CSV output with video links and metadata
- 🍪 Cookie-based authentication
- 🎯 Configurable limits and delays

## Prerequisites

- Python 3.9+
- Google Chrome browser
- ChromeDriver (auto-installed via webdriver-manager)

## Setup

### 1. Create Virtual Environment

**macOS/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```bash
py -3 -m venv .venv
.\.venv\Scripts\activate
```

### 2. Install Dependencies

```bash
python -m pip install -U pip setuptools wheel
pip install -r requirements.txt
```

### 3. Configure Cookies

The scraper requires valid TikTok cookies for authentication.

#### Manual Cookie Update

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

## Usage

### Basic Command

```bash
python tiktok_keyword_scraper.py --keyword "K뷰티" --limit 50 --out creators.csv
```

### Command Options

```bash
python tiktok_keyword_scraper.py [OPTIONS]

Options:
  -k, --keyword TEXT          Search keyword (required)
  -l, --limit INTEGER         Number of videos to collect (default: 50)
  -o, --out TEXT             Output CSV file path (default: creators.csv)
  --delay-min FLOAT          Minimum delay between requests in seconds (default: 1.5)
  --delay-max FLOAT          Maximum delay between requests in seconds (default: 3.0)
  --use-browser              Run in visible browser mode (for debugging)
  --cookies PATH             Path to cookies JSON file (default: cookies.json)
```

### Examples

**Search for K-beauty creators:**
```bash
python tiktok_keyword_scraper.py -k "K뷰티" -l 50 -o kbeauty.csv
```

**Search with custom delays:**
```bash
python tiktok_keyword_scraper.py -k "skincare" -l 100 -o skincare.csv --delay-min 2.0 --delay-max 4.0
```

**Debug mode with visible browser:**
```bash
python tiktok_keyword_scraper.py -k "beauty" -l 10 -o test.csv --use-browser
```

**Short form (using aliases):**
```bash
python tiktok_keyword_scraper.py -k "beauty" -l 5 -o skincare.csv
```

## Output Format

The scraper generates a CSV file with the following columns:

| Column | Description |
|--------|-------------|
| `keyword` | Search keyword used |
| `video_id` | TikTok video ID |
| `video_url` | Full URL to the video |
| `creator_id` | Creator's unique ID |
| `creator_username` | Creator's @username |
| `creator_email` | Extracted email address(es) |
| `follower_count` | Number of followers |
| `source_api` | Data source (e.g., "tiktok_api") |
| `extraction_method` | How email was found (e.g., "bio_text") |
| `scraped_at` | Timestamp of scraping |
| `notes` | Additional notes or errors |

## Workflow

1. **Search Videos**: Searches TikTok for the specified keyword
2. **Sort by Views**: Sorts results by view count (highest first)
3. **Extract Creators**: Visits each creator's profile
4. **Find Emails**: Extracts email addresses from bio and profile data
5. **Export to CSV**: Saves results to CSV file (saves every 10 profiles)

## Troubleshooting

### No Results Found

If the scraper returns 0 results:
1. Update your cookies using the manual method above
2. Try running with `--use-browser` flag to see what's happening
3. Check if TikTok's page structure has changed

### CAPTCHA Issues

If you encounter CAPTCHA:
1. Use `--use-browser` flag to run in visible mode
2. Manually solve the CAPTCHA when it appears
3. Press Enter in the terminal to continue

### Rate Limiting

If you're being rate-limited:
1. Increase delays: `--delay-min 3.0 --delay-max 5.0`
2. Reduce the limit: `-l 20` instead of `-l 100`
3. Wait a few hours before running again

## Advanced Usage

See `KEYWORD_SCRAPER_GUIDE.md` for detailed documentation including:
- Architecture overview
- Profile scraper integration
- Email extraction methods
- Error handling strategies
- Performance optimization tips

## Project Structure

```
.
├── tiktok_keyword_scraper.py      # Main scraper script
├── tiktok-profile-scraper/        # Profile scraping library
├── tiktok-hashtag-scraper/        # Hashtag scraping utilities
├── cookies.json                   # TikTok authentication cookies
├── extract_cookies.py             # Cookie extraction utility
├── test_keyword_scraper.sh        # Test script
├── KEYWORD_SCRAPER_GUIDE.md       # Detailed documentation
└── README.md                      # This file
```

## License

MIT License - see LICENSE file for details

## Notes

- This tool is for educational and research purposes only
- Respect TikTok's Terms of Service and rate limits
- Use reasonable delays to avoid being blocked
- Keep your cookies file secure and private
