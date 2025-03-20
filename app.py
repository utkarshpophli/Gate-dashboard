import os
import json
import sqlite3
import time
import datetime
import requests
import random
import pandas as pd
import easyocr
from io import BytesIO
import plotly.express as px
import streamlit as st
from pathlib import Path
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
import sqlalchemy
from sqlalchemy import create_engine, text
from azure.ai.inference.models import (
    SystemMessage,
    UserMessage,
    AssistantMessage,
    TextContentItem,
    ImageContentItem,
    ImageUrl,
    ImageDetailLevel
)
from azure.core.credentials import AzureKeyCredential
from supabase import create_client, Client
from PIL import Image
import pytesseract
import PyPDF2
from transformers import pipeline


load_dotenv()

# Supabase client initialization
supabase: Client = create_client(
    supabase_url=st.secrets["SUPABASE_URL"],
    supabase_key=st.secrets["SUPABASE_KEY"]
)

st.set_page_config(
    page_title="GATE DA 2026 Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Optional: for PDF and image text extraction
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None
try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

def load_css():
    """Load all CSS files from the static directory"""
    css_directory = Path("static/css")

    # First load base styles
    base_styles = [
        css_directory / "base/reset.css",
        css_directory / "base/variables.css",
        css_directory / "base/typography.css",
        css_directory / "base/animations.css"
    ]

    css_content = []

    # Load base styles first
    for css_file in base_styles:
        if css_file.exists():
            with open(css_file) as f:
                css_content.append(f.read())

    # Load main style.css which imports everything else
    main_style = css_directory / "style.css"
    if main_style.exists():
        with open(main_style) as f:
            css_content.append(f.read())

    # Combine all CSS and inject
    combined_css = "\n".join(css_content)
    st.markdown(f"<style>{combined_css}</style>", unsafe_allow_html=True)

def load_page_specific_css(page_name):
    """Load page-specific CSS"""
    css_file = Path(f"static/css/pages/{page_name.lower().replace(' ', '_')}.css")
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def create_header():
    """Create the app header with logo and title"""
    header_html = """
        <div class="app-header">
            <img src="data:image/png;base64,{}" class="app-logo">
            <div class="app-header-content">
                <h1 class="app-title">GATE DA 2026</h1>
                <p class="app-subtitle">Study Dashboard & Planner</p>
            </div>
        </div>
    """

    # Read the logo image
    logo_path = Path("static/images/logos/app-logo.png")
    if logo_path.exists():
        import base64
        with open(logo_path, "rb") as f:
            logo_data = base64.b64encode(f.read()).decode()

        # Display the header
        st.markdown(header_html.format(logo_data), unsafe_allow_html=True)
    else:
        st.error("Logo file not found!")

def set_favicon():
    """Set a custom favicon"""
    favicon_path = Path("static/images/logos/app-logo.png")
    if favicon_path.exists():
        import base64
        with open(favicon_path, "rb") as f:
            favicon_data = base64.b64encode(f.read()).decode()

        favicon_html = f"""
            <link rel="shortcut icon" href="data:image/png;base64,{favicon_data}">
        """
        st.markdown(favicon_html, unsafe_allow_html=True)

# Database Setup & Helpers
def init_db():
    """Initializes the Supabase database by creating tables and inserting default schedule data."""
    try:
        default_phases = {
            "Phase 1": {
                "title": "Foundations (Months 1–2)",
                "focus": "Engineering Mathematics & Discrete Mathematics",
                "table": [
                    ["Monday", "7:00-9:00 PM", "Theory Lecture", "Calculus Fundamentals"],
                    ["Tuesday", "7:00-9:00 PM", "Problem-Solving", "Calculus: Worked examples and derivations"],
                    ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Linear Algebra Basics: Vector spaces, matrices, operations"],
                    ["Thursday", "7:00-9:00 PM", "Problem-Solving", "Linear Algebra: Determinants, eigenvalues"],
                    ["Friday", "7:00-9:00 PM", "Weekly Recap & Quiz", "Combined Topics: Quick tests and self-assessment"],
                    ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Live lecture reinforcing fundamentals"],
                    ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "In-depth lecture on Calculus/Linear Algebra"],
                    ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Exercises and sample problems"],
                    ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Comprehensive problem sets"],
                    ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Full-length practice test and error analysis"]
                ]
            },
            "Phase 2": {
                "title": "Advanced Mathematics & Probability/Statistics (Months 3–4)",
                "focus": "Advanced Probability & Statistics topics (counting, axioms, distributions, optimization, hypothesis testing) with Go Classes sessions for clarifications.",
                "table": [
                    ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
                    ["Monday", "7:00-9:00 PM", "Theory Lecture", "Counting Techniques & Probability Basics: Permutations, combinations, axioms"],
                    ["Tuesday", "7:00-9:00 PM", "Problem-Solving", "Probability Concepts: Sample spaces, independence, events"],
                    ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Random Variables & Distributions: Discrete (Bernoulli, Binomial) and Continuous (Uniform, Exponential)"],
                    ["Thursday", "7:00-9:00 PM", "Practice & Exercises", "Statistical Inference: Conditional probability, Bayes' theorem"],
                    ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: CLT, confidence intervals, z-test, t-test, chi-squared test"],
                    ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Session on key problem areas in probability/statistics"],
                    ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Advanced Topics: In-depth derivations and optimization techniques"],
                    ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Challenging problems and test-style questions"],
                    ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined exercises and review"],
                    ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Timed tests with detailed error analysis"]
                ]
            },
            "Phase 3": {
                "title": "Programming, Data Structures, Algorithms & Database Management (Months 5–7)",
                "focus": "Python programming, core data structures and algorithms, and database management fundamentals, with supplementary Go Classes sessions for coding and database concepts.",
                "table": [
                    ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
                    ["Monday", "7:00-9:00 PM", "Theory Lecture", "Python Programming & Basic Data Structures: Syntax, data types, stacks, queues"],
                    ["Tuesday", "7:00-9:00 PM", "Coding Practice", "Data Structures: Implementation of linked lists, arrays, etc."],
                    ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Algorithms: Search algorithms (linear, binary) and basic sorting"],
                    ["Thursday", "7:00-9:00 PM", "Problem-Solving", "Hands-On: Coding exercises on trees, hash tables, etc."],
                    ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: Quick quizzes and conceptual coding reviews"],
                    ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Live session on coding challenges and database queries"],
                    ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Database Management: ER-model, relational algebra, SQL, normalization"],
                    ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Hands-on coding and SQL query practices"],
                    ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined coding challenges and algorithm problem sets"],
                    ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Full-length tests with detailed walkthroughs"]
                ]
            },
            "Phase 4": {
                "title": "Machine Learning & Artificial Intelligence (Months 8–10)",
                "focus": "Supervised & unsupervised machine learning techniques and AI fundamentals, with interactive Go Classes sessions on advanced ML/AI topics.",
                "table": [
                    ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
                    ["Monday", "7:00-9:00 PM", "Theory Lecture", "Supervised Learning: Regression (simple, multiple, ridge) & Classification (logistic, SVM, etc.)"],
                    ["Tuesday", "7:00-9:00 PM", "Practical Implementation", "Supervised Learning: Python coding (k-nearest neighbors, decision trees)"],
                    ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Neural Networks: Fundamentals of MLP and feed-forward architecture"],
                    ["Thursday", "7:00-9:00 PM", "Coding Practice", "Unsupervised Learning: Clustering (k-means, hierarchical) and PCA implementations"],
                    ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: Bias-variance, cross-validation, and key ML/AI concepts"],
                    ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Interactive session on ML/AI problem solving"],
                    ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Artificial Intelligence: Search strategies, logic, reasoning under uncertainty"],
                    ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Case studies and sample problems on ML/AI algorithms"],
                    ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Mixed Topics: Comprehensive exercises integrating ML/AI concepts"],
                    ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Full-length mock tests with in-depth error analysis"]
                ]
            },
            "Phase 5": {
                "title": "Revision, Practice & Mock Tests (Months 11–12)",
                "focus": "Comprehensive revision of all subjects with intensive practice, mock tests, and error analysis. Final Go Classes sessions polish exam strategies.",
                "table": [
                    ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
                    ["Monday", "7:00-9:00 PM", "Revision Session", "Quick review of Calculus, Linear Algebra, Discrete Math"],
                    ["Tuesday", "7:00-9:00 PM", "Revision & Practice", "Probability & Statistics: Key formulas and targeted problems"],
                    ["Wednesday", "7:00-9:00 PM", "Revision Session", "Programming & Algorithms: Code review and challenging problem solving"],
                    ["Thursday", "7:00-9:00 PM", "Revision & Practice", "Database Management: SQL queries, normalization, ER-model refresh"],
                    ["Friday", "7:00-9:00 PM", "Mixed Revision & Quiz", "Machine Learning & AI: Quick quizzes and concept reviews"],
                    ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Final review and strategy session"],
                    ["Saturday", "10:00 AM-12:00 PM", "Full-Length Mock Test", "Simulated exam covering the entire syllabus"],
                    ["Saturday", "1:00-4:00 PM", "Error Analysis & Revision", "Detailed review of mistakes and focus on weak areas"],
                    ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined problem sets for speed and accuracy"],
                    ["Sunday", "1:00-5:00 PM", "Final Revision & Strategy", "Overall preparation: Strategy session, key summaries, and Q&A review"]
                ]
            },
            "General Aptitude": {
                "title": "General Aptitude",
                "focus": "Quantitative, Logical, and Verbal skills",
                "table": [
                    ["Monday", "5:00-6:00 PM", "Practice", "Quantitative problems"],
                    ["Wednesday", "5:00-6:00 PM", "Practice", "Logical reasoning puzzles"],
                    ["Friday", "5:00-6:00 PM", "Practice", "Verbal ability and reading comprehension"]
                ]
            }
        }

        # Insert default phases if they don't exist
        for phase, details in default_phases.items():
            existing = supabase.table("schedule").select("*").eq("phase", phase).execute()

            if not existing.data:  # If phase doesn't exist, insert it
                response = supabase.table("schedule").insert({
                    "phase": phase,
                    "title": details["title"],
                    "focus": details["focus"],
                    "schedule_json": json.dumps(details["table"])
                }).execute()

                if not hasattr(response, 'data'):
                    st.error(f"Error inserting phase {phase}")

    except Exception as e:
        st.error(f"Error initializing database: {str(e)}")

def insert_progress_log(date_str, phase, subject, hours, notes):
    """Inserts a new progress log."""
    try:
        data = {
            'date': date_str,
            'phase': phase,
            'subject': subject,
            'hours': float(hours),
            'notes': notes
        }

        response = supabase.table('progress_logs').insert(data).execute()

        if isinstance(response.data, list) and len(response.data) > 0:
            return True
        return False

    except Exception as e:
        st.error(f"Error inserting progress log: {str(e)}")
        return False

def update_schedule_db(phase, new_table):
    data = {"schedule_json": json.dumps(new_table)}
    result = supabase.table("schedule").update(data).eq("phase", phase).execute()
    if result.error:
        st.error(f"Error updating schedule: {result.error}")

def get_all_schedules():
    """Retrieves all schedules from the Supabase database"""
    try:
        response = supabase.table('schedule').select('*').execute()

        schedules = {}

        if hasattr(response, 'data') and response.data:
            for row in response.data:
                schedules[row['phase']] = {
                    'title': row['title'],
                    'focus': row['focus'],
                    'table': json.loads(row['schedule_json']) if row['schedule_json'] else []
                }
        return schedules
    except Exception as e:
        st.error(f"Error fetching schedules: {str(e)}")
        return {}

def get_progress_logs():
    """Retrieves all progress logs."""
    try:
        response = supabase.table('progress_logs').select(
            'id,date,phase,subject,hours,notes'
        ).order('date', desc=True).execute()

        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching progress logs: {str(e)}")
        return []

def insert_question(subject, question, answer):
    """Inserts a new question into the question bank."""
    try:
        data = {
            "subject": subject,
            "question": question,
            "answer": answer
        }
        response = supabase.table("question_bank").insert(data).execute()
        return hasattr(response, 'data') and response.data
    except Exception as e:
        st.error(f"Error inserting question: {str(e)}")
        return False

def get_all_questions():
    """Retrieves all questions from the question bank."""
    try:
        response = supabase.table("question_bank").select("*").execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching questions: {str(e)}")
        return []

def insert_resource(subject, title, link, filename=None):
    """Inserts a new resource into the database."""
    try:
        data = {
            "subject": subject,
            "title": title,
            "link": link,
            "filename": filename
        }
        response = supabase.table("resources").insert(data).execute()
        return hasattr(response, 'data') and response.data
    except Exception as e:
        st.error(f"Error inserting resource: {str(e)}")
        return False

def delete_resource(resource_id):
    """Deletes a resource from the database."""
    try:
        response = supabase.table("resources").delete().eq('id', resource_id).execute()
        return hasattr(response, 'data') and response.data
    except Exception as e:
        st.error(f"Error deleting resource: {str(e)}")
        return False

def get_all_resources():
    """Retrieves all resources from the database."""
    try:
        response = supabase.table("resources").select("*").execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching resources: {str(e)}")
        return []

def insert_study_goal(description, target_hours, achieved_hours=0):
    """Inserts a new study goal into the database."""
    try:
        data = {
            "description": description,
            "target_hours": float(target_hours),
            "achieved_hours": float(achieved_hours)
        }
        response = supabase.table("study_goals").insert(data).execute()
        return hasattr(response, 'data') and response.data
    except Exception as e:
        st.error(f"Error inserting study goal: {str(e)}")
        return False

def get_study_goals():
    """Retrieves all study goals from the database."""
    try:
        response = supabase.table("study_goals").select("*").execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching study goals: {str(e)}")
        return []

def update_goal_achievement(goal_id, additional_hours):
    """Updates the achieved hours for a study goal."""
    try:
        response = supabase.table("study_goals").select("*").eq('id', goal_id).execute()
        if hasattr(response, 'data') and response.data:
            current_goal = response.data[0]
            new_achieved = float(current_goal['achieved_hours']) + float(additional_hours)

            update_response = supabase.table("study_goals").update(
                {"achieved_hours": new_achieved}
            ).eq('id', goal_id).execute()

            return hasattr(update_response, 'data') and update_response.data
        return False
    except Exception as e:
        st.error(f"Error updating goal achievement: {str(e)}")
        return False

def delete_study_goal(goal_id):
    """Deletes a study goal from the database."""
    try:
        response = supabase.table("study_goals").delete().eq('id', goal_id).execute()
        return hasattr(response, 'data') and response.data
    except Exception as e:
        st.error(f"Error deleting study goal: {str(e)}")
        return False

