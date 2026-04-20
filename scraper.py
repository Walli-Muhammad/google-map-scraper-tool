"""
Google Maps Business Scraper
============================
Extracts business listings (Name, Website, Phone) from Google Maps
for a given search query using Playwright (synchronous API).

Usage:
    python scraper.py

Output:
    ortho_leads.csv
"""

import time
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
SEARCH_QUERY = "Orthodontist in Dallas, Texas"
MAX_SCROLLS   = 5          # Number of times to scroll the results pane
OUTPUT_FILE   = "ortho_leads.csv"
HEADLESS      = False      # Set True to run without a visible browser window
SCROLL_PAUSE  = 2.0        # Seconds to wait between each scroll
LOAD_PAUSE    = 3.0        # Seconds to wait after the initial page load


# ─────────────────────────────────────────────
# SELECTORS  (update if Google changes its DOM)
# ─────────────────────────────────────────────
# The scrollable side-panel that contains all result cards
RESULTS_PANEL_SELECTOR = 'div[role="feed"]'

# Individual listing cards inside the panel
LISTING_CARD_SELECTOR  = f'{RESULTS_PANEL_SELECTOR} > div > div > a[href^="https://www.google.com/maps/place"]'

# Selectors used *inside* an open listing detail panel
DETAIL_WEBSITE_SELECTOR = 'a[data-item-id="authority"]'
DETAIL_PHONE_SELECTOR   = 'button[data-item-id^="phone"]'


def scroll_results_panel(page, panel_selector: str, num_scrolls: int, pause: float) -> None:
    """
    Scroll the Google Maps results feed panel to trigger lazy-loading of
    additional listings.
    """
    print(f"  Scrolling results panel {num_scrolls} time(s)…")
    panel = page.query_selector(panel_selector)
    if panel is None:
        print("  ⚠ Results panel not found – skipping scroll.")
        return

    for i in range(1, num_scrolls + 1):
        panel.evaluate("el => el.scrollBy(0, el.scrollHeight)")
        time.sleep(pause)
        print(f"    Scroll {i}/{num_scrolls} complete.")


def extract_listing_details(page) -> dict:
    """
    Extract Website and Phone from the currently open listing detail panel.
    Returns a dict with keys 'website' and 'phone'.
    """
    details = {"website": "N/A", "phone": "N/A"}

    # --- Website ---
    try:
        website_el = page.query_selector(DETAIL_WEBSITE_SELECTOR)
        if website_el:
            href = website_el.get_attribute("href")
            details["website"] = href.strip() if href else "N/A"
    except Exception as exc:
        print(f"    ⚠ Could not extract website: {exc}")

    # --- Phone ---
    try:
        phone_el = page.query_selector(DETAIL_PHONE_SELECTOR)
        if phone_el:
            # The visible text label contains the phone number
            aria = phone_el.get_attribute("aria-label") or ""
            # aria-label typically looks like "Phone: +1 123-456-7890"
            phone_text = aria.replace("Phone:", "").replace("phone:", "").strip()
            details["phone"] = phone_text if phone_text else "N/A"
    except Exception as exc:
        print(f"    ⚠ Could not extract phone: {exc}")

    return details


def run_scraper(search_query: str = SEARCH_QUERY, max_scrolls: int = MAX_SCROLLS, headless: bool = HEADLESS):
    results: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(
            # Mimic a real desktop browser
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = context.new_page()

        # ── 1. Navigate to Google Maps ────────────────────────────────────
        search_url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
        print(f"[1/4] Navigating to Google Maps…\n  URL: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
        time.sleep(LOAD_PAUSE)

        # Dismiss any consent / cookie dialog (EU regions)
        try:
            consent_btn = page.query_selector('button[aria-label="Accept all"]')
            if consent_btn:
                consent_btn.click()
                time.sleep(1)
        except Exception:
            pass

        # ── 2. Wait for results panel & scroll ───────────────────────────
        print(f"\n[2/4] Waiting for results panel to load…")
        try:
            page.wait_for_selector(RESULTS_PANEL_SELECTOR, timeout=20_000)
        except PlaywrightTimeoutError:
            print("  ✗ Results panel did not appear within 20 s. Exiting.")
            browser.close()
            return

        scroll_results_panel(page, RESULTS_PANEL_SELECTOR, max_scrolls, SCROLL_PAUSE)

        # ── 3. Collect listing card links ─────────────────────────────────
        print(f"\n[3/4] Collecting listing cards…")
        cards = page.query_selector_all(LISTING_CARD_SELECTOR)
        print(f"  Found {len(cards)} listing card(s).")

        if not cards:
            print("  ✗ No listing cards found. The page structure may have changed.")
            browser.close()
            return

        # Gather hrefs first so we can navigate into each listing
        listing_hrefs: list[str] = []
        for card in cards:
            href = card.get_attribute("href")
            if href:
                listing_hrefs.append(href)

        print(f"  Collected {len(listing_hrefs)} unique listing URL(s).")

        # ── 4. Visit each listing & extract details ───────────────────────
        print(f"\n[4/4] Extracting details from each listing…")
        for idx, href in enumerate(listing_hrefs, start=1):
            print(f"  [{idx}/{len(listing_hrefs)}] Opening listing…")
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=30_000)
                # Wait for the detail panel to stabilise
                page.wait_for_timeout(2_000)

                # --- Clinic Name ---
                name = "N/A"
                try:
                    name_el = page.query_selector('h1')
                    if name_el:
                        name = name_el.inner_text().strip()
                except Exception as exc:
                    print(f"    ⚠ Could not extract name: {exc}")

                # --- Website & Phone ---
                details = extract_listing_details(page)

                record = {
                    "Platform": "Google Maps",
                    "Keyword": search_query,
                    "Name": name,
                    "Website":     details["website"],
                    "Phone":       details["phone"],
                    "Description": ""
                }
                results.append(record)
                print(f"    ✔ {name} | {details['phone']} | {details['website']}")

                # Polite delay between requests
                time.sleep(1.5)

            except PlaywrightTimeoutError:
                print(f"    ✗ Timeout navigating to listing {idx}. Skipping.")
            except Exception as exc:
                print(f"    ✗ Unexpected error on listing {idx}: {exc}. Skipping.")

        browser.close()

    # ── 5. Return Results ───────────────────────────────────────────────────
    if results:
        print(f"\n✅  Done! {len(results)} record(s) scraped from Google Maps.")
        return results
    else:
        print("\n⚠  No results were collected.")
        return []

if __name__ == "__main__":
    run_scraper()
