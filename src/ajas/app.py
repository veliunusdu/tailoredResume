import json
import os
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

from ajas.cli import (
    generate_cl_pipeline,
    generate_cv_pipeline,
    generate_tailored_for_job,
)
from ajas.database import Database
from ajas.llm import (
    generate_interview_prep,
    generate_networking_request,
    parse_cv_to_master,
)
from ajas.models import UserPreferences
from ajas.query_builder import build_queries_from_master
from ajas.run_filler import run_filler_sync
from ajas.search import query_jobs, search_jobs
from ajas.uploader import extract_text_from_bytes
from ajas.worker import generate_cl_task, generate_cv_task

# ---------------------------------------------------------------------------
# Setup & Sidebar
# ---------------------------------------------------------------------------
st.set_page_config(page_title="AJAS Command Center", layout="wide")
db = Database()

st.title("AJAS — Automated Job Application System")

# Password gate
password = st.sidebar.text_input("Enter Password", type="password")
if password != st.secrets.get("PASSWORD", "ajas2026"):
    st.sidebar.warning("Restricted Access")
    st.stop()

st.sidebar.success("Authenticated")

# Sidebar Metrics
st.sidebar.header("Daily Metrics")
daily_cost = db.get_daily_cost()
st.sidebar.metric("Today's Cost", f"${daily_cost:.4f}")
if daily_cost > 2.0:
    st.sidebar.error("⚠️ Daily soft limit of $2.00 exceeded.")

# ---------------------------------------------------------------------------
# Renderer Functions
# ---------------------------------------------------------------------------

def render_dashboard():
    st.header("Application Pipeline")
    apps = db.get_applications()

    if not apps:
        st.info("No applications yet. Start by generating one in the **Workbench** tab!")
    else:
        cols = st.columns(5)
        statuses = ["draft", "applied", "interview", "offer", "rejected"]

        for i, status in enumerate(statuses):
            with cols[i]:
                st.subheader(status.capitalize())
                status_apps = [a for a in apps if a["status"] == status]
                st.caption(f"{len(status_apps)} application(s)")
                for app in status_apps:
                    with st.expander(f"{app['company']} — {app['role']}"):
                        st.text(f"Applied: {app['applied_at']}")
                        if app["ats_score"]:
                            score = app["ats_score"]
                            color = "🟢" if score >= 60 else "🔴"
                            st.text(f"ATS Score: {color} {score:.1f}%")

                        if app.get("url") and st.button(
                            "🚀 Auto-Fill", key=f"fill_{app['id']}"
                        ):
                            with st.spinner("Launching browser for auto-fill..."):
                                with open(
                                    "data/master.yaml", "r", encoding="utf-8"
                                ) as f:
                                    master_data = yaml.safe_load(f)
                                run_filler_sync(app["url"], master_data)

                        new_status = st.selectbox(
                            "Update Status",
                            statuses,
                            index=statuses.index(status),
                            key=f"status_{app['id']}",
                        )
                        if new_status != status:
                            db.update_status(app["id"], new_status)
                            st.rerun()
    
    st.divider()
    st.subheader("Analytics (Coming Soon)")
    st.info("Visual breakdown of your application funnel will appear here.")

