# TikTok Keyword Scraper v2.0

**🎉 Major Update**: Completely refactored with modular architecture and advanced features!

Search TikTok by keyword and export creator profiles to CSV/Excel with email addresses, follower counts, and enhanced metadata.

## ✨ What's New in v2.0

### 🏗️ **Phase 1: Code Structure Improvements**
- ✅ **Modular Architecture** - Clean separation of concerns
- ✅ **Configuration File Support** - `config.yaml` for default settings
- ✅ **Advanced Logging** - Separate file/console output with rotation
- ✅ **Better Error Handling** - Comprehensive exception management

### 🛡️ **Phase 2: Stability & Anti-Detection**
- ✅ **undetected-chromedriver** - Better bot detection avoidance
- ✅ **Automatic Retry Logic** - Exponential backoff on failures
- ✅ **CAPTCHA Handling** - Manual solving support
- ✅ **Multiple Selector Strategies** - Adapts to page structure changes
- ✅ **Random User-Agent** - Rotates browser fingerprints

### 🚀 **Phase 3: Feature Additions**
- ✅ **Multi-Keyword Support** - Process multiple keywords in one run
- ✅ **Enhanced Data Collection** - Hashtags, descriptions, video stats
- ✅ **Advanced Filtering** - Min followers, min views, email required
- ✅ **Excel Output** - XLSX format support
- ✅ **Incremental Scraping** - Skip existing creators, append mode

### ⚡ **Phase 4: Performance Optimizations**
- ✅ **Parallel Processing** - Multi-threaded profile fetching
- ✅ **Memory Optimization** - Streaming CSV writes
- ✅ **Progress Bars** - Real-time progress with tqdm
- ✅ **Incremental Saves** - Auto-save every 10 profiles

## 📋 Features

- 🔍 Keyword-based video search on TikTok
- 📊 Auto-sort results by view count
- 👤 Extract creator profiles (username, email, followers)
- 📧 Multiple email extraction methods (bio, profile API, page source)
- 📁 CSV/Excel output with comprehensive metadata
- 🍪 Cookie-based authentication
- 🎯 Configurable limits, delays, and filters
- 🔄 Retry logic with exponential backoff
- 🤖 Advanced bot detection avoidance

## 📦 Prerequisites

- Python 3.9+
- Google Chrome browser
- ChromeDriver (auto-installed via webdriver-manager)

## 🚀 Setup

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