def insert_revision_note(subject, short_notes, formula):
    data = {"subject": subject, "short_notes": short_notes, "formula": formula}
    result = supabase.table("revision_notes").insert(data).execute()
    if result.error:
        st.error(f"Error inserting revision note: {result.error}")

def get_revision_notes():
    """Retrieves all revision notes from the database."""
    try:
        response = supabase.table("revision_notes").select("*").execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching revision notes: {str(e)}")
        return []

def get_progress_logs_for_report():
    """Retrieves all progress logs with additional analytics for reporting."""
    try:
        response = supabase.table('progress_logs').select('*').order('date', ascending=False).execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching progress logs: {str(e)}")
        return []

# Global Lists for Dropdowns
SUBJECT_LIST = [
    "Linear Algebra",
    "Probability",
    "Calculus",
    "Discrete Mathematics",
    "Programming & Data Structures",
    "Algorithms",
    "Database Management",
    "Machine Learning",
    "Artificial Intelligence",
    "General Aptitude"
]

# Utility Functions for RAG
def extract_text_from_file(file_path):
    ext = file_path.split('.')[-1].lower()
    extracted_text = ""
    if ext == "pdf" and PyPDF2:
        try:
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted_text += page.extract_text() + "\n"
        except Exception as e:
            extracted_text += f"[Error extracting PDF text: {e}]"
    elif ext in ["png", "jpg", "jpeg"]:
        try:
            reader = easyocr.Reader(['en'])
            result = reader.readtext(file_path)
            for (bbox, text, prob) in result:
                extracted_text += text + "\n"
        except Exception as e:
            extracted_text += f"[Error extracting image text: {e}]"
    return extracted_text

def generate_notes_from_text(extracted_text):
    """Generate structured notes from the extracted text."""
    notes = []
    lines = extracted_text.split('\n')
    current_section = ""
    current_content = []

    for line in lines:
        if line.strip().endswith(":") or line.strip().endswith("→"):
            if current_section:
                notes.append((current_section, current_content))
            current_section = line.strip()
            current_content = []
        else:
            current_content.append(line.strip())

    if current_section:
        notes.append((current_section, current_content))

    return notes

def get_rag_context(selected_subject):
    """Combine text from question bank, revision notes, and resources for a given subject."""
    context_parts = []

    try:
        questions = get_all_questions()
        subject_questions = [q for q in questions if q["subject"].lower() == selected_subject.lower()]
        if subject_questions:
            q_text = "\n".join([
                f"Q: {q['question']}\nA: {q['answer'] if q['answer'] else 'No answer provided'}"
                for q in subject_questions
            ])
            context_parts.append("Question Bank:\n" + q_text)

        notes = get_revision_notes()
        subject_notes = [n for n in notes if n["subject"].lower() == selected_subject.lower()]
        if subject_notes:
            n_text = "\n".join([
                f"Note: {n['short_notes']}\nFormula: {n['formula']}"
                for n in subject_notes
            ])
            context_parts.append("Revision Notes:\n" + n_text)

        resources = get_all_resources()
        subject_resources = [
            r for r in resources
            if r["subject"] and r["subject"].lower() == selected_subject.lower()
            and r["filename"]
        ]

        if subject_resources:
            r_text = "\n".join([
                f"Resource: {r['title']} (File: {os.path.basename(r['filename'])})"
                for r in subject_resources
            ])
            context_parts.append("Available Resources:\n" + r_text)

        return "\n\n".join(context_parts)

    except Exception as e:
        st.error(f"Error building RAG context: {str(e)}")
        return ""

# Streamlit App Pages
def display_dataframe(df, hide_index=True):
    """Helper function to display dataframes with hidden index"""
    if hide_index:
        return st.dataframe(df.reset_index(drop=True))
    return st.dataframe(df)

def dashboard_page():
    st.title("GATE DA 2026 Dashboard")
    st.subheader("Overview of Your Study Progress")

    try:
        schedules = get_all_schedules()
        phase_options = list(schedules.keys()) if schedules else ['Phase 1']

        with st.form("study_session_form"):
            session_date = st.date_input("Date", datetime.date.today())
            selected_phase = st.selectbox("Select Phase", phase_options)
            selected_subject = st.selectbox("Subject", SUBJECT_LIST)
            hours = st.number_input(
                "Hours Studied",
                min_value=0.0,
                max_value=24.0,
                value=0.0,
                step=0.5
            )
            notes = st.text_area("Notes / Reflection")
            submitted = st.form_submit_button("Log Session")

            if submitted:
                try:
                    date_str = session_date.strftime("%-m/%-d/%Y")
                    success = insert_progress_log(date_str, selected_phase, selected_subject, hours, notes)

                    if success:
                        st.success("Study session logged successfully!")
                        time.sleep(0.5)
                        st.rerun()

                except Exception as e:
                    st.error(f"Error logging session: {str(e)}")

    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
        return

    try:
        logs_response = supabase.table('progress_logs').select(
            'id,date,phase,subject,hours,notes'
        ).order('date', desc=True).execute()

        if isinstance(logs_response.data, list) and len(logs_response.data) > 0:
            st.header("Study Sessions Log")
            df_logs = pd.DataFrame(logs_response.data)

            df_logs['date'] = pd.to_datetime(df_logs['date'])
            df_logs = df_logs.sort_values('date', ascending=False)
            df_logs['date'] = df_logs['date'].dt.strftime('%Y-%m-%d')

            columns_order = ['id', 'date', 'phase', 'subject', 'hours', 'notes']
            df_logs = df_logs[columns_order]

            st.dataframe(
                df_logs,
                hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID"),
                    "date": "Date",
                    "phase": "Phase",
                    "subject": "Subject",
                    "hours": st.column_config.NumberColumn(
                        "Hours",
                        format="%.1f"
                    ),
                    "notes": "Notes"
                }
            )

    except Exception as e:
        st.error(f"Error loading logs: {str(e)}")

def analytics_page():
    st.title("Progress Analytics")

    try:
        logs_response = supabase.table('progress_logs').select('*').execute()

        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study session data available for analytics.")
            return

        logs = logs_response.data

        df_logs = pd.DataFrame(logs)
        df_logs["date"] = pd.to_datetime(df_logs["date"])
        df_logs.sort_values("date", inplace=True)

        tab1, tab2, tab3 = st.tabs(["Progress Summary", "Time Analysis", "Subject Analysis"])

        with tab1:
            st.header("Progress Summary")

            total_hours = df_logs["hours"].sum()
            total_days = len(df_logs["date"].unique())
            avg_hours_per_day = total_hours / total_days if total_days > 0 else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Study Hours", f"{total_hours:.1f}")
            with col2:
                st.metric("Days Studied", total_days)
            with col3:
                st.metric("Avg Hours/Day", f"{avg_hours_per_day:.1f}")

            st.subheader("Subject-wise Progress")
            subject_summary = df_logs.groupby("subject").agg({
                "hours": ["sum", "count"],
                "date": "nunique"
            }).reset_index()
            subject_summary.columns = ["Subject", "Total Hours", "Sessions", "Days"]
            subject_summary["Avg Hours/Session"] = subject_summary["Total Hours"] / subject_summary["Sessions"]
            subject_summary = subject_summary.sort_values("Total Hours", ascending=False)
            st.dataframe(subject_summary.round(2))

        with tab2:
            st.header("Time Analysis")

            time_analysis = st.selectbox(
                "Select Time Analysis",
                ["Daily Trend", "Weekly Pattern", "Monthly Progress", "Cumulative Progress"]
            )

            if time_analysis == "Daily Trend":
                daily_hours = df_logs.groupby("date")["hours"].sum().reset_index()
                fig = px.line(daily_hours, x="date", y="hours",
                             title="Daily Study Hours",
                             labels={"hours": "Hours", "date": "Date"})
                st.plotly_chart(fig, use_container_width=True, key='tab2')

            elif time_analysis == "Weekly Pattern":
                df_logs["weekday"] = df_logs["date"].dt.day_name()
                weekly_hours = df_logs.groupby("weekday")["hours"].agg(["sum", "mean"]).reset_index()
                weekly_hours.columns = ["Weekday", "Total Hours", "Average Hours"]

                weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                weekly_hours["Weekday"] = pd.Categorical(weekly_hours["Weekday"], categories=weekday_order, ordered=True)
                weekly_hours = weekly_hours.sort_values("Weekday")

                fig = px.bar(weekly_hours, x="Weekday", y="Average Hours",
                            title="Average Study Hours by Weekday")
                st.plotly_chart(fig, use_container_width=True,key='tab_week')

            elif time_analysis == "Monthly Progress":
                df_logs["month"] = df_logs["date"].dt.strftime("%Y-%m")
                monthly_hours = df_logs.groupby("month")["hours"].sum().reset_index()
                fig = px.bar(monthly_hours, x="month", y="hours",
                            title="Monthly Study Hours")
                st.plotly_chart(fig, use_container_width=True, key='tab_month')

            else:
                df_logs["cumulative_hours"] = df_logs["hours"].cumsum()
                fig = px.line(df_logs, x="date", y="cumulative_hours",
                             title="Cumulative Study Hours")
                st.plotly_chart(fig, use_container_width=True, key='tab_cumulative')

        with tab3:
            st.header("Subject Analysis")

            selected_subject = st.selectbox("Select Subject for Detailed Analysis",
                                          df_logs["subject"].unique())

            subject_data = df_logs[df_logs["subject"] == selected_subject]

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Hours", f"{subject_data['hours'].sum():.1f}")
            with col2:
                st.metric("Number of Sessions", len(subject_data))
            with col3:
                avg_session = subject_data["hours"].mean()
                st.metric("Avg Hours/Session", f"{avg_session:.1f}")

            fig = px.line(subject_data, x="date", y="hours",
                         title=f"{selected_subject} - Study Hours Over Time")
            st.plotly_chart(fig, use_container_width=True, key='tab3')

            st.subheader("Session Details")
            session_details = subject_data[["date", "phase", "hours", "notes"]].sort_values("date", ascending=False)
            st.dataframe(session_details)

    except Exception as e:
        st.error(f"Error in analytics: {str(e)}")
        return

def study_planner_page():
    st.title("Study Planner")
    st.subheader("Plan and View Your Schedule for Each Phase")

    try:
        schedules = get_all_schedules()

        if not schedules:
            st.warning("No schedule data available. Initializing default schedules...")
            init_db()
            schedules = get_all_schedules()

        if not schedules:
            st.error("Could not load schedule data. Please check the database connection.")
            return

        phase_keys = sorted(list(schedules.keys()))

        if not phase_keys:
            st.error("No phases found in the schedule.")
            return

        tabs = st.tabs(phase_keys)

        for i, phase in enumerate(phase_keys):
            with tabs[i]:
                phase_info = schedules[phase]
                st.write(f"**Title:** {phase_info['title']}")
                st.write(f"**Focus:** {phase_info['focus']}")
                st.write("**Schedule:**")

                if phase_info.get("table"):
                    df_phase = pd.DataFrame(
                        phase_info["table"],
                        columns=["Day", "Time Slot", "Activity", "Details"]
                    )

                    if hasattr(st, "experimental_data_editor"):
                        edited_df = st.experimental_data_editor(
                            df_phase,
                            num_rows="dynamic",
                            key=f"schedule_{phase}"
                        )
                        if st.button("Save changes", key=f"save_{phase}"):
                            update_schedule_db(phase, edited_df.values.tolist())
                            st.success(f"Schedule for {phase} saved!")
                    else:
                        st.dataframe(df_phase)
                else:
                    st.info(f"No schedule data available for {phase}")

    except Exception as e:
        st.error(f"Error loading study planner: {str(e)}")
        st.error("Detailed error information:")
        st.exception(e)

