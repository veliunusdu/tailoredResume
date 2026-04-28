import streamlit as st
import pandas as pd
import altair as alt
from app.db import get_all_scored_jobs
from app.config import DATA_DIR

# ── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="TailoredResume",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { box-sizing: border-box; }

html, body, .stApp {
    background: #0a0a0f;
    color: #e2e8f0;
    font-family: 'Inter', sans-serif;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, header, footer { visibility: hidden; }
.block-container { padding: 2rem 3rem; max-width: 1400px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0f0f1a;
    border-right: 1px solid #1e1e2e;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #111120;
    border: 1px solid #1e1e2e;
    border-radius: 12px;
    padding: 1.5rem !important;
}
[data-testid="stMetricValue"] {
    font-size: 2.4rem !important;
    font-weight: 700 !important;
    color: #ffffff !important;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    color: #64748b !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
[data-testid="stMetricDelta"] { font-size: 0.85rem !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid #1e1e2e;
    gap: 0;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    border: none;
    color: #64748b;
    font-size: 0.875rem;
    font-weight: 500;
    padding: 0.75rem 1.5rem;
    border-radius: 0;
}
.stTabs [aria-selected="true"] {
    color: #ffffff !important;
    border-bottom: 2px solid #6366f1 !important;
    background: transparent !important;
}

/* ── Expanders (job cards) ── */
div[data-testid="stExpander"] {
    background: #111120 !important;
    border: 1px solid #1e1e2e !important;
    border-radius: 10px !important;
    margin-bottom: 10px !important;
}
div[data-testid="stExpander"]:hover {
    border-color: #6366f1 !important;
}
.st-expander-content { padding: 1rem 1.5rem; }

/* ── Buttons ── */
.stLinkButton a {
    background: #6366f1 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-size: 0.8rem !important;
    padding: 0.4rem 1rem !important;
    font-weight: 600 !important;
}
.stLinkButton a:hover { background: #4f46e5 !important; }

/* ── Score pill ── */
.score-pill {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 99px;
    font-size: 0.75rem;
    font-weight: 700;
    margin-right: 8px;
}
.score-high   { background: #14532d; color: #4ade80; }
.score-mid    { background: #1e1b4b; color: #a5b4fc; }
.score-low    { background: #451a03; color: #fbbf24; }

/* ── Tag pill ── */
.tag {
    display: inline-block;
    background: #1e1e2e;
    color: #94a3b8;
    border-radius: 6px;
    padding: 2px 10px;
    font-size: 0.72rem;
    font-weight: 500;
    margin: 2px;
    border: 1px solid #2d2d45;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ── Divider ── */
hr { border-color: #1e1e2e; }

/* ── Altair chart bg ── */
.vega-embed { background: transparent !important; }
</style>
""", unsafe_allow_html=True)


# ── Data ─────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_data():
    try:
        return get_all_scored_jobs()
    except Exception as e:
        st.error(f"Database error: {e}")
        return []

all_jobs = load_data()


# ── Header ───────────────────────────────────────────────────────────────────
col_logo, col_actions = st.columns([1, 1])
with col_logo:
    st.markdown("""
    <div style="display:flex; align-items:center; gap:12px; margin-bottom:0.5rem">
        <span style="font-size:1.8rem">🎯</span>
        <div>
            <h1 style="margin:0; font-size:1.4rem; font-weight:700; color:#fff">TailoredResume</h1>
            <p style="margin:0; font-size:0.78rem; color:#64748b">Autonomous Job Discovery & Scoring Engine</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
with col_actions:
    st.markdown("""
    <div style="text-align:right; padding-top:0.5rem">
        <code style="background:#1e1e2e; color:#a5b4fc; padding:6px 14px; border-radius:8px; font-size:0.8rem">
            .venv/Scripts/python.exe main.py run
        </code>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin:0.75rem 0 1.5rem 0'>", unsafe_allow_html=True)


# ── KPI Row ──────────────────────────────────────────────────────────────────
if all_jobs:
    strong = [j for j in all_jobs if j.get("score", 0) >= 7]
    maybe  = [j for j in all_jobs if 4 <= j.get("score", 0) < 7]
    avg_score = round(sum(j.get("score", 0) for j in all_jobs) / max(len(all_jobs), 1), 1)
    pending = len([j for j in all_jobs if not j.get("score")])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Jobs", f"{len(all_jobs):,}")
    k2.metric("Strong Match", f"{len(strong):,}", delta=f"≥7/10")
    k3.metric("Maybe", f"{len(maybe):,}", delta=f"4–6/10")
    k4.metric("Avg Score", f"{avg_score}/10")
    k5.metric("Unscored", f"{pending:,}")
else:
    st.info("No scored jobs yet. Run the pipeline to get started.")


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_jobs, tab_analytics = st.tabs(["  Jobs  ", "  Analytics  "])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1: JOBS
# ════════════════════════════════════════════════════════════════════════════
with tab_jobs:
    if not all_jobs:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div style="text-align:center; padding:4rem; color:#64748b">
            <div style="font-size:3rem; margin-bottom:1rem">🔍</div>
            <h3 style="color:#94a3b8; margin-bottom:0.5rem">No jobs found</h3>
            <p>Run the pipeline to start discovering jobs</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        # ── Filters bar ─────────────────────────────────────────────────────
        fc1, fc2, fc3, fc4 = st.columns([3, 1, 1, 1])
        with fc1:
            q = st.text_input("Search", placeholder="🔍  Search title, company...", label_visibility="collapsed")
        with fc2:
            min_s = st.selectbox("Min Score", list(range(11)), index=4, label_visibility="collapsed")
        with fc3:
            sources = ["All Sources"] + sorted(set(j.get("site","?") for j in all_jobs if j.get("site")))
            site_filter = st.selectbox("Source", sources, label_visibility="collapsed")
        with fc4:
            verdict_opts = ["All Verdicts", "yes", "maybe", "no"]
            verdict_filter = st.selectbox("Verdict", verdict_opts, label_visibility="collapsed")

        # ── Apply filters ───────────────────────────────────────────────────
        filtered = [
            j for j in all_jobs
            if j.get("score", 0) >= min_s
            and (not q or q.lower() in (j.get("title","") + j.get("company","")).lower())
            and (site_filter == "All Sources" or j.get("site") == site_filter)
            and (verdict_filter == "All Verdicts" or j.get("verdict") == verdict_filter)
        ]

        st.markdown(
            f"<p style='color:#64748b; font-size:0.82rem; margin:0.75rem 0'>"
            f"Showing <b style='color:#fff'>{len(filtered)}</b> of {len(all_jobs)} jobs</p>",
            unsafe_allow_html=True
        )

        # ── Job list ────────────────────────────────────────────────────────
        for job in filtered:
            score = job.get("score", 0)
            verdict = job.get("verdict", "no")

            if score >= 7:
                pill_cls = "score-high"
            elif score >= 4:
                pill_cls = "score-mid"
            else:
                pill_cls = "score-low"

            verdict_icon = {"yes": "✅", "maybe": "⚡", "no": "❌"}.get(verdict, "—")

            label_html = (
                f"<div style='display:flex; align-items:center; width:100%'>"
                f"<span class='score-pill {pill_cls}' style='min-width:50px; text-align:center'>{score}</span>"
                f"<span style='font-size:1.1rem; font-weight:600; color:#fff; margin-left:10px'>{job.get('title','?')}</span>"
                f"<span style='color:#64748b; font-size:0.9rem; margin-left:auto; margin-right:20px'>{job.get('company','?')}</span>"
                f"</div>"
            )

            with st.expander(label_html, expanded=False):
                left, right = st.columns([5, 1])
                with left:
                    # Meta tags
                    loc = job.get("location") or "Remote"
                    sal = job.get("salary") or "—"
                    src = job.get("site") or "Web"
                    dt  = job.get("date_posted") or "—"
                    st.markdown(
                        f"<span class='tag'>📍 {loc}</span>"
                        f"<span class='tag'>💰 {sal}</span>"
                        f"<span class='tag'>🌐 {src}</span>"
                        f"<span class='tag'>📅 {dt}</span>",
                        unsafe_allow_html=True
                    )
                    st.markdown("<br>", unsafe_allow_html=True)
                    reason = job.get("reason", "No AI insight available.")
                    st.markdown(
                        f"<p style='color:#94a3b8; font-size:0.875rem; line-height:1.7; margin:0'>"
                        f"<b style='color:#cbd5e1'>AI Insight:</b> {reason}</p>",
                        unsafe_allow_html=True
                    )
                with right:
                    url = job.get("url", "#")
                    if url and url != "#":
                        st.link_button("Open Job →", url, width="stretch")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2: ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    if not all_jobs:
        st.info("No data yet.")
    else:
        chart_col, dist_col = st.columns([3, 2])

        with chart_col:
            st.markdown("#### Score Distribution")
            df_scores = pd.DataFrame(all_jobs)
            df_scores["score"] = df_scores["score"].fillna(0).astype(int)
            counts = df_scores["score"].value_counts().reset_index()
            counts.columns = ["score", "count"]

            chart = alt.Chart(counts).mark_bar(
                cornerRadiusTopLeft=4,
                cornerRadiusTopRight=4,
            ).encode(
                x=alt.X("score:O", title="Score", axis=alt.Axis(labelAngle=0, labelColor="#64748b", titleColor="#64748b")),
                y=alt.Y("count:Q", title="Jobs",  axis=alt.Axis(labelColor="#64748b", titleColor="#64748b")),
                color=alt.condition(
                    alt.datum.score >= 7,
                    alt.value("#6366f1"),  # High score
                    alt.value("#1e293b")   # Others
                ),
                tooltip=["score:O", "count:Q"]
            ).configure_view(
                strokeWidth=0,
                fill="#0a0a0f"
            ).configure_axis(
                grid=False,
                domain=False,
            ).properties(height=260)

            st.altair_chart(chart, width="stretch")

        with dist_col:
            st.markdown("#### By Source")
            site_counts = (
                pd.DataFrame(all_jobs)
                .assign(site=lambda d: d["site"].fillna("Unknown"))
                ["site"].value_counts()
                .reset_index()
            )
            site_counts.columns = ["Source", "Count"]
            st.dataframe(
                site_counts,
                width="stretch",
                hide_index=True,
                height=290,
            )

        st.markdown("<hr>", unsafe_allow_html=True)

        # Verdict breakdown
        v1, v2 = st.columns(2)
        with v1:
            st.markdown("#### Verdict Breakdown")
            v_df = (
                pd.DataFrame(all_jobs)
                .assign(verdict=lambda d: d["verdict"].fillna("unscored"))
                ["verdict"].value_counts()
                .reset_index()
            )
            v_df.columns = ["Verdict", "Count"]
            v_df["Verdict"] = v_df["Verdict"].map(
                {"yes": "✅ Strong", "maybe": "⚡ Maybe", "no": "❌ No Fit", "unscored": "⏳ Pending"}
            ).fillna(v_df["Verdict"])
            st.dataframe(v_df, width="stretch", hide_index=True)

        with v2:
            st.markdown("#### Top Companies")
            top_co = (
                pd.DataFrame(all_jobs)
                .assign(company=lambda d: d["company"].fillna("Unknown"))
                ["company"].value_counts()
                .head(10)
                .reset_index()
            )
            top_co.columns = ["Company", "Jobs"]
            st.dataframe(top_co, width="stretch", hide_index=True)
