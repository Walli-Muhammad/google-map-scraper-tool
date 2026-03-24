import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import streamlit as st
from scraper import run_scraper
from email_scraper import run_email_enrichment

FONT_URL = "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap"

st.set_page_config(
    page_title="Google Maps Scraper",
    page_icon="📍",
    layout="centered",
)

st.markdown(
    f"""
    <style>
    @import url('{FONT_URL}');
    :root {{
        --primary: #0af5c0;
        --accent: #4e8cff;
        --card: rgba(8, 17, 40, 0.85);
        --text: #f4f7ff;
        --muted: rgba(244, 247, 255, 0.6);
        --gradient: linear-gradient(135deg, #030712 0%, #0c1f3a 45%, #082046 100%);
    }}
    body, .stApp {{
        background: var(--gradient);
        color: var(--text);
        font-family: 'Space Grotesk', 'Segoe UI', sans-serif;
    }}
    .stButton>button {{
        background-color: var(--primary);
        color: #03111f;
        border-radius: 999px;
        font-weight: 600;
        border: none;
        padding: 0.65rem 1.5rem;
        transition: transform 0.2s ease;
    }}
    .stButton>button:hover {{
        transform: translateY(-1px);
    }}
    .stSlider>div {{
        color: var(--muted);
    }}
    .form-card {{
        border-radius: 1.5rem;
        padding: 1.25rem;
        background: var(--card);
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 20px 60px rgba(2, 6, 23, 0.6);
    }}
    .hero-banner {{
        background: rgba(10, 15, 40, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 1.25rem;
        padding: 1.5rem;
        margin-bottom: 1rem;
        backdrop-filter: blur(12px);
    }}
    .hero-banner h2 {{
        margin-bottom: 0.5rem;
    }}
    .metric-row .stMetric {{
        background: rgba(255, 255, 255, 0.03);
        border-radius: 1rem;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-banner">
        <p style="color:var(--primary); letter-spacing:0.15em; text-transform:uppercase; font-size:0.85rem; margin-bottom:0.2rem;">Playwright + Streamlit</p>
        <h2>Map + email scraping in one ride</h2>
        <p style="margin:0; color:var(--muted);">Stage every query with purposeful scroll depth, resilient email enrichment, and neatly packaged CSV exports.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.title("📍 Google Maps Lead Scraper")
st.markdown("Extract business leads directly from Google Maps into a clean CSV format.")

with st.form("scraper_form"):
    st.markdown("<div class='form-card'>", unsafe_allow_html=True)
    col_left, col_right = st.columns([2, 1])

    with col_left:
        query = st.text_input(
            "Search Query",
            value="Orthodontist in Dallas, Texas",
            help="What are you looking for and where? (e.g., 'Coffee shops in Seattle')",
        )

        scrolls = st.slider(
            "Scroll Attempts",
            min_value=1,
            max_value=20,
            value=5,
            help="Google Maps loads results dynamically. More scrolls = more results, but takes longer.",
        )

    with col_right:
        headless = st.checkbox(
            "Run in background (Headless)",
            value=True,
            help="If unchecked, you can visually watch the Playwright browser scroll.",
        )

        get_emails = st.checkbox(
            "Extract Emails",
            value=True,
            help="After scraping Maps, automatically visit each website to find contact emails.",
        )

        retry_attempts = st.slider(
            "Email retry attempts",
            min_value=1,
            max_value=5,
            value=3,
            help="How many times the scraper should retry fetching a domain before moving on.",
            disabled=not get_emails,
        )

        extra_paths_input = st.text_input(
            "Additional contact paths",
            placeholder="/team, /staff, /offices",
            help="Comma-separated extra endpoints to try when looking for emails.",
            disabled=not get_emails,
        )

    st.markdown("</div>", unsafe_allow_html=True)
    submitted = st.form_submit_button("Start Scraping", type="primary", use_container_width=True)

if submitted:
    if not query.strip():
        st.error("Please enter a valid search query.")
    else:
        extra_paths = [path.strip() for path in extra_paths_input.split(",") if path.strip()]
        with st.spinner("Scraping in progress... Google Maps is loading your results. Please wait."):
            try:
                df = run_scraper(search_query=query, max_scrolls=scrolls, headless=headless)

                if not df.empty:
                    if get_emails:
                        st.info("Maps scraping done! Now extracting emails...")

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def ui_progress_callback(current, total, name):
                            progress_bar.progress(current / total)
                            status_text.text(f"Checking {name} ({current}/{total})...")

                        df = run_email_enrichment(
                            df,
                            on_progress=ui_progress_callback,
                            retry_attempts=retry_attempts,
                            extra_paths=extra_paths if extra_paths else None,
                        )
                        status_text.text("Email extraction complete!")

                    st.success(f"✅ Successfully scraped {len(df)} leads!")

                    if "Email Status" in df.columns:
                        found = int(df["Email Status"].eq("Found").sum())
                        missing = len(df) - found
                        checked_at = df.get("Email Checked At")
                        last_checked = (
                            checked_at.dropna().max()
                            if checked_at is not None
                            else None
                        )

                        stat_cols = st.columns(3, gap="large")
                        stat_cols[0].metric("Leads scraped", len(df))
                        stat_cols[1].metric("Emails found", found)
                        stat_cols[2].metric(
                            "Emails missing",
                            missing,
                            delta="Headless" if headless else "Visible",
                        )

                        if last_checked:
                            st.caption(f"Last email check at {last_checked} UTC")

                    st.subheader("Data Preview")
                    st.dataframe(df, use_container_width=True)

                    csv_data = df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")

                    st.download_button(
                        label="⬇️ Download CSV",
                        data=csv_data,
                        file_name=f"leads_{query.replace(' ', '_')}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                else:
                    st.warning(
                        "No leads found. Google Maps might have blocked the request, or there are no results for this query."
                    )
            except Exception as exc:
                st.error(f"An error occurred during scraping:\n\n{str(exc)}")
