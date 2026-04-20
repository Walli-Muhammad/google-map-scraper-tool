import sys
import asyncio
import warnings

# Suppress the asyncio deprecation warning in Python 3.16+
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except AttributeError:
            pass

import streamlit as st
import pandas as pd
from scraper import run_scraper
from google_search_scraper import run_google_search_scraper
from email_scraper import run_email_enrichment

st.set_page_config(
    page_title="Google Maps Scraper",
    page_icon="📍",
    layout="centered"
)

st.title("📍 Multi-Platform Lead Scraper")
st.markdown("Extract business leads directly from Google Maps and Google Search into a clean CSV format.")

# ─────────────────────────────────────────────
# INPUT FORM
# ─────────────────────────────────────────────
with st.form("scraper_form"):
    query = st.text_area(
        "Search Keywords (one per line)", 
        value="Orthodontist in Dallas, Texas\nDentists in Austin, Texas",
        help="What are you looking for and where? (e.g., 'Coffee shops in Seattle')",
        height=100
    )
    
    platforms = st.multiselect(
        "Platforms to Scrape",
        ["Google Maps", "Google Search"],
        default=["Google Maps", "Google Search"],
        help="Select which platforms to extract data from."
    )
    
    scrolls = st.slider(
        "Google Maps Scroll Attempts / Google Search Pages", 
        min_value=1, 
        max_value=20, 
        value=5, 
        help="More scrolls or pages = more results, but takes longer."
    )
    
    headless = st.checkbox(
        "Run in background (Headless)", 
        value=True, 
        help="If unchecked, you can visually watch the Playwright browser scroll."
    )

    get_emails = st.checkbox(
        "Extract Emails", 
        value=True, 
        help="After scraping, automatically visit each website to find contact emails."
    )
    
    submitted = st.form_submit_button("Start Scraping", type="primary", use_container_width=True)

# ─────────────────────────────────────────────
# SCRAPING LOGIC & RESULTS
# ─────────────────────────────────────────────
if submitted:
    queries = [q.strip() for q in query.split('\n') if q.strip()]

    if not queries:
        st.error("Please enter at least one valid search query.")
    elif not platforms:
        st.error("Please select at least one platform to scrape.")
    else:
        all_results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        total_tasks = len(queries) * len(platforms)
        current_task = 0

        with st.spinner("Scraping in progress... Please wait."):
            try:
                for idx, q in enumerate(queries):
                    if "Google Maps" in platforms:
                        current_task += 1
                        status_text.text(f"Task {current_task}/{total_tasks}: Scraping '{q}' on Google Maps...")
                        progress_bar.progress(current_task / total_tasks)
                        
                        map_results = run_scraper(search_query=q, max_scrolls=scrolls, headless=headless)
                        if isinstance(map_results, pd.DataFrame):
                            map_results = map_results.to_dict('records')
                        all_results.extend(map_results)
                        
                    if "Google Search" in platforms:
                        current_task += 1
                        status_text.text(f"Task {current_task}/{total_tasks}: Scraping '{q}' on Google Search...")
                        progress_bar.progress(current_task / total_tasks)
                        
                        search_results = run_google_search_scraper(search_query=q, max_pages=min(scrolls, 5), headless=headless)
                        all_results.extend(search_results)
                
                df = pd.DataFrame(all_results)
                
                if not df.empty:
                    # Clean up: Deduplicate using the 'Website' column, dropping rows with 'N/A' or missing websites
                    status_text.text("Deduplicating and cleaning data...")
                    
                    df["Website"] = df["Website"].astype(str).str.strip()
                    df["Website_Lower"] = df["Website"].str.lower()
                    
                    # Sort so that rows with actual websites appear first, then drop duplicates
                    df = df.sort_values(by="Website_Lower", ascending=False)
                    # Keep only the first occurrence of each valid website
                    df_valid_websites = df[(df["Website_Lower"] != "n/a") & (df["Website_Lower"] != "")].drop_duplicates(subset=["Website_Lower"], keep="first")
                    # Keep all rows without a valid website (so we don't dedupe all "N/A"s into just one row)
                    df_no_websites = df[(df["Website_Lower"] == "n/a") | (df["Website_Lower"] == "")]
                    
                    df = pd.concat([df_valid_websites, df_no_websites], ignore_index=True)
                    df = df.drop(columns=["Website_Lower"])
                    
                    if get_emails:
                        st.info("Scraping done! Now extracting emails...")
                        
                        # Reset progress bar for email extraction
                        progress_bar.progress(0)
                        
                        def ui_progress_callback(current, total, name):
                            progress_bar.progress(current / total)
                            status_text.text(f"Checking {name} ({current}/{total})...")
                            
                        # Run the email scraper
                        df = run_email_enrichment(df, on_progress=ui_progress_callback)
                        status_text.text("Email extraction complete!")
                    else:
                        status_text.text("Scraping complete!")
                    
                    st.success(f"✅ Successfully scraped {len(df)} unique leads!")
                    
                    # Preview the data in the UI
                    st.subheader("Data Preview")
                    st.dataframe(df, use_container_width=True)
                    
                    # Format to CSV in memory so the user can download it
                    csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                    
                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv_data,
                        file_name=f"leads_export.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                else:
                    st.warning("No leads found. Platforms might have blocked the request, or there are no results for these queries.")
                    
            except Exception as e:
                st.error(f"An error occurred during scraping:\n\n{str(e)}")
