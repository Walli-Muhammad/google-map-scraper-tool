import time
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def run_google_search_scraper(search_query: str, max_pages: int = 1, headless: bool = True):
    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US"
        )
        page = context.new_page()

        url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
        print(f"Scraping Google Search for: {search_query}")
        
        for page_num in range(1, max_pages + 1):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as e:
                print(f"Failed to load search results: {e}")
                break

            time.sleep(2)
            
            # Dismiss consent dialog if visible
            try:
                consent_btn = page.query_selector('button[aria-label="Accept all"]')
                if consent_btn:
                    consent_btn.click()
                    time.sleep(1)
            except:
                pass

            # Check if Google threw a CAPTCHA
            if "unusual traffic" in page.content() or "detected unusual traffic" in page.content() or page.title() == "Sorry...":
                print("=====================================================================")
                print("🚨 GOOGLE BLOCKED THE SEARCH (CAPTCHA / Anti-Bot) 🚨")
                print("Google detected the automated browser and blocked the search.")
                if headless:
                    print("--> FIX: Uncheck the 'Run in background (Headless)' box in the UI,")
                    print("         run it again, and manually click/solve the CAPTCHA.")
                else:
                    print("--> ACTION REQUIRED: Please solve the CAPTCHA on the screen now.")
                    print("    Waiting 30 seconds for you to solve it...")
                    try:
                        # Wait for the search results container to appear (meaning CAPTCHA solved)
                        page.wait_for_selector('div#search', timeout=60_000)
                        # Added an explicit wait for the actual results to populate the DOM after CAPTCHA redirects.
                        page.wait_for_timeout(3_000)
                        print("CAPTCHA solved! Continuing...")
                    except PlaywrightTimeoutError:
                        print("Timeout waiting for CAPTCHA to be solved.")
                        break
                print("=====================================================================")
                if headless:
                    break

            # Fallback wait for the results if no CAPTCHA triggered but page is slow
            page.wait_for_timeout(1_000)

            # Extract organic results. Google DOM changes slightly; we accept div.g or div.MjjYud
            search_results = page.query_selector_all('div.g')
            if not search_results:
                 # Sometimes Google wraps the organic hits in alternate div classes
                 search_results = page.query_selector_all('div.MjjYud')
            for result in search_results:
                try:
                    title_el = result.query_selector('h3')
                    link_el = result.query_selector('a')
                    snippet_els = result.query_selector_all('div[data-sncf="1"], div.VwiC3b, span.aCOpRe, div.IsZvec')
                    
                    title = title_el.inner_text().strip() if title_el else ""
                    href = link_el.get_attribute('href') if link_el else ""
                    snippet = " ".join([s.inner_text().strip() for s in snippet_els if s]).strip()

                    # Basic check for a visible phone number in the snippet
                    phone = "N/A"
                    import re
                    # Look for things like +92-300-1234567, 0300 1234 567 formatting
                    phone_match = re.search(r'(?:\+92|0)\s?-?\d{3}\s?-?\d{7}|\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', snippet)
                    if phone_match:
                        phone = phone_match.group(0)

                    if title and href and not href.startswith('/') and "google.com" not in href:
                        results.append({
                            "Platform": "Google Search",
                            "Keyword": search_query,
                            "Name": title,
                            "Website": href,
                            "Phone": phone,
                            "Description": snippet
                        })
                except Exception as ev:
                    pass

            # Go to next page if required and possible
            if page_num < max_pages:
                next_button = page.query_selector('a#pnnext')
                if next_button:
                    url = "https://www.google.com" + next_button.get_attribute("href")
                else:
                    break

        browser.close()

    print(f"✅  Done! {len(results)} record(s) scraped from Google Search.")
    return results

if __name__ == "__main__":
    print(run_google_search_scraper("Orthodontist in Dallas, Texas"))