# Multi-Platform Lead Scraper

A comprehensive local, zero-cost web scraper built in Python that extracts business information directly from Google Maps and Google Search. Includes advanced email enrichment and smart deduplication, powered by an easy-to-use Streamlit UI.

## Capabilities

1. **Multi-Platform Search**: Seamlessly route keyword queries to Google Maps and Google Search.
2. **Bulk Keyword Support**: Paste 10s or 100s of keywords to search automatically.
3. **Data Extraction**: Extracts core business details:
  - Clinic/Business Name
  - Website URL
  - Phone Number
  - Text Snippets/Descriptions from Search Pages
4. **Email Enrichment**: A built-in sub-routine that crawls the collected websites to extract contact emails (looking for mailto: or via regex on `/contact` pages).
5. **Smart Deduplication**: Aggregates all listings into a single view and guarantees no duplicate domains in your final export.
6. **Built-in UI**: Streamlit provides a clean, visual interface to start tasks, review progress, and instantly download a `.csv`.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Walli-Muhammad/google-map-scraper-tool.git
   cd google-map-scraper-tool
   ```

2. Create and activate a Virtual Environment (Optional but recommended):
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```

3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Install the Playwright Chromium browser binary:
   ```bash
   playwright install chromium
   ```

## Usage

Simply launch the Streamlit User Interface:
```bash
python -m streamlit run app.py
```

- **Search Keywords**: Paste your target lookups, e.g. "Restaurants in New York", one per line.
- **Platforms**: Tick Google Maps or Google Search (or both!)
- **Scrolls/Pages**: Customize how deep the Playwright browser probes into the results.
- **Extract Emails**: Turn on an automated background crawl across every found website looking for real contact formulas.

### Important Notes on Google Anti-Bot

When scraping via Google Search, Google tends to trigger CAPTCHA screens ("Our systems have detected unusual traffic from your computer network...").
1. If this occurs in **Background/Headless mode**, the scraper will safely abort and return an empty result list.
2. For maximum success, **uncheck "Run in background (Headless)"** on the frontend UI. When the Playwright browser appears, wait for a CAPTCHA to show, manually click "I am not a robot", and the scraper will auto-resume immediately after.

## Output

Once the processing bar reaches 100%, a robust structured dataset is presented in a table widget and offered as an instant `.csv` download link.# Google Map Scraper Tool

A local, zero-cost web scraper built in Python that extracts business information directly from Google Maps. 

## Features
- **Automated Scrolling**: Navigates to Google Maps and scrolls through the dynamic results pane to load multiple pages of listings.
- **Data Extraction**: Extracts core business details:
  - Clinic/Business Name
  - Website URL
  - Phone Number
  - Email
- **Playwright Powered**: Uses the robust Playwright browser automation library for handling dynamic content and lazily loaded feeds.
- **CSV Export**: Automatically saves the final dataset into a structured CSV file (`ortho_leads.csv`).

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Walli-Muhammad/google-map-scraper-tool.git
   cd google-map-scraper-tool
   ```

2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the Playwright Chromium browser binary:
   ```bash
   playwright install chromium
   ```

## Usage

Simply run the scraper script in your terminal:
```bash
python scraper.py
```

### Configuration
You can customize the search parameters directly at the top of the `scraper.py` file:
- `SEARCH_QUERY`: The specific search term you want to look up on Google Maps (default is `"Orthodontist in Dallas, Texas"`).
- `MAX_SCROLLS`: How many times the script should scroll down the results panel to load more businesses (default is `5`).
- `HEADLESS`: Change to `True` if you prefer the browser to run invisibly in the background.

## Output
The script will cleanly export the scraped name, website, and phone number of each listing into a local file named `ortho_leads.csv`.