def revision_hub_page():
    st.title("Revision Hub")
    st.subheader("Add and Display Short Notes, Formulas, and Upload Files")
    with st.form("revision_notes_form"):
        selected_subject = st.selectbox("Select Subject", SUBJECT_LIST)
        short_notes = st.text_area("Short Notes")
        formula = st.text_area("Formula")
        submitted = st.form_submit_button("Add Revision Note")
        if submitted:
            if selected_subject and (short_notes or formula):
                insert_revision_note(selected_subject, short_notes, formula)
                st.success("Revision note added!")
            else:
                st.error("Please provide at least one of Short Notes or Formula.")
    all_notes = get_revision_notes()
    if all_notes:
        df_notes = pd.DataFrame(all_notes, columns=all_notes[0].keys())
        st.dataframe(df_notes)
    else:
        st.info("No revision notes added yet.")

    st.markdown("---")
    st.markdown("### Upload Additional Revision Resources (PDF/Images)")
    uploaded_file = st.file_uploader("Upload a file", type=["pdf", "docx", "xlsx", "png", "jpg"])
    if uploaded_file:
        upload_folder = "uploads"
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        file_path = os.path.join(upload_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        subject_for_resource = st.text_input("Enter subject for this resource (optional)")
        title = st.text_input("Enter title for this resource (optional)", value=uploaded_file.name)
        insert_resource(subject_for_resource, title, "", file_path)
        st.success("Resource uploaded and saved!")

def question_bank_page():
    st.title("Question Bank")
    st.subheader("Store and Review Questions & Patterns by Subject")

    with st.form("question_bank_form"):
        subject = st.selectbox("Subject", SUBJECT_LIST)
        question_text = st.text_area("Question")
        answer_text = st.text_area("Answer / Pattern (optional)")
        submit = st.form_submit_button("Add Question")

        if submit:
            if subject and question_text:
                if insert_question(subject, question_text, answer_text):
                    st.success("Question added successfully!")
                    st.rerun()
            else:
                st.error("Please provide both a subject and a question.")

    try:
        questions = get_all_questions()
        if questions:
            st.header("Existing Questions")

            search_term = st.text_input("Search questions (by subject or content):")

            df_questions = pd.DataFrame(questions)

            if search_term:
                mask = (
                    df_questions['subject'].str.contains(search_term, case=False, na=False) |
                    df_questions['question'].str.contains(search_term, case=False, na=False) |
                    df_questions['answer'].str.contains(search_term, case=False, na=False)
                )
                df_questions = df_questions[mask]

            subjects = df_questions['subject'].unique()

            for subject in subjects:
                with st.expander(f"{subject} ({len(df_questions[df_questions['subject'] == subject])} questions)"):
                    subject_questions = df_questions[df_questions['subject'] == subject]

                    for _, row in subject_questions.iterrows():
                        st.markdown("---")
                        st.markdown(f"**Question:** {row['question']}")
                        if row['answer']:
                            st.markdown(f"**Answer:** {row['answer']}")

                        if st.button(f"Delete Question {row['id']}", key=f"del_{row['id']}"):
                            try:
                                response = supabase.table("question_bank").delete().eq('id', row['id']).execute()
                                if hasattr(response, 'data'):
                                    st.success(f"Question {row['id']} deleted successfully!")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error deleting question: {str(e)}")
        else:
            st.info("No questions added yet. Use the form above to add questions.")

    except Exception as e:
        st.error(f"Error loading questions: {str(e)}")

def resources_page():
    st.title("Resources")
    st.subheader("Store Resource Links and Files")

    tab1, tab2 = st.tabs(["Add Resource", "View Resources"])

    with tab1:
        with st.form("resources_form"):
            subject = st.selectbox("Subject", SUBJECT_LIST)
            resource_title = st.text_input("Resource Title")
            resource_link = st.text_input("Resource Link (URL)")

            uploaded_file = st.file_uploader(
                "Upload a file (optional)",
                type=["pdf", "docx", "xlsx", "png", "jpg"],
                key="resource_file"
            )

            submit = st.form_submit_button("Add Resource")

            if submit:
                if subject and resource_title and (resource_link or uploaded_file):
                    filename = None
                    if uploaded_file:
                        try:
                            upload_folder = "uploads"
                            os.makedirs(upload_folder, exist_ok=True)

                            file_path = os.path.join(upload_folder, uploaded_file.name)
                            with open(file_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            filename = file_path

                        except Exception as e:
                            st.error(f"Error saving file: {str(e)}")
                            filename = None

                    if insert_resource(subject, resource_title, resource_link, filename):
                        st.success("Resource added successfully!")
                        st.rerun()
                else:
                    st.error("Please provide the subject, resource title, and at least a link or file.")

    with tab2:
        resources = get_all_resources()
        if resources:
            search_term = st.text_input("Search resources (by subject or title):")

            df_resources = pd.DataFrame(resources)

            if search_term:
                mask = (
                    df_resources['subject'].str.contains(search_term, case=False, na=False) |
                    df_resources['title'].str.contains(search_term, case=False, na=False)
                )
                df_resources = df_resources[mask]

            subjects = df_resources['subject'].unique()

            for subject in sorted(subjects):
                with st.expander(f"{subject} ({len(df_resources[df_resources['subject'] == subject])} resources)"):
                    subject_resources = df_resources[df_resources['subject'] == subject]

                    for _, row in subject_resources.iterrows():
                        st.markdown("---")
                        st.markdown(f"**Title:** {row['title']}")

                        if row['link']:
                            st.markdown(f"**Link:** [{row['link']}]({row['link']})")

                        if row['filename']:
                            try:
                                if os.path.exists(row['filename']):
                                    with open(row['filename'], "rb") as file:
                                        st.download_button(
                                            label="Download File",
                                            data=file,
                                            file_name=os.path.basename(row['filename']),
                                            mime="application/octet-stream"
                                        )
                            except Exception as e:
                                st.error(f"Error accessing file: {str(e)}")

                        if st.button(f"Delete Resource {row['id']}", key=f"del_res_{row['id']}"):
                            if delete_resource(row['id']):
                                if row['filename'] and os.path.exists(row['filename']):
                                    try:
                                        os.remove(row['filename'])
                                    except Exception as e:
                                        st.error(f"Error deleting file: {str(e)}")
                                st.success(f"Resource {row['id']} deleted successfully!")
                                st.rerun()
        else:
            st.info("No resources added yet. Use the form above to add resources.")

def study_goals_page():
    st.title("Study Goals")
    st.subheader("Set and Track Your Study Targets")

    tab1, tab2 = st.tabs(["Add Goal", "View Goals"])

    with tab1:
        with st.form("goals_form"):
            description = st.text_input("Goal Description",
                placeholder="E.g., Complete Linear Algebra in 2 weeks")
            target_hours = st.number_input("Target Hours",
                min_value=0.0, step=0.5)
            initial_achieved = st.number_input("Initial Achieved Hours (Optional)",
                min_value=0.0, step=0.5)

            submit = st.form_submit_button("Add Goal")

            if submit:
                if description and target_hours > 0:
                    if insert_study_goal(description, target_hours, initial_achieved):
                        st.success("Study goal added successfully!")
                        st.rerun()
                else:
                    st.error("Please provide a valid goal description and target hours.")

    with tab2:
        goals = get_study_goals()
        if goals:
            df_goals = pd.DataFrame(goals)
            st.dataframe(df_goals.reset_index(drop=True))
            df_goals = df_goals.sort_values('achieved_hours', ascending=False)

            st.subheader("Overall Progress")
            total_target = df_goals['target_hours'].sum()
            total_achieved = df_goals['achieved_hours'].sum()
            overall_progress = (total_achieved / total_target * 100) if total_target > 0 else 0

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Target Hours", f"{total_target:.1f}")
            with col2:
                st.metric("Total Achieved Hours", f"{total_achieved:.1f}")
            with col3:
                st.metric("Overall Progress", f"{overall_progress:.1f}%")

            st.subheader("Individual Goals")
            for _, goal in df_goals.iterrows():
                with st.expander(f"Goal: {goal['description']}"):
                    progress = (goal['achieved_hours'] / goal['target_hours'] * 100) if goal['target_hours'] > 0 else 0

                    st.progress(min(float(progress) / 100, 1.0))

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Target Hours", f"{goal['target_hours']:.1f}")
                    with col2:
                        st.metric("Achieved Hours", f"{goal['achieved_hours']:.1f}")
                    with col3:
                        st.metric("Progress", f"{progress:.1f}%")

                    with st.form(f"update_goal_{goal['id']}"):
                        additional_hours = st.number_input(
                            "Add Hours",
                            min_value=0.0,
                            step=0.5,
                            key=f"add_hours_{goal['id']}"
                        )
                        update_col1, update_col2 = st.columns([1, 4])
                        with update_col1:
                            if st.form_submit_button("Update"):
                                if update_goal_achievement(goal['id'], additional_hours):
                                    st.success("Goal updated successfully!")
                                    st.rerun()

                        with update_col2:
                            if st.form_submit_button("Delete Goal"):
                                if delete_study_goal(goal['id']):
                                    st.success("Goal deleted successfully!")
                                    st.rerun()
        else:
            st.info("No study goals set yet. Use the form above to add goals.")

def calendar_view_page():
    st.title("Calendar View")
    st.subheader("Interactive Study Calendar")

    try:
        logs_response = supabase.table('progress_logs').select('*').order('date').execute()

        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study sessions logged yet. Start logging your study sessions to view them here.")
            return

        df_logs = pd.DataFrame(logs_response.data)

        df_logs['date'] = pd.to_datetime(df_logs['date'])

        if len(df_logs) == 0:
            st.warning("No study sessions found. Please log some study sessions first.")
            return

        col1, col2 = st.columns([1, 2])

        with col1:
            today = pd.Timestamp.now()
            min_date = df_logs['date'].min()
            max_date = df_logs['date'].max()

            date_range = pd.date_range(
                start=min_date.replace(day=1),
                end=max_date + pd.offsets.MonthEnd(0),
                freq='M'
            )

            month_options = [d.strftime('%B %Y') for d in date_range]

            if not month_options:
                month_options = [today.strftime('%B %Y')]

            selected_month_str = st.selectbox(
                "Select Month",
                options=month_options,
                index=len(month_options)-1
            )

            selected_month = pd.to_datetime(selected_month_str + "-01")

        with col2:
            view_type = st.radio(
                "View Type",
                ["Monthly Calendar", "Daily List", "Weekly Summary"],
                horizontal=True
            )

        month_mask = (
            (df_logs['date'].dt.year == selected_month.year) &
            (df_logs['date'].dt.month == selected_month.month)
        )
        month_data = df_logs[month_mask]

        if view_type == "Monthly Calendar":
            st.markdown("### Monthly Calendar")

            first_day = selected_month.replace(day=1)
            last_day = (first_day + pd.offsets.MonthEnd(0))

            current_date = first_day - pd.Timedelta(days=first_day.weekday())

            cols = st.columns(7)
            for i, day in enumerate(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']):
                cols[i].markdown(f"**{day}**", help="Click for daily details")

            while current_date <= last_day + pd.Timedelta(days=6):
                cols = st.columns(7)
                for i in range(7):
                    with cols[i]:
                        if current_date.month == selected_month.month:
                            day_data = month_data[month_data['date'].dt.date == current_date.date()]
                            total_hours = day_data['hours'].sum()
                            subjects = day_data['subject'].nunique()

                            if len(day_data) > 0:
                                st.markdown(
                                    f"""
                                    <div style="
                                        padding: 10px;
                                        border: 1px solid #ddd;
                                        border-radius: 5px;
                                        background-color: #f0f2f6;
                                        text-align: center;
                                    ">
                                        <h4>{current_date.day}</h4>
                                        <p>{total_hours:.1f}h<br>{subjects} subjects</p>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                                with st.expander("Details", expanded=False):
                                    st.dataframe(
                                        day_data[['subject', 'hours', 'notes']].reset_index(drop=True),
                                        height=100
                                    )
                            else:
                                st.markdown(
                                    f"""
                                    <div style="
                                        padding: 10px;
                                        border: 1px solid #eee;
                                        border-radius: 5px;
                                        text-align: center;
                                        color: #666;
                                    ">
                                        <h4>{current_date.day}</h4>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        else:
                            st.markdown("")
                    current_date += pd.Timedelta(days=1)

        elif view_type == "Daily List":
            st.markdown("### Daily Study Sessions")

            if len(month_data) == 0:
                st.info(f"No study sessions recorded for {selected_month_str}")
            else:
                for date in sorted(month_data['date'].dt.date.unique(), reverse=True):
                    day_data = month_data[month_data['date'].dt.date == date]
                    total_hours = day_data['hours'].sum()
                    subjects = day_data['subject'].nunique()

                    with st.expander(
                        f"{date.strftime('%A, %B %d')} - {total_hours:.1f}h ({subjects} subjects)"
                    ):
                        st.dataframe(
                            day_data[['subject', 'hours', 'phase', 'notes']].reset_index(drop=True)
                        )

        else:
            st.markdown("### Weekly Summary")

            if len(month_data) == 0:
                st.info(f"No study sessions recorded for {selected_month_str}")
            else:
                month_data['week'] = month_data['date'].dt.isocalendar().week
                weekly_summary = month_data.groupby('week').agg({
                    'hours': ['sum', 'count'],
                    'subject': 'nunique',
                    'date': 'nunique'
                }).reset_index()

                weekly_summary.columns = ['Week', 'Total Hours', 'Number of Sessions', 'Unique Subjects', 'Days Studied']

                st.dataframe(weekly_summary)

                fig = px.bar(
                    weekly_summary,
                    x='Week',
                    y='Total Hours',
                    title='Weekly Study Hours',
                    labels={'Total Hours': 'Hours', 'Week': 'Week of Month'}
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Monthly Statistics")
        col1, col2, col3, col4 = st.columns(4)

        total_hours = month_data['hours'].sum() if len(month_data) > 0 else 0
        study_days = len(month_data['date'].dt.date.unique()) if len(month_data) > 0 else 0
        subjects = month_data['subject'].nunique() if len(month_data) > 0 else 0
        avg_hours = total_hours / study_days if study_days > 0 else 0

        with col1:
            st.metric("Total Hours", f"{total_hours:.1f}")
        with col2:
            st.metric("Study Days", study_days)
        with col3:
            st.metric("Subjects Covered", subjects)
        with col4:
            st.metric("Avg Hours/Day", f"{avg_hours:.1f}")

        if len(month_data) > 0:
            daily_hours = month_data.groupby('date')['hours'].sum().reset_index()
            fig = px.line(
                daily_hours,
                x='date',
                y='hours',
                title='Daily Study Hours this Month',
                labels={'hours': 'Hours', 'date': 'Date'}
            )
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error in calendar view: {str(e)}")
        st.error("Detailed error information:")
        st.exception(e)
        return

def download_reports_page():
    st.title("Download Reports")
    st.subheader("Study Session Reports and Analytics")

    try:
        logs_response = supabase.table('progress_logs').select('*').order('date').execute()

        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study sessions available to download.")
            return

        logs = logs_response.data

        df_logs = pd.DataFrame(logs)
        df_logs['date'] = pd.to_datetime(df_logs['date'])

        st.header("Available Reports")

        basic_df = df_logs[['date', 'subject', 'phase', 'hours', 'notes']]
        st.dataframe(basic_df.reset_index(drop=True))

        csv_basic = basic_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Basic Study Log (CSV)",
            csv_basic,
            "study_sessions_basic.csv",
            "text/csv",
            key='download_basic'
        )

        subject_summary = df_logs.groupby('subject').agg({
            'hours': ['sum', 'mean', 'count'],
            'date': 'nunique'
        }).round(2)
        subject_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions', 'Number of Days']
        st.dataframe(subject_summary.reset_index())

        csv_subject = subject_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Subject Summary (CSV)",
            csv_subject,
            "subject_summary.csv",
            "text/csv",
            key='download_subject'
        )

        daily_summary = df_logs.groupby('date').agg({
            'hours': ['sum', 'count'],
            'subject': 'nunique'
        }).round(2)
        daily_summary.columns = ['Total Hours', 'Number of Sessions', 'Subjects Covered']
        st.dataframe(daily_summary.reset_index())

        csv_daily = daily_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Daily Summary (CSV)",
            csv_daily,
            "daily_summary.csv",
            "text/csv",
            key='download_daily'
        )

        phase_summary = df_logs.groupby('phase').agg({
            'hours': ['sum', 'mean', 'count'],
            'subject': 'nunique',
            'date': 'nunique'
        }).round(2)
        phase_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions',
                               'Unique Subjects', 'Number of Days']
        st.dataframe(phase_summary.reset_index())

        csv_phase = phase_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Phase Summary (CSV)",
            csv_phase,
            "phase_summary.csv",
            "text/csv",
            key='download_phase'
        )

        df_logs['month_year'] = df_logs['date'].dt.strftime('%Y-%m')
        monthly_summary = df_logs.groupby('month_year').agg({
            'hours': ['sum', 'mean', 'count'],
            'subject': 'nunique',
            'date': 'nunique'
        }).round(2)
        monthly_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions',
                                 'Unique Subjects', 'Number of Days']
        st.dataframe(monthly_summary.reset_index())

        csv_monthly = monthly_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Monthly Summary (CSV)",
            csv_monthly,
            "monthly_summary.csv",
            "text/csv",
            key='download_monthly'
        )

        comprehensive_data = {
            'study_sessions': df_logs,
            'subject_summary': subject_summary,
            'daily_summary': daily_summary,
            'phase_summary': phase_summary,
            'monthly_summary': monthly_summary
        }

        combined_csv_parts = []

        for section_name, df in comprehensive_data.items():
            combined_csv_parts.append(f"\n\n{section_name.upper()}\n")
            combined_csv_parts.append(df.to_csv())

        combined_csv = "\n".join(combined_csv_parts)

        st.download_button(
            "Download Comprehensive Report (CSV)",
            combined_csv.encode('utf-8'),
            "comprehensive_study_report.csv",
            "text/csv",
            key='download_comprehensive'
        )

        st.header("Overall Statistics")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Study Hours", f"{df_logs['hours'].sum():.1f}")
        with col2:
            st.metric("Total Sessions", len(df_logs))
        with col3:
            st.metric("Days Studied", df_logs['date'].nunique())
        with col4:
            avg_hours_per_day = df_logs['hours'].sum() / df_logs['date'].nunique()
            st.metric("Avg Hours/Day", f"{avg_hours_per_day:.1f}")

        st.header("Study Progress Visualizations")

        fig1 = px.line(
            df_logs.groupby('date')['hours'].sum().reset_index(),
            x='date',
            y='hours',
            title='Daily Study Hours'
        )
        st.plotly_chart(fig1, use_container_width=True)

        fig2 = px.pie(
            df_logs.groupby('subject')['hours'].sum().reset_index(),
            values='hours',
            names='subject',
            title='Study Hours by Subject'
        )
        st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.bar(
            df_logs.groupby('phase')['hours'].sum().reset_index(),
            x='phase',
            y='hours',
            title='Study Hours by Phase'
        )
        st.plotly_chart(fig3, use_container_width=True)

        monthly_progress = df_logs.groupby('month_year')['hours'].sum().reset_index()
        fig4 = px.bar(
            monthly_progress,
            x='month_year',
            y='hours',
            title='Monthly Study Progress'
        )
        st.plotly_chart(fig4, use_container_width=True)

    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")
        st.error("Detailed error information:")
        st.exception(e)
        return

