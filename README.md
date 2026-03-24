# Google Map Scraper Tool

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