See [Manual Cookie Update](#manual-cookie-update) section below.

## 💻 Usage

### Basic Command

```bash
python run_scraper.py -k "K뷰티" -l 50 -o creators.csv
```

### Advanced Examples

**Multi-keyword search:**
```bash
python run_scraper.py -k "kbeauty,skincare,beauty routine" -l 100 -o beauty.csv
```

**With filtering:**
```bash
python run_scraper.py -k "kbeauty" -l 100 \
  --min-followers 10000 \
  --min-views 50000 \
  --email-required \
  -o high_quality.csv
```

**Excel output:**
```bash
python run_scraper.py -k "kbeauty" -l 50 --format xlsx -o creators.xlsx
```

**Parallel processing:**
```bash
python run_scraper.py -k "kbeauty" -l 100 --parallel --max-workers 5
```

**Incremental scraping:**
```bash
python run_scraper.py -k "kbeauty" -l 50 --incremental --skip-existing
```

**Visible browser (for CAPTCHA):**
```bash
python run_scraper.py -k "kbeauty" -l 10 --use-browser
```

### All Command Options

```bash
python run_scraper.py [OPTIONS]

Required:
  -k, --keywords TEXT          Search keywords (comma-separated)

Optional:
  -l, --limit INTEGER          Number of videos to collect (default: 50)
  -o, --output TEXT           Output file path (default: output.csv)
  --format {csv,xlsx}         Output format
  --cookies TEXT              Cookie file path (default: cookies.json)

  --delay-min FLOAT           Minimum delay between requests (default: 1.5s)
  --delay-max FLOAT           Maximum delay between requests (default: 3.0s)

  --use-browser               Run in visible browser mode
  --headless                  Run in headless mode

  --min-followers INT         Minimum follower count filter
  --min-views INT             Minimum view count filter
  --email-required            Only include creators with email

  --incremental               Incremental scraping mode
  --skip-existing             Skip existing creators in output file

  --parallel                  Enable parallel processing
  --max-workers INT           Number of parallel workers (default: 3)

  --config TEXT               Config file path (default: config.yaml)
```

## ⚙️ Configuration File

Create `config.yaml` to set default values:

```yaml
defaults:
  limit: 50
  output_format: csv
  delay_min: 1.5
  delay_max: 3.0
  headless: true
  use_undetected: true

filters:
  min_followers: 1000
  min_views: 0
  email_required: false

performance:
  parallel: false
  max_workers: 3
  cache_enabled: true

logging:
  level: INFO
  console_level: INFO
  file_level: DEBUG
```

CLI arguments always override config file settings.

## 📤 Output Format

### CSV/Excel Columns

| Column | Description |
|--------|-------------|
| `keyword` | Search keyword used |
| `video_id` | TikTok video ID |
| `video_url` | Full URL to the video |
| `creator_id` | Creator's unique ID |
| `creator_username` | Creator's @username |
| `creator_email` | Extracted email address(es) |
| `follower_count` | Number of followers |
| `view_count` | Video view count |
| `like_count` | Video like count |
| `comment_count` | Video comment count |
| `hashtags` | Extracted hashtags (comma-separated) |
| `video_desc` | Video description/caption |
| `posted_date` | Posting date (if available) |
| `source_api` | Data source |
| `extraction_method` | Email extraction method |
| `scraped_at` | Timestamp of scraping |
| `notes` | Additional notes or errors |

## 🔧 Troubleshooting

### No Results Found

If the scraper returns 0 results:

1. **Update cookies** using the manual method below
2. **Try browser mode**: `--use-browser`
3. **Check keywords**: Try different search terms
4. **Wait and retry**: TikTok may temporarily limit your access

### CAPTCHA Issues

When encountering CAPTCHA:

1. Use `--use-browser` flag to run in visible mode
2. Manually solve the CAPTCHA when it appears
3. Press Enter in the terminal to continue

The scraper automatically detects CAPTCHAs and pauses for manual intervention.

### Rate Limiting

If you're being rate-limited:

1. **Increase delays**: `--delay-min 3.0 --delay-max 5.0`
2. **Reduce limit**: Use `-l 20` instead of `-l 100`
3. **Wait**: Take a break for a few hours
4. **Update cookies**: Refresh your authentication

## 🍪 Manual Cookie Update

The scraper requires valid TikTok cookies for authentication.

### Steps:

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
6. Create or update `cookies.json`:

```bash
# macOS/Linux
pbpaste > cookies.json

# Or manually paste into cookies.json
```

7. Run the scraper again

## 📂 Project Structure

```
.
├── tiktok_keyword_scraper/       # Main package
│   ├── __init__.py
│   ├── main.py                   # CLI entry point
│   ├── models.py                 # Data classes
│   ├── scraper.py                # Search scraping
│   ├── profile.py                # Profile extraction
│   ├── email.py                  # Email extraction
│   ├── cookie.py                 # Cookie management
│   ├── config.py                 # Configuration management
│   ├── output.py                 # Output handling
│   ├── logger.py                 # Logging setup
│   └── utils.py                  # Utility functions
├── run_scraper.py                # Entry point script
├── config.yaml                   # Default configuration
├── cookies.json                  # TikTok cookies
├── requirements.txt              # Python dependencies
├── KEYWORD_SCRAPER_GUIDE.md      # Detailed guide
└── README.md                     # This file
```

## 🎯 Keyword Management System (NEW!)

**v2.1 introduces automated keyword tracking and duplicate prevention!**

### Quick Start

```bash
# Check current keywords
python keyword_manager.py

# Smart batch scraping (auto-skip duplicates)
python smart_batch_scraper.py -f keywords.txt -l 200

# Force re-scraping
python smart_batch_scraper.py -f keywords.txt --force
```

### Key Features

- ✅ **Automatic duplicate detection** - Never scrape the same keyword twice
- ✅ **Usage history tracking** - Complete statistics per keyword
- ✅ **Duplicate file consolidation** - Auto-merge similar filenames
- ✅ **Smart batch processing** - Only scrape new keywords

### Documentation

- 📖 **SCRAPING_SOP.md** - Step-by-step guide for all scraping requests
- 📖 **KEYWORD_MANAGEMENT_GUIDE.md** - Detailed keyword system guide
- 📖 **SUMMARY.md** - Project status and statistics

### Current Statistics

```
Total keywords: 22
Total items: 9,790
Average per keyword: 445 items
Success rate: 100%
```

## 📚 Advanced Usage

See `KEYWORD_SCRAPER_GUIDE.md` for detailed documentation including:
- Architecture overview
- Module descriptions
- Advanced configuration
- Performance tuning
- API reference

**NEW:** See `SCRAPING_SOP.md` for Claude Code scraping workflow

## 🔄 Migration from v1.x

**Old command:**
```bash
python tiktok_keyword_scraper.py -k "beauty" -l 5 -o output.csv
```

**New command:**
```bash
python run_scraper.py -k "beauty" -l 5 -o output.csv
```

The old file is backed up as `tiktok_keyword_scraper_old.py`.

## 📝 License

MIT License - see LICENSE file for details

## ⚠️ Disclaimer

This tool is for educational and research purposes only. Please:
- Respect TikTok's Terms of Service
- Use reasonable delays to avoid being blocked
- Keep your cookies file secure and private
- Do not use for spam or harassment

## 🤝 Contributing

Issues and pull requests are welcome!

## 📞 Support

For issues and questions:
- Check `KEYWORD_SCRAPER_GUIDE.md`
- Review troubleshooting section
- Check existing issues on GitHub

---

**v2.0** - Major refactoring with Phase 1-4 improvements
**v1.0** - Initial release