def render_profile():
    st.header("👤 Profile & Smart Sync")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("1. Sync from CV (LLM Parser)")

        # New: File Uploader
        uploaded_file = st.file_uploader(
            "Upload your CV (PDF, DOCX, TXT)", type=["pdf", "docx", "txt", "md"]
        )
        if uploaded_file is not None:
            if st.button("Extract & Parse Uploaded CV"):
                with st.spinner("Extracting text and parsing..."):
                    file_bytes = uploaded_file.read()
                    cv_text = extract_text_from_bytes(file_bytes, uploaded_file.name)
                    if cv_text:
                        try:
                            clean_json = parse_cv_to_master(cv_text)
                            parsed_data = json.loads(clean_json)
                            with open("data/master.yaml", "w", encoding="utf-8") as f:
                                yaml.dump(
                                    parsed_data, f, allow_unicode=True, sort_keys=False
                                )
                            st.success(
                                f"Successfully parsed {uploaded_file.name} and updated master.yaml!"
                            )
                            st.rerun()
                        except Exception as e:
                            st.error(f"Failed to parse extracted text: {e}")
                    else:
                        st.error("Failed to extract text from file.")

        st.divider()
        cv_raw = st.text_area("Paste your raw CV text here...", height=200)
        if st.button("Parse & Overwrite master.yaml"):
            with st.spinner("LLM is extracting structured data..."):
                try:
                    clean_json = parse_cv_to_master(cv_raw)
                    # Validate and Save
                    parsed_data = json.loads(clean_json)
                    with open("data/master.yaml", "w", encoding="utf-8") as f:
                        yaml.dump(parsed_data, f, allow_unicode=True, sort_keys=False)
                    st.success("master.yaml updated! Refreshing...")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to parse CV: {e}")

    with col2:
        st.subheader("2. Job Preferences")
        if not os.path.exists("data/master.yaml"):
            st.error("data/master.yaml not found. Upload a CV or create it manually.")
        else:
            with open("data/master.yaml", "r", encoding="utf-8") as f:
                master = yaml.safe_load(f)

            # Ensure preferences key exists
            if "preferences" not in master:
                master["preferences"] = UserPreferences().model_dump()

            prefs = master["preferences"]

            new_roles = st.text_input(
                "Target Roles (comma separated)",
                value=", ".join(prefs.get("target_roles", [])),
            )
            new_salary = st.text_input(
                "Target Salary", value=prefs.get("target_salary", "")
            )
            new_loc = st.text_input(
                "Preferred Locations", value=", ".join(prefs.get("location_preference", []))
            )
            new_remote = st.selectbox(
                "Remote Preference",
                ["Remote", "Hybrid", "On-site"],
                index=["Remote", "Hybrid", "On-site"].index(
                    prefs.get("remote_preference", "Remote")
                ),
            )
            new_visa = st.checkbox(
                "Visa Sponsorship Needed", value=prefs.get("visa_sponsorship", False)
            )

            if st.button("Save Preferences"):
                master["preferences"]["target_roles"] = [
                    r.strip() for r in new_roles.split(",") if r.strip()
                ]
                master["preferences"]["target_salary"] = new_salary
                master["preferences"]["location_preference"] = [
                    l.strip() for l in new_loc.split(",") if l.strip()
                ]
                master["preferences"]["remote_preference"] = new_remote
                master["preferences"]["visa_sponsorship"] = new_visa
                with open("data/master.yaml", "w", encoding="utf-8") as f:
                    yaml.dump(master, f, allow_unicode=True, sort_keys=False)
                st.success("Preferences saved!")

    st.divider()
    st.subheader("3. LinkedIn Connection Request Generator")
    st.caption("Paste the hiring manager's About/profile text manually (ToS-safe).")

    col_c, col_d = st.columns(2)
    with col_c:
        profile_text = st.text_area(
            "Paste Hiring Manager's Profile Text",
            height=250,
            key="profile_text",
        )
    with col_d:
        net_job_title = st.text_input("Role You're Interested In", key="net_job_title")
        net_company = st.text_input("Company Name", key="net_company")

    if st.button("✉️ Generate Connection Request"):
        if (
            not profile_text.strip()
            or not net_job_title.strip()
            or not net_company.strip()
        ):
            st.error("Profile text, job title, and company name are all required.")
        else:
            with st.spinner("Crafting connection request…"):
                try:
                    result = generate_networking_request(
                        profile_text, net_job_title, net_company
                    )

                    char_color = "🟢" if result.char_count <= 300 else "🔴"
                    st.subheader("Your Connection Request")
                    st.text_area(
                        f"Message ({char_color} {result.char_count}/300 characters)",
                        value=result.message,
                        height=150,
                        key="net_result",
                    )
                    if result.char_count > 300:
                        st.error(
                            "Message exceeds 300 characters — LinkedIn will truncate it."
                        )
                    else:
                        st.success("Ready to send! Copy and paste into LinkedIn.")
                except Exception as e:
                    st.error(f"Failed to generate connection request: {e}")