def focus_timer_page():
    st.title("Focus Timer")
    st.subheader("Start a Pomodoro-Style Focus Timer")
    duration = st.number_input("Set timer duration (minutes)", min_value=1, max_value=60, value=25)
    if st.button("Start Timer"):
        placeholder = st.empty()
        total_seconds = duration * 60
        for seconds in range(total_seconds, -1, -1):
            mins, secs = divmod(seconds, 60)
            timer_format = f"{mins:02d}:{secs:02d}"
            placeholder.markdown(f"### {timer_format}")
            time.sleep(1)
        placeholder.markdown("### Time's up!")

def get_and_verify_token():
    """Prompts the user to enter a GitHub token and verifies it. Returns the verified token or None."""
    if "token" in st.session_state and st.session_state.token:
        return st.session_state.token

    token_input = st.text_input("Enter your GitHub Token:", type="password")

    if token_input:
        with st.spinner("Verifying token..."):
            try:
                headers = {
                    "Authorization": f"token {token_input}",
                    "Accept": "application/vnd.github.v3+json"
                }
                response = requests.get(
                    "https://api.github.com/user",
                    headers=headers
                )

                if response.status_code == 200:
                    st.success("Token verified successfully!")
                    st.session_state.token = token_input
                    return token_input
                else:
                    st.error(f"Token verification failed: ({response.status_code}) {response.json().get('message', 'Unknown error')}")
                    return None

            except Exception as e:
                st.error(f"Token verification error: {str(e)}")
                return None
    return None

