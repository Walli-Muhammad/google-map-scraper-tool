"""
Email Enrichment Scraper
========================
Reads `ortho_leads.csv`, visits each clinic's website, extracts
any email addresses found (via mailto links or body text), and
saves the enriched dataset to `ortho_leads_enriched.csv`.

Install dependencies first:
    pip install requests beautifulsoup4 pandas

Usage:
    python email_scraper.py
"""

import re
import time
import warnings

import pandas as pd
import requests
from bs4 import BeautifulSoup

warnings.filterwarnings("ignore", message="Unverified HTTPS request")  # suppress SSL warnings

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
INPUT_FILE   = "ortho_leads.csv"
OUTPUT_FILE  = "ortho_leads_enriched.csv"

# Sub-paths to try if no email found on the homepage
CONTACT_PATHS = ["/contact", "/contact-us", "/contactus", "/about", "/about-us"]

REQUEST_TIMEOUT  = 8        # seconds per request
DELAY_BETWEEN    = 1.0      # seconds between domains
KEEP_FIRST_ONLY  = True     # set False to keep ALL emails joined by ";"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ─────────────────────────────────────────────
# EMAIL REGEX
# Excludes strings ending with common image extensions
# ─────────────────────────────────────────────
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

_IMAGE_EXT_RE = re.compile(
    r"\.(png|jpg|jpeg|gif|webp|svg|bmp|ico|tiff?)$",
    re.IGNORECASE,
)

# Domains to skip – commonly appear in source code but are never real emails
_JUNK_DOMAINS = {
    "sentry.io", "example.com", "domain.com", "email.com",
    "yourdomain.com", "yoursite.com", "wixpress.com",
}


def is_valid_email(email: str) -> bool:
    """Filter out image-like strings and known junk domains."""
    if _IMAGE_EXT_RE.search(email):
        return False
    domain = email.split("@")[-1].lower()
    if domain in _JUNK_DOMAINS:
        return False
    return True


def extract_emails_from_html(html: str) -> list[str]:
    """
    Extract emails from raw HTML using two strategies:
    1. Parse all mailto: href attributes with BeautifulSoup.
    2. Run the email regex over the raw text content.
    Returns a de-duplicated, filtered list.
    """
    found: set[str] = set()

    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: mailto links
    for tag in soup.find_all("a", href=True):
        href: str = tag["href"]
        if href.lower().startswith("mailto:"):
            addr = href[7:].split("?")[0].strip()
            if addr and is_valid_email(addr):
                found.add(addr.lower())

    # Strategy 2: regex over visible text
    for match in _EMAIL_RE.findall(soup.get_text(" ")):
        if is_valid_email(match):
            found.add(match.lower())

    return list(found)


def fetch_page(url: str) -> str | None:
    """Fetch a URL and return the HTML, or None on failure."""
    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            verify=False,       # ignore SSL cert errors
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"    ⚠ Could not fetch {url}: {type(exc).__name__}")
        return None


def scrape_emails_for_domain(base_url: str) -> str:
    """
    Try the homepage first; if no email found, try common contact sub-paths.
    Returns a formatted email string, or "N/A".
    """
    # Normalise URL
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")

    urls_to_try = [base_url] + [base_url + path for path in CONTACT_PATHS]

    for url in urls_to_try:
        html = fetch_page(url)
        if html is None:
            continue
        emails = extract_emails_from_html(html)
        if emails:
            if KEEP_FIRST_ONLY:
                return emails[0]
            return "; ".join(sorted(emails))

    return "N/A"


def run_email_enrichment(df: pd.DataFrame, on_progress=None) -> pd.DataFrame:
    """
    Takes a DataFrame with a 'Website' column, scrapes an email for each row,
    appends an 'Email' column, and returns the modified DataFrame.
    
    on_progress: Optional callback function that takes (current_index, total_rows, current_name) 
                 to update UI progress.
    """
    total = len(df)
    emails: list[str] = []

    for idx, row in df.iterrows():
        website = str(row.get("Website", "")).strip()
        name    = str(row.get("Name", row.get("Clinic Name", f"Row {idx}"))).strip()

        if on_progress:
            on_progress(idx + 1, total, name)
        else:
            print(f"[{idx + 1}/{total}] {name}")

        if not website or website.lower() in ("n/a", "nan", "none", ""):
            if not on_progress:
                print("    ↳ No website — skipping.")
            emails.append("N/A")
            continue

        email = scrape_emails_for_domain(website)
        if not on_progress:
            print(f"    ↳ Email: {email}")
        emails.append(email)

        time.sleep(DELAY_BETWEEN)

    # ── Save enriched CSV ─────────────────────────────────────────────────
    df["Email"] = emails
    return df

def main() -> None:
    # ── Load CSV ──────────────────────────────────────────────────────────
    try:
        df = pd.read_csv(INPUT_FILE)
    except FileNotFoundError:
        print(f"✗ '{INPUT_FILE}' not found. Make sure it's in the same directory.")
        return

    if "Website" not in df.columns:
        print(f"✗ Expected a 'Website' column in '{INPUT_FILE}'. Aborting.")
        return

    total = len(df)
    print(f"Loaded {total} records from '{INPUT_FILE}'.")
    print("Starting email enrichment…\n")

    # ── Run Enrichment ────────────────────────────────────────────────────
    df = run_email_enrichment(df)
    
    # ── Save enriched CSV ─────────────────────────────────────────────────
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

    found_count = sum(1 for e in df["Email"] if e != "N/A")
    print(f"\n{'='*50}")
    print(f"✅  Done! {found_count}/{total} email(s) found.")
    print(f"    Enriched dataset saved to '{OUTPUT_FILE}'.")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
