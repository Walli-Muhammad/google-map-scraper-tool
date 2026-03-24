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
from datetime import datetime
from typing import Sequence

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

warnings.filterwarnings("ignore", message="Unverified HTTPS request")  # suppress SSL warnings

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
INPUT_FILE   = "ortho_leads.csv"
OUTPUT_FILE  = "ortho_leads_enriched.csv"

# Sub-paths to try if no email found on the homepage
CONTACT_PATHS = [
    "/contact",
    "/contact-us",
    "/contactus",
    "/about",
    "/about-us",
    "/team",
    "/team-us",
    "/staff",
    "/offices",
]

REQUEST_TIMEOUT  = 8        # seconds per request
DELAY_BETWEEN    = 1.0      # seconds between domains
KEEP_FIRST_ONLY  = True     # set False to keep ALL emails joined by ";"
RETRY_TOTAL      = 3        # HTTP retries per domain
RETRY_BACKOFF    = 0.8      # seconds multiplier for retries
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def build_session(retry_attempts: int) -> requests.Session:
    """Create a requests session with retries for transient HTTP failures."""
    retry_strategy = Retry(
        total=retry_attempts,
        backoff_factor=RETRY_BACKOFF,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=["GET", "HEAD"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.headers.update(HEADERS)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

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


def fetch_page(session: requests.Session, url: str) -> str | None:
    """Fetch a URL through the provided session and return the HTML."""
    try:
        resp = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            verify=False,
            allow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"    ⚠ Could not fetch {url}: {type(exc).__name__}")
        return None


def scrape_emails_for_domain(
    base_url: str,
    session: requests.Session,
    extra_paths: Sequence[str] | None = None,
) -> tuple[str, str]:
    """
    Try the homepage plus fallback paths and return the first email plus the source path.
    """
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url
    base_url = base_url.rstrip("/")

    normalized_paths = CONTACT_PATHS.copy()
    if extra_paths:
        for path in extra_paths:
            clean = path.strip()
            if not clean:
                continue
            if not clean.startswith("/"):
                clean = "/" + clean
            normalized_paths.append(clean)

    urls_to_try = [base_url] + [f"{base_url}{path}" for path in normalized_paths]

    for url in urls_to_try:
        html = fetch_page(session, url)
        if html is None:
            continue
        emails = extract_emails_from_html(html)
        if emails:
            chosen = emails[0] if KEEP_FIRST_ONLY else "; ".join(sorted(emails))
            relative_path = url[len(base_url) :] or "/"
            source_label = relative_path if relative_path else "/"
            return chosen, source_label

    return "N/A", "not-found"


def run_email_enrichment(
    df: pd.DataFrame,
    on_progress=None,
    retry_attempts: int = RETRY_TOTAL,
    extra_paths: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Scrape emails for each row and append richness columns to the DataFrame."""

    total = len(df)
    emails: list[str] = []
    sources: list[str] = []
    statuses: list[str] = []
    checked_at: list[str] = []

    session = build_session(retry_attempts)
    try:
        for idx, row in df.iterrows():
            website = str(row.get("Website", "")).strip()
            name = str(row.get("Clinic Name", f"Row {idx}")).strip()
            timestamp = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

            if on_progress:
                on_progress(idx + 1, total, name)
            else:
                print(f"[{idx + 1}/{total}] {name}")

            if not website or website.lower() in ("n/a", "nan", "none", ""):
                if not on_progress:
                    print("    ↳ No website — skipping.")
                emails.append("N/A")
                sources.append("no-website")
                statuses.append("Missing")
                checked_at.append(timestamp)
                time.sleep(DELAY_BETWEEN)
                continue

            email, source = scrape_emails_for_domain(website, session, extra_paths)
            status = "Found" if email != "N/A" else "Missing"
            if not on_progress:
                print(f"    ↳ Email: {email} ({source})")

            emails.append(email)
            sources.append(source)
            statuses.append(status)
            checked_at.append(timestamp)

            time.sleep(DELAY_BETWEEN)
    finally:
        session.close()

    df["Email"] = emails
    df["Email Source"] = sources
    df["Email Status"] = statuses
    df["Email Checked At"] = checked_at
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