def rag_assistant_page():
    st.title("RAG Assistant")
    st.subheader("Upload a PDF and ask questions about its visual content")

    token = get_and_verify_token()
    if not token:
        st.warning("Please enter and verify your GitHub token above to proceed.")
        return

    # Add clear button to top right
    col1, col2 = st.columns([6,1])
    with col2:
        if st.button("Clear 🗑️"):
            if 'pdf_processed' in st.session_state:
                del st.session_state['pdf_processed']
            if 'pdf_images' in st.session_state:
                del st.session_state['pdf_images']
            if 'pdf_name' in st.session_state:
                del st.session_state['pdf_name']
            if 'current_page' in st.session_state:
                del st.session_state['current_page']
            st.rerun()

    st.markdown("#### Upload Resource (PDF)")
    uploaded_file = st.file_uploader(
        "Upload a PDF file",
        type=["pdf"],
        key="rag_resource"
    )

    # Add model selection
    model_options = {
        "Llama-3.2-90B-Vision-Instruct": "Best for scanned documents with OCR capabilities",
        "gpt-4o": "Good for text-based PDFs and general visual analysis"
    }
    
    selected_model = st.selectbox(
        "Select AI Model",
        options=list(model_options.keys()),
        format_func=lambda x: f"{x} ({model_options[x]})",
        index=0  # Default to Llama model
    )

    if "pdf_processed" not in st.session_state:
        st.session_state.pdf_processed = False
        st.session_state.pdf_images = []
        st.session_state.pdf_name = ""
        st.session_state.current_page = 0

    if uploaded_file and st.button("Process PDF"):
        try:
            with st.spinner("Converting PDF to images..."):
                upload_folder = "uploads"
                images_folder = os.path.join(upload_folder, "images")
                os.makedirs(upload_folder, exist_ok=True)
                os.makedirs(images_folder, exist_ok=True)

                # Save the PDF file
                file_path = os.path.join(upload_folder, uploaded_file.name)
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # Use PyMuPDF for PDF to image conversion
                try:
                    import pymupdf
                    st.info("Converting PDF using PyMuPDF...")
                    
                    # Calculate zoom factor for 300 DPI (default PDF DPI is 72)
                    zoom_factor = 300 / 72
                    
                    # Open the PDF document
                    pdf_document = pymupdf.open(file_path)
                    image_paths = []
                    
                    # Get the base name of the PDF file (without extension)
                    base_name = os.path.splitext(uploaded_file.name)[0]
                    
                    # Process each page
                    for page_number in range(len(pdf_document)):
                        # Get the page
                        page = pdf_document[page_number]
                        
                        # Render page to an image (pixmap)
                        matrix = pymupdf.Matrix(zoom_factor, zoom_factor)
                        pixmap = page.get_pixmap(matrix=matrix)
                        
                        # Save the image
                        image_path = os.path.join(images_folder, f"{base_name}_page_{page_number+1}.jpg")
                        pixmap.save(image_path)
                        image_paths.append(image_path)
                    
                    # Close the PDF document
                    pdf_document.close()
                    
                    if image_paths:
                        st.session_state.pdf_processed = True
                        st.session_state.pdf_images = image_paths
                        st.session_state.pdf_name = uploaded_file.name
                        st.session_state.current_page = 0
                        st.success(f"PDF processed successfully: {uploaded_file.name} ({len(image_paths)} pages)")
                    else:
                        raise Exception("No images were generated")
                        
                except ImportError:
                    st.error("PyMuPDF is not installed. Please install it using: pip install pymupdf")
                    return
                except Exception as e:
                    st.error(f"Error processing PDF with PyMuPDF: {str(e)}")
                    return

        except Exception as e:
            st.error(f"Error processing PDF file: {str(e)}")
            st.exception(e)

    if st.session_state.pdf_processed and len(st.session_state.pdf_images) > 0:
        # Display page navigation
        col1, col2, col3 = st.columns([1, 3, 1])
        with col1:
            if st.button("Previous Page", disabled=st.session_state.current_page <= 0):
                st.session_state.current_page = max(0, st.session_state.current_page - 1)
                st.rerun()
        
        with col2:
            st.write(f"Page {st.session_state.current_page + 1} of {len(st.session_state.pdf_images)}")
        
        with col3:
            if st.button("Next Page", disabled=st.session_state.current_page >= len(st.session_state.pdf_images) - 1):
                st.session_state.current_page = min(len(st.session_state.pdf_images) - 1, st.session_state.current_page + 1)
                st.rerun()
        
        # Display the current page image
        current_image_path = st.session_state.pdf_images[st.session_state.current_page]
        st.image(current_image_path, caption=f"Page {st.session_state.current_page + 1}", use_container_width=True)

        # Add text extraction button
        if st.button("Extract Text 🔍", type="primary"):
            with st.spinner("Processing image with Azure AI Vision..."):
                try:
                    # Initialize Azure AI client
                    client = ChatCompletionsClient(
                        endpoint="https://models.inference.ai.azure.com",
                        credential=AzureKeyCredential(token),
                        api_version="2024-12-01-preview"
                    )

                    # Read the current image
                    with open(current_image_path, "rb") as img_file:
                        import base64
                        image_data = base64.b64encode(img_file.read()).decode('utf-8')

                    # Create system message based on selected model
                    if selected_model == "Llama-3.2-90B-Vision-Instruct":
                        system_message = SystemMessage(
                            "You are an expert assistant for analyzing document content from images. "
                            "The user has uploaded a scanned PDF that has been converted to images. "
                            "Use your OCR capabilities to read and understand the text in the image. "
                            "Pay attention to both text and visual elements in the document. "
                            "Be precise and thorough in your analysis."
                        )
                    else:  # GPT-4o
                        system_message = SystemMessage(
                            "You are an expert assistant for analyzing document content from images. "
                            "The user has uploaded a PDF that has been converted to images with text content. "
                            "Please analyze the image content and answer questions about it accurately and helpfully. "
                            "The PDF has been processed to extract text only, so focus on the textual content."
                        )

                    # Create user message with image
                    user_message_with_image = UserMessage(
                        content=[
                            TextContentItem("Please analyze this image and extract all readable content in a structured format."),
                            ImageContentItem(
                                image_url=ImageUrl(
                                    url=f"data:image/jpeg;base64,{image_data}",
                                    detail=ImageDetailLevel.HIGH
                                )
                            )
                        ]
                    )

                    # Get response from Azure AI
                    response = client.complete(
                        messages=[system_message, user_message_with_image],
                        model=selected_model,
                        temperature=0.7,
                        max_tokens=1000
                    )

                    # Store the extracted text in session state
                    if 'extracted_text' not in st.session_state:
                        st.session_state.extracted_text = {}
                    st.session_state.extracted_text[st.session_state.current_page] = response.choices[0].message.content
                    
                    # Display the extracted text
                    st.markdown("### Extracted Text")
                    st.markdown(response.choices[0].message.content)
                    
                except Exception as e:
                    st.error(f"Error processing image: {str(e)}")

        # Display previously extracted text if available
        if 'extracted_text' in st.session_state and st.session_state.current_page in st.session_state.extracted_text:
            st.markdown("### Previously Extracted Text")
            st.markdown(st.session_state.extracted_text[st.session_state.current_page])

    user_query = st.text_input(
        "Enter your question about the PDF content:"
    )

    if st.button("Ask Question") and user_query and st.session_state.pdf_processed and len(st.session_state.pdf_images) > 0:
        try:
            with st.spinner("Processing your question with Azure AI Vision..."):
                # Initialize Azure AI client
                client = ChatCompletionsClient(
                    endpoint="https://models.inference.ai.azure.com",
                    credential=AzureKeyCredential(token),
                    api_version="2024-12-01-preview"
                )

                # Read the current image
                current_image_path = st.session_state.pdf_images[st.session_state.current_page]
                with open(current_image_path, "rb") as img_file:
                    import base64
                    image_data = base64.b64encode(img_file.read()).decode('utf-8')

                # Create system message based on selected model
                if selected_model == "Llama-3.2-90B-Vision-Instruct":
                    system_message = SystemMessage(
                        "You are an expert assistant for analyzing document content from images. "
                        "The user has uploaded a scanned PDF that has been converted to images. "
                        "Use your OCR capabilities to read and understand the text in the image. "
                        "Pay attention to both text and visual elements in the document. "
                        "Be precise and thorough in your analysis."
                    )
                else:  # GPT-4o
                    system_message = SystemMessage(
                        "You are an expert assistant for analyzing document content from images. "
                        "The user has uploaded a PDF that has been converted to images with text content. "
                        "Please analyze the image content and answer questions about it accurately and helpfully. "
                        "The PDF has been processed to extract text only, so focus on the textual content."
                    )

                # Create user message with image and question
                user_message_with_image = UserMessage(
                    content=[
                        TextContentItem(f"Based on the content in this image, please answer this question: {user_query}"),
                        ImageContentItem(
                            image_url=ImageUrl(
                                url=f"data:image/jpeg;base64,{image_data}",
                                detail=ImageDetailLevel.HIGH
                            )
                        )
                    ]
                )

                # Get response from Azure AI
                response = client.complete(
                    messages=[system_message, user_message_with_image],
                    model=selected_model,
                    temperature=0.7,
                    max_tokens=1000
                )
                
                # Display the response
                st.markdown("### Response")
                st.markdown(response.choices[0].message.content)

        except Exception as e:
            st.error(f"Error processing question: {str(e)}")
            st.exception(e)

    # Footer
    st.markdown("---")
    st.markdown("Made with ❤️ using Azure AI Vision Models")

