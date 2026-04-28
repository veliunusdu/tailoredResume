import streamlit as st
import pandas as pd
import altair as alt
from app.agent import get_jobs

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="ApplyPilot Dashboard",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- PREMIUM STYLING ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Outfit:wght@500;700;800&display=swap');

    :root {
        --primary: #6366f1;
        --secondary: #a855f7;
        --success: #10b981;
        --warning: #f59e0b;
        --danger: #ef4444;
        --bg: #030712;
        --surface: #111827;
        --surface-light: #1f2937;
        --text: #f8fafc;
        --text-muted: #94a3b8;
    }

    .stApp {
        background-color: var(--bg);
        color: var(--text);
        font-family: 'Inter', sans-serif;
    }

    /* Gradient Titles */
    .main-title {
        font-family: 'Outfit', sans-serif;
        background: linear-gradient(to right, #818cf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem;
        font-weight: 800;
        margin-bottom: 0.5rem;
    }

    /* Glassmorphism Cards */
    div[data-testid="column"] {
        background: rgba(31, 41, 55, 0.4);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 24px;
        border-radius: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }

    /* Metrics Styling */
    [data-testid="stMetricValue"] {
        font-family: 'Outfit', sans-serif;
        font-size: 2.8rem !important;
        font-weight: 700 !important;
        color: var(--text) !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--text-muted) !important;
        font-size: 1rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Job Card / Expander */
    div[data-testid="stExpander"] {
        background: rgba(17, 24, 39, 0.7) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
    }
    div[data-testid="stExpander"]:hover {
        border-color: rgba(99, 102, 241, 0.4) !important;
        background: rgba(17, 24, 39, 0.9) !important;
    }

    /* Custom Tags */
    .badge {
        padding: 4px 12px;
        border-radius: 99px;
        font-weight: 600;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
        display: inline-flex;
        align-items: center;
        margin-right: 8px;
    }
    .badge-primary { background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.2); }
    .badge-success { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.2); }
    .badge-warning { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.2); }

    /* Score Indicator */
    .score-circle {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-family: 'Outfit', sans-serif;
        font-size: 1.2rem;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #030712 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.2rem !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.3);
    }

    /* Info boxes */
    .stAlert {
        border-radius: 16px !important;
        background-color: rgba(31, 41, 55, 0.6) !important;
        border: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SESSION STATE ---
if 'all_jobs' not in st.session_state:
    st.session_state.all_jobs = []
if 'last_run' not in st.session_state:
    st.session_state.last_run = False

# --- PIPELINE LOGIC ---
def run_pipeline():
    with st.spinner("✨ Running AI Engine..."):
        try:
            strong, maybe = get_jobs()
            st.session_state.all_jobs = strong + maybe
            st.session_state.last_run = True
        except Exception as e:
            st.error(f"Pipeline failed: {e}")

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h1 style='font-family:Outfit; font-weight:800; font-size:2rem; margin-bottom:0'>ApplyPilot</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94a3b8; font-size:0.9rem; margin-bottom:2rem'>Your Career Co-Pilot</p>", unsafe_allow_html=True)
    
    if st.button("🚀 INITIATE ANALYSIS", use_container_width=True, type="primary"):
        run_pipeline()
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("Filter Suite")
    min_score = st.select_slider("Minimum Fit Score", options=list(range(11)), value=5)
    search_query = st.text_input("Keywords", placeholder="Title, Tech, Location...")
    
    available_sites = ["All Sources"]
    if st.session_state.all_jobs:
        available_sites += sorted(list(set(j.get('site', 'Unknown') for j in st.session_state.all_jobs)))
    selected_site = st.selectbox("Market Source", available_sites)

# --- HERO SECTION ---
st.markdown("<h1 class='main-title'>Job Market Pulse</h1>", unsafe_allow_html=True)

if not st.session_state.last_run:
    st.markdown("""
    <div style="background: rgba(99, 102, 241, 0.05); padding: 60px; border-radius: 30px; border: 1px dashed rgba(99, 102, 241, 0.2); text-align: center; margin-top: 40px;">
        <h2 style="font-family:Outfit; margin-bottom: 15px;">Ready to find your match?</h2>
        <p style="color: #94a3b8; font-size: 1.1rem; max-width: 500px; margin: 0 auto 30px;">ApplyPilot uses advanced LLMs to analyze 20+ job sources simultaneously against your unique profile.</p>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# --- KEY PERFORMANCE INDICATORS ---
all_jobs = st.session_state.all_jobs
strong_jobs = [j for j in all_jobs if j.get('score', 0) >= 7]

kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("ANALYZED", len(all_jobs))
kpi2.metric("HIGH MATCH", len(strong_jobs))
avg_s = round(sum(j.get('score', 0) for j in all_jobs) / max(len(all_jobs), 1), 1)
kpi3.metric("AVG FIT", f"{avg_s}/10")

st.markdown("<br>", unsafe_allow_html=True)

# --- DATA VISUALIZATION ---
chart_col, table_col = st.columns([2, 1])

with chart_col:
    st.subheader("Fit Distribution")
    df = pd.DataFrame([j.get('score', 0) for j in all_jobs], columns=['score'])
    score_counts = df['score'].value_counts().reset_index()
    score_counts.columns = ['score', 'count']
    
    chart = alt.Chart(score_counts).mark_bar(
        cornerRadiusTopLeft=8, cornerRadiusTopRight=8, size=35
    ).encode(
        x=alt.X('score:O', title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y('count:Q', title=None),
        color=alt.condition(
            alt.datum.score >= 7,
            alt.value('#10b981'),
            alt.value('#6366f1')
        ),
        tooltip=['score', 'count']
    ).configure_view(strokeWidth=0).properties(height=250)
    st.altair_chart(chart, use_container_width=True)

with table_col:
    st.subheader("Source Breakdown")
    site_df = pd.DataFrame([j.get('site', 'Unknown') for j in all_jobs], columns=['Source'])
    top_sources = site_df['Source'].value_counts().reset_index()
    top_sources.columns = ['Source', 'Count']
    st.dataframe(top_sources, use_container_width=True, hide_index=True)

st.markdown("---")

# --- RESULTS ENGINE ---
filtered = [
    j for j in all_jobs 
    if j.get('score', 0) >= min_score
    and (search_query.lower() in j.get('title', '').lower() or 
         search_query.lower() in j.get('company', '').lower())
    and (selected_site == "All Sources" or j.get('site') == selected_site)
]

st.markdown(f"<h3 style='margin-bottom:1.5rem'>Found {len(filtered)} matches for you</h3>", unsafe_allow_html=True)

if not filtered:
    st.warning("No matches found for current filters.")
else:
    # Grouping logic
    scores = sorted(list(set(j.get('score', 0) for j in filtered)), reverse=True)
    
    for score in scores:
        group = [j for j in filtered if j.get('score', 0) == score]
        
        # Color logic
        s_color = "#10b981" if score >= 8 else ("#6366f1" if score >= 6 else "#f59e0b")
        s_bg = f"{s_color}22"
        
        st.markdown(f"""
            <div style="display:flex; align-items:center; gap:12px; margin: 2rem 0 1rem 0">
                <div class="score-circle" style="background:{s_color}; color:#030712">{score}</div>
                <h3 style="margin:0; font-family:Outfit">{ 'Elite' if score >= 9 else ('Strong' if score >= 7 else 'Potential') } Match Pool</h3>
                <span style="color:#94a3b8; font-size:0.9rem">({len(group)} items)</span>
            </div>
        """, unsafe_allow_html=True)
        
        for job in group:
            with st.expander(f"**{job['title']}** @ {job.get('company', 'Unknown')}"):
                c_main, c_side = st.columns([4, 1])
                
                with c_main:
                    # Metadata row
                    meta_html = f"""
                        <div style="margin-bottom:15px">
                            <span class="badge badge-primary">{job.get('site', 'Web')}</span>
                            <span class="badge badge-success">{job.get('salary') or 'Competitive'}</span>
                            <span class="badge badge-warning">{job.get('location') or 'Remote'}</span>
                        </div>
                    """
                    st.markdown(meta_html, unsafe_allow_html=True)
                    
                    st.markdown(f"<p style='color:#cbd5e1; line-height:1.6'><b>AI Insight:</b> {job.get('reason', 'N/A')}</p>", unsafe_allow_html=True)
                    
                    if job.get('description'):
                        with st.container():
                            st.markdown("<p style='color:#64748b; font-size:0.85rem'>Preview:</p>", unsafe_allow_html=True)
                            st.write(job['description'][:350] + "...")
                
                with c_side:
                    st.link_button("View Job", job.get('url', '#'), use_container_width=True)
                    st.markdown(f"<p style='text-align:center; margin-top:15px; font-weight:800; font-size:1.1rem; color:{s_color}'>{score}/10</p>", unsafe_allow_html=True)
                    st.progress(score / 10)