def render_workbench():
    st.header("🛠️ Job Workbench")
    
    with st.expander("🔍 Find New Opportunities", expanded=True):
        st.subheader("Instant Search")
        st.caption("Search live jobs via Adzuna API and tailor your CV instantly.")

        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            query = st.text_input(
                "What (Keywords)", placeholder="Software Engineer, Python...", key="workbench_query"
            )
        with col2:
            location = st.text_input(
                "Where (Location)", placeholder="USA, New York, Remote...", key="workbench_loc"
            )
        with col3:
            st.write("")  # Spacer
            if st.button("Search Jobs", use_container_width=True, key="workbench_search_btn"):
                st.session_state.job_results = search_jobs(query, location)

        if st.button("🧠 Find jobs matching my CV (Smart Query)", key="workbench_smart_btn"):
            with st.spinner("Analyzing CV and building search queries..."):
                with open("data/master.yaml", "r", encoding="utf-8") as f:
                    master_data = yaml.safe_load(f)
                queries = build_queries_from_master(master_data)
                st.session_state.job_results = query_jobs(queries)
                st.success(
                    f"Generated {len(queries)} queries and found {len(st.session_state.job_results)} results!"
                )

        if "job_results" in st.session_state and st.session_state.job_results:
            st.write(f"Found {len(st.session_state.job_results)} results:")
            for job in st.session_state.job_results:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.subheader(job["title"])
                        st.write(
                            f"**{job['company']}** | {job['location']} | Source: {job.get('source', 'Adzuna')}"
                        )
                        st.text(job["description"][:300] + "...")
                    with c2:
                        job_key = job.get("id") or job.get("fingerprint")
                        if st.button("Tailor CV", key=f"tailor_{job_key}"):
                            st.session_state.target_jd = job["description"]
                            st.info("JD copied to 'Generate' section! Scroll down.")

                        if st.button("⚡ Quick Tailor", key=f"qtailor_{job_key}"):
                            with st.spinner("Running one-click pipeline..."):
                                try:
                                    cv_path, app_id = generate_tailored_for_job(
                                        job, "data/master.yaml"
                                    )
                                    st.success(
                                        f"Generated! [Open Folder](file:///{os.path.abspath('data/outputs')})"
                                    )
                                    st.info(f"Logged as application ID: {app_id}")
                                except Exception as e:
                                    st.error(f"Quick Tailor failed: {e}")

                        st.link_button("View Original", job["url"])

        st.divider()

        st.subheader("Daily Discovery Scout")
        st.caption("Fetch and score jobs from all configured sources in data/sources.yaml.")

        if st.button("🚀 Trigger Discovery Scout", key="workbench_scout_btn"):
            from ajas.search import discover_new_jobs

            with st.spinner("Discovering and scoring new jobs..."):
                new_count = discover_new_jobs()
                st.success(f"Scout complete! Found {new_count} new unique jobs.")

        st.write("### Discovered Opportunities")
        discovered = db.get_new_jobs(limit=10)
        if discovered:
            for job in discovered:
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    with c1:
                        st.subheader(job["title"])
                        st.write(
                            f"**{job['company']}** | {job['location']} | Source: {job['source']}"
                        )
                        st.write(f"**Relevance Score: {job['relevance_score']:.2f}**")
                        st.text(job["description"][:200] + "...")
                    with c2:
                        if st.button("Tailor CV", key=f"tailor_disc_{job['fingerprint']}"):
                            st.session_state.target_jd = job["description"]
                            st.info("JD copied to 'Generate' section!")
                        st.link_button("View Original", job["url"])
        else:
            st.info("No discovered jobs yet. Run the scout to find some!")

    with st.expander("✍️ Generate Tailored Assets", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            job_input = st.text_area("Paste Job Description or URL", 
                                    value=st.session_state.get("target_jd", ""),
                                    height=300, key="workbench_jd_input")
        with col2:
            master_path = st.text_input("Path to Master CV", value="data/master.yaml", key="workbench_master_path")
            target_url = st.text_input("Application URL (for Auto-Fill)", key="workbench_target_url")

        if st.button("🚀 Queue Generation (Async)", key="workbench_gen_btn"):
            if not job_input.strip():
                st.error("Please paste a job description first.")
            else:
                job_file = "data/temp_job.txt"
                with open(job_file, "w", encoding="utf-8") as f:
                    f.write(job_input)
                with st.spinner("Queuing tasks..."):
                    trace_id = str(uuid.uuid4())
                    try:
                        generate_cv_task.delay(job_file, master_path, trace_id)
                        generate_cl_task.delay(job_file, master_path, trace_id)
                        st.success(f"✅ Tasks queued! Trace ID: `{trace_id}`")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Failed to queue task — make sure Redis/Celery are running: {e}")

        st.divider()
        st.subheader("Run Inline (Sync)")
        col3, col4 = st.columns(2)
        with col3:
            if st.button("Generate CV (inline)", key="workbench_cv_inline"):
                if not job_input.strip():
                    st.error("Paste a job description first.")
                else:
                    job_file = "data/temp_job.txt"
                    with open(job_file, "w", encoding="utf-8") as f:
                        f.write(job_input)
                    with st.spinner("Running CV pipeline…"):
                        try:
                            generate_cv_pipeline(job_file, master_path)
                            st.success("CV generated! Check data/outputs/")
                        except Exception as e:
                            st.error(f"Pipeline error: {e}")
        with col4:
            if st.button("Generate Cover Letter (inline)", key="workbench_cl_inline"):
                if not job_input.strip():
                    st.error("Paste a job description first.")
                else:
                    job_file = "data/temp_job.txt"
                    with open(job_file, "w", encoding="utf-8") as f:
                        f.write(job_input)
                    with st.spinner("Running cover letter pipeline…"):
                        try:
                            generate_cl_pipeline(job_file, master_path)
                            st.success("Cover Letter generated! Check data/outputs/")
                        except Exception as e:
                            st.error(f"Pipeline error: {e}")

    with st.expander("🎯 Interview Prep", expanded=False):
        st.caption("Generates STAR behavioral questions, technical questions, and a pitch.")

        col_a, col_b = st.columns(2)
        with col_a:
            prep_jd = st.text_area("Paste Job Description", height=250, key="workbench_prep_jd")
        with col_b:
            prep_cv = st.text_area(
                "Paste the Tailored CV that was sent",
                height=250,
                key="workbench_prep_cv",
            )

        if st.button("🎯 Generate Interview Prep", key="workbench_prep_btn"):
            if not prep_jd.strip() or not prep_cv.strip():
                st.error("Both Job Description and submitted CV text are required.")
            else:
                with st.spinner("Generating interview prep…"):
                    try:
                        prep = generate_interview_prep(prep_jd, prep_cv)
                        st.subheader("📋 STAR Behavioral Questions")
                        for i, q in enumerate(prep.behavioral_questions, 1):
                            st.markdown(f"**{i}.** {q}")
                        st.subheader("💻 Technical Questions")
                        for i, q in enumerate(prep.technical_questions, 1):
                            st.markdown(f"**{i}.** {q}")
                        st.subheader("🎤 30-Second Elevator Pitch")
                        st.info(prep.elevator_pitch)
                    except Exception as e:
                        st.error(f"Failed to generate interview prep: {e}")

# ---------------------------------------------------------------------------
# Main Router
# ---------------------------------------------------------------------------
tab_workbench, tab_profile_sync, tab_dashboard = st.tabs(["Workbench", "Profile", "Dashboard"])

with tab_workbench:
    render_workbench()

with tab_profile_sync:
    render_profile()

with tab_dashboard:
    render_dashboard()