def chat_assistant_page():
    st.title("Chat Assistant")
    st.subheader("Talk to your study data assistant using OpenAI o3-mini (GitHub-hosted)!")

    token = get_and_verify_token()
    if not token:
        st.warning("Please enter and verify your GitHub token above to start chatting.")
        return

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

    user_input = st.chat_input("Enter your message:")

    if user_input:
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input
        })

        with st.chat_message("user"):
            st.write(user_input)

        try:
            client = ChatCompletionsClient(
                endpoint="https://models.inference.ai.azure.com",
                credential=AzureKeyCredential(token),
                api_version="2024-12-01-preview"
            )

            messages = [
                SystemMessage("You are a helpful study assistant."),
                *[UserMessage(msg["content"]) if msg["role"] == "user"
                  else AssistantMessage(msg["content"])
                  for msg in st.session_state.chat_history]
            ]

            with st.spinner("Thinking..."):
                response = client.complete(
                    messages=messages,
                    model="o3-mini"
                )

                assistant_reply = response.choices[0].message.content

                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": assistant_reply
                })

                with st.chat_message("assistant"):
                    st.write(assistant_reply)

        except Exception as e:
            st.error(f"Error: {str(e)}")

def main():
    load_css()

    pages = {
        "Dashboard": dashboard_page,
        "Study Planner": study_planner_page,
        "Progress Analytics": analytics_page,
        "Revision Hub": revision_hub_page,
        "Question Bank": question_bank_page,
        "Resources": resources_page,
        "Study Goals": study_goals_page,
        "Calendar View": calendar_view_page,
        "Download Reports": download_reports_page,
        "Focus Timer": focus_timer_page,
        "Chat Assistant": chat_assistant_page,
        "RAG Assistant": rag_assistant_page
    }

    selection = st.sidebar.radio("Navigation", list(pages.keys()))

    load_page_specific_css(selection)

    pages[selection]()

if __name__ == '__main__':
    set_favicon()
    main()
    