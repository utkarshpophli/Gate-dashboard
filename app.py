import os
import json
import sqlite3
import time
import datetime
import requests
import random
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from azure.ai.inference import ChatCompletionsClient
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

load_dotenv()

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

# ============================
# 1. Database Setup & Helpers
# ============================

DB_FILE = "data_hub.db"

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create progress_logs table
    c.execute("""
        CREATE TABLE IF NOT EXISTS progress_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            phase TEXT NOT NULL,
            subject TEXT NOT NULL,
            hours REAL NOT NULL,
            notes TEXT
        )
    """)
    # Create schedule table
    c.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            phase TEXT PRIMARY KEY,
            title TEXT,
            focus TEXT,
            schedule_json TEXT
        )
    """)
    # Create question_bank table (for GateOverflow questions)
    c.execute("""
        CREATE TABLE IF NOT EXISTS question_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT
        )
    """)
    # Create resources table (for uploaded PDFs/images)
    c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            title TEXT,
            link TEXT,
            filename TEXT
        )
    """)
    # Create study_goals table
    c.execute("""
        CREATE TABLE IF NOT EXISTS study_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT,
            target_hours REAL,
            achieved_hours REAL
        )
    """)
    # Create revision_notes table
    c.execute("""
        CREATE TABLE IF NOT EXISTS revision_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            short_notes TEXT,
            formula TEXT
        )
    """)
    conn.commit()
    
    # Insert default schedule data if not already present.
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
    
    for phase, details in default_phases.items():
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM schedule WHERE phase = ?", (phase,))
        if c.fetchone()[0] == 0:
            c.execute("""
                INSERT INTO schedule (phase, title, focus, schedule_json)
                VALUES (?, ?, ?, ?)
            """, (phase, details["title"], details["focus"], json.dumps(details["table"])))
    conn.commit()
    conn.close()

init_db()  # Initialize database/tables

# -----------------------
# 2. Database CRUD Helpers
# -----------------------

def insert_progress_log(date_str, phase, subject, hours, notes):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO progress_logs (date, phase, subject, hours, notes) VALUES (?, ?, ?, ?, ?)",
              (date_str, phase, subject, hours, notes))
    conn.commit()
    conn.close()

def get_progress_logs():
    conn = get_db_connection()
    c = conn.cursor()
    logs = c.execute("SELECT * FROM progress_logs ORDER BY date").fetchall()
    conn.close()
    return logs

def update_schedule_db(phase, new_table):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE schedule SET schedule_json = ? WHERE phase = ?",
              (json.dumps(new_table), phase))
    conn.commit()
    conn.close()

def get_all_schedules():
    conn = get_db_connection()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM schedule").fetchall()
    conn.close()
    schedules = {}
    for row in rows:
        schedules[row["phase"]] = {
            "title": row["title"],
            "focus": row["focus"],
            "table": json.loads(row["schedule_json"])
        }
    return schedules

def insert_question(subject, question, answer):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO question_bank (subject, question, answer) VALUES (?, ?, ?)",
              (subject, question, answer))
    conn.commit()
    conn.close()

def get_all_questions():
    conn = get_db_connection()
    c = conn.cursor()
    questions = c.execute("SELECT * FROM question_bank").fetchall()
    conn.close()
    return questions

def insert_resource(subject, title, link, filename):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO resources (subject, title, link, filename) VALUES (?, ?, ?, ?)",
              (subject, title, link, filename))
    conn.commit()
    conn.close()

def get_all_resources():
    conn = get_db_connection()
    c = conn.cursor()
    resources = c.execute("SELECT * FROM resources").fetchall()
    conn.close()
    return resources

def insert_study_goal(description, target_hours, achieved_hours=0):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO study_goals (description, target_hours, achieved_hours) VALUES (?, ?, ?)",
              (description, target_hours, achieved_hours))
    conn.commit()
    conn.close()

def get_study_goals():
    conn = get_db_connection()
    c = conn.cursor()
    goals = c.execute("SELECT * FROM study_goals").fetchall()
    conn.close()
    return goals

def update_goal_achievement(goal_id, additional_hours):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE study_goals SET achieved_hours = achieved_hours + ? WHERE id = ?",
              (additional_hours, goal_id))
    conn.commit()
    conn.close()

def insert_revision_note(subject, short_notes, formula):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO revision_notes (subject, short_notes, formula) VALUES (?, ?, ?)",
              (subject, short_notes, formula))
    conn.commit()
    conn.close()

def get_revision_notes():
    conn = get_db_connection()
    c = conn.cursor()
    notes = c.execute("SELECT * FROM revision_notes").fetchall()
    conn.close()
    return notes

# ------------------------
# 3. Global Lists for Dropdowns
# ------------------------

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

# ------------------------
# 4. Utility Functions for RAG
# ------------------------

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
    elif ext in ["png", "jpg", "jpeg"] and Image and pytesseract:
        try:
            image = Image.open(file_path)
            extracted_text = pytesseract.image_to_string(image)
        except Exception as e:
            extracted_text += f"[Error extracting image text: {e}]"
    return extracted_text

def get_rag_context(selected_subject):
    """Combine text from question bank, revision notes, and resources for a given subject."""
    context_parts = []
    # Questions from question bank
    questions = get_all_questions()
    subject_questions = [q for q in questions if q["subject"].lower() == selected_subject.lower()]
    if subject_questions:
        q_text = "\n".join([f"Q: {q['question']}\nA: {q['answer'] if q['answer'] else 'No answer provided'}" 
                             for q in subject_questions])
        context_parts.append("Question Bank:\n" + q_text)
    
    # Revision notes
    notes = get_revision_notes()
    subject_notes = [n for n in notes if n["subject"].lower() == selected_subject.lower()]
    if subject_notes:
        n_text = "\n".join([f"Note: {n['short_notes']}\nFormula: {n['formula']}" for n in subject_notes])
        context_parts.append("Revision Notes:\n" + n_text)
    
    # Resources (uploaded PDFs/images)
    resources = get_all_resources()
    subject_resources = [r for r in resources if r["subject"] and r["subject"].lower() == selected_subject.lower() and r["filename"]]
    for r in subject_resources:
        extracted = extract_text_from_file(r["filename"])
        if extracted:
            context_parts.append(f"Resource ({r['title']}):\n" + extracted)
    
    return "\n\n".join(context_parts)

# ------------------------
# 5. Streamlit App Pages
# ------------------------


def dashboard_page():
    st.title("GATE DA 2026 Dashboard")
    st.subheader("Overview of Your Study Progress")
    
    st.header("Log a Study Session")
    with st.form("study_session_form"):
        session_date = st.date_input("Date", datetime.date.today())
        phase_options = list(get_all_schedules().keys())
        selected_phase = st.selectbox("Select Phase", phase_options)
        selected_subject = st.selectbox("Select Subject", SUBJECT_LIST)
        hours = st.number_input("Hours Studied", min_value=0.0, step=0.5)
        notes = st.text_area("Notes / Reflection")
        submitted = st.form_submit_button("Log Session")
        if submitted:
            date_str = session_date.strftime("%Y-%m-%d")
            insert_progress_log(date_str, selected_phase, selected_subject, hours, notes)
            goals = get_study_goals()
            for goal in goals:
                update_goal_achievement(goal["id"], hours)
            st.success("Study session logged!")
    
    st.header("Study Sessions Log")
    logs = get_progress_logs()
    if logs:
        df_logs = pd.DataFrame(logs, columns=logs[0].keys())
        st.dataframe(df_logs)
    else:
        st.info("No study sessions logged yet.")
    
    st.header("Progress Summary")
    if logs:
        df_logs = pd.DataFrame(logs, columns=logs[0].keys())
        total_hours = df_logs["hours"].sum()
        st.write(f"**Total Hours Studied:** {total_hours} hours")

        # Existing phase summary
        phase_hours = df_logs.groupby("phase")["hours"].sum().reset_index()
        st.table(phase_hours)

        # NEW: Subject Summary Table
        df_logs["date"] = pd.to_datetime(df_logs["date"])
        subject_summary = df_logs.groupby("subject").agg(
            total_hours=("hours", "sum"),
            days_studied=("date", "nunique"),
            start_date=("date", "min"),
            end_date=("date", "max")
        ).reset_index()
        # Calculate total duration for each subject
        subject_summary["duration_days"] = (
            subject_summary["end_date"] - subject_summary["start_date"]
        ).dt.days + 1

        st.header("Subject Summary:")
        st.dataframe(subject_summary)

    else:
        st.write("Log your study sessions to see progress summary.")

def analytics_page():
    st.title("Progress Analytics")
    st.subheader("Visualize Your Study Progress with Different Analyses")
    
    logs = get_progress_logs()
    if not logs:
        st.info("No study session data available for analytics.")
        return
    
    # Convert logs to DataFrame and sort by date
    df_logs = pd.DataFrame(logs, columns=logs[0].keys())
    df_logs["date"] = pd.to_datetime(df_logs["date"])
    df_logs.sort_values("date", inplace=True)

    # Create a dropdown to select the type of analysis
    analysis_options = ["Overall Progress", "By Subject", "By Week", "By Month", "By Phase"]
    selected_analysis = st.selectbox("Select Analysis Type", analysis_options)

    if selected_analysis == "Overall Progress":
        st.markdown("### Cumulative Hours Over Time")
        df_logs["cumulative_hours"] = df_logs["hours"].cumsum()
        st.line_chart(df_logs.set_index("date")["cumulative_hours"])

        st.markdown("### Study Hours by Weekday")
        df_logs["weekday"] = df_logs["date"].dt.day_name()
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday_hours = df_logs.groupby("weekday")["hours"].sum().reindex(order).reset_index()
        fig_bar = px.bar(
            weekday_hours,
            x="weekday",
            y="hours",
            title="Hours Studied per Weekday"
        )
        st.plotly_chart(fig_bar)

    elif selected_analysis == "By Subject":
        st.markdown("### Study Hours by Subject")
        subject_hours = df_logs.groupby("subject")["hours"].sum().reset_index()
        fig_subj = px.bar(
            subject_hours,
            x="subject",
            y="hours",
            title="Hours Studied by Subject"
        )
        st.plotly_chart(fig_subj)

    elif selected_analysis == "By Week":
        st.markdown("### Study Hours by Week (ISO Week Number)")
        df_logs["week"] = df_logs["date"].dt.isocalendar().week
        weekly_hours = df_logs.groupby("week")["hours"].sum().reset_index()
        fig_week = px.line(
            weekly_hours,
            x="week",
            y="hours",
            title="Hours Studied by Week"
        )
        st.plotly_chart(fig_week)

    elif selected_analysis == "By Month":
        st.markdown("### Study Hours by Month")
        # Convert date to a monthly period (YYYY-MM)
        df_logs["month"] = df_logs["date"].dt.to_period("M")
        monthly_hours = df_logs.groupby("month")["hours"].sum().reset_index()
        # Convert period to string for plotting
        monthly_hours["month"] = monthly_hours["month"].astype(str)
        fig_month = px.bar(
            monthly_hours,
            x="month",
            y="hours",
            title="Hours Studied by Month"
        )
        st.plotly_chart(fig_month)

    elif selected_analysis == "By Phase":
        st.markdown("### Study Hours by Phase")
        phase_hours = df_logs.groupby("phase")["hours"].sum().reset_index()
        fig_pie = px.pie(
            phase_hours,
            names="phase",
            values="hours",
            title="Study Hours by Phase"
        )
        st.plotly_chart(fig_pie)

def study_planner_page():
    st.title("Study Planner")
    st.subheader("Plan and View Your Schedule for Each Phase")
    schedules = get_all_schedules()
    phase_keys = list(schedules.keys())
    tabs = st.tabs(phase_keys)
    for i, phase in enumerate(phase_keys):
        with tabs[i]:
            phase_info = schedules[phase]
            st.write(f"**Title:** {phase_info['title']}")
            st.write(f"**Focus:** {phase_info['focus']}")
            st.write("**Schedule:**")
            df_phase = pd.DataFrame(phase_info["table"], columns=["Day", "Time Slot", "Activity", "Details"])
            if hasattr(st, "experimental_data_editor"):
                edited_df = st.experimental_data_editor(df_phase, num_rows="dynamic", key=phase)
                if st.button("Save changes", key=f"save_{phase}"):
                    update_schedule_db(phase, edited_df.values.tolist())
                    st.success(f"Schedule for {phase} saved!")
            else:
                st.dataframe(df_phase)

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
        # Save uploaded file as a resource (subject can be chosen or left NULL)
        subject_for_resource = st.text_input("Enter subject for this resource (optional)")
        title = st.text_input("Enter title for this resource (optional)", value=uploaded_file.name)
        insert_resource(subject_for_resource, title, "", file_path)
        st.success("Resource uploaded and saved!")

def question_bank_page():
    st.title("Question Bank")
    st.subheader("Store and Review Questions & Patterns by Subject")
    with st.form("question_bank_form"):
        subject = st.text_input("Subject")
        question_text = st.text_area("Question")
        answer_text = st.text_area("Answer / Pattern (optional)")
        submit = st.form_submit_button("Add Question")
        if submit:
            if subject and question_text:
                insert_question(subject, question_text, answer_text)
                st.success("Question added!")
            else:
                st.error("Please provide both a subject and a question.")
    questions = get_all_questions()
    if questions:
        df_q = pd.DataFrame(questions, columns=questions[0].keys())
        st.dataframe(df_q)
    else:
        st.info("No questions added yet.")

def resources_page():
    st.title("Resources")
    st.subheader("Store Resource Links and Files")
    with st.form("resources_form"):
        subject = st.text_input("Subject")
        resource_title = st.text_input("Resource Title")
        resource_link = st.text_input("Resource Link (URL)")
        uploaded_file = st.file_uploader("Upload a file (optional)",
                                         type=["pdf", "docx", "xlsx", "png", "jpg"],
                                         key="resource_file")
        submit = st.form_submit_button("Add Resource")
        if submit:
            if subject and resource_title and (resource_link or uploaded_file):
                filename = None
                if uploaded_file is not None:
                    upload_folder = "uploads"
                    if not os.path.exists(upload_folder):
                        os.makedirs(upload_folder)
                    file_path = os.path.join(upload_folder, uploaded_file.name)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    filename = file_path
                insert_resource(subject, resource_title, resource_link, filename)
                st.success("Resource added!")
            else:
                st.error("Please provide the subject, resource title, and at least a link or file.")
    resources = get_all_resources()
    if resources:
        df_res = pd.DataFrame(resources, columns=resources[0].keys())
        st.dataframe(df_res)
    else:
        st.info("No resources added yet.")

def study_goals_page():
    st.title("Study Goals")
    st.subheader("Set and Track Your Study Targets")
    with st.form("goals_form"):
        description = st.text_input("Goal Description", "E.g., Study 50 hours in November")
        target_hours = st.number_input("Target Hours", min_value=0.0, step=1.0)
        submit = st.form_submit_button("Add Goal")
        if submit:
            if description and target_hours > 0:
                insert_study_goal(description, target_hours)
                st.success("Study goal added!")
            else:
                st.error("Please provide a valid goal description and target hours.")
    goals = get_study_goals()
    if goals:
        st.markdown("### Current Study Goals")
        for goal in goals:
            achieved = goal["achieved_hours"]
            target = goal["target_hours"]
            progress = (achieved / target * 100) if target else 0
            st.write(f"**{goal['description']}**")
            st.progress(min(int(progress), 100))
            st.write(f"{achieved:.1f} / {target:.1f} hours achieved")
    else:
        st.info("No study goals set yet.")

def calendar_view_page():
    st.title("Calendar View")
    st.subheader("View Your Study Sessions Grouped by Date")
    logs = get_progress_logs()
    if logs:
        df_logs = pd.DataFrame(logs, columns=logs[0].keys())
        df_logs['date'] = pd.to_datetime(df_logs['date'])
        grouped = df_logs.groupby(df_logs['date'].dt.date)
        for d, group in grouped:
            with st.expander(f"{d} - {len(group)} session(s)"):
                st.dataframe(group)
    else:
        st.info("No study sessions logged yet.")

def download_reports_page():
    st.title("Download Reports")
    st.subheader("Download Your Study Sessions Data as CSV")
    logs = get_progress_logs()
    if logs:
        df_logs = pd.DataFrame(logs, columns=logs[0].keys())
        csv = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, "study_sessions.csv", "text/csv")
    else:
        st.info("No study sessions available to download.")

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

# ------------------------
# New Combined Page: RAG Assistant
# ------------------------

def rag_assistant_page():
    st.title("RAG Assistant")
    st.subheader("Ask for subject/topic questions and revision points – all through a prompt!")
    
    # Let the user select a subject
    selected_subject = st.selectbox("Select Subject", SUBJECT_LIST)
    
    # Optional: File upload for additional revision resources (PDF/Image)
    st.markdown("#### Upload Revision Resource (PDF or Image)")
    uploaded_file = st.file_uploader("Upload a file", type=["pdf", "png", "jpg", "jpeg"], key="rag_resource")
    additional_messages = []  # List to hold any extra messages for the model
    
    if uploaded_file:
        upload_folder = "uploads"
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        file_path = os.path.join(upload_folder, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Resource uploaded!")
        
        ext = uploaded_file.name.split('.')[-1].lower()
        if ext in ["png", "jpg", "jpeg"]:
            try:
                # Create an image message using Azure AI Inference's types
                image_url = ImageUrl.load(
                    image_file=file_path,
                    image_format=ext,
                    detail=ImageDetailLevel.LOW
                )
                additional_messages.append(ImageContentItem(image_url=image_url))
            except Exception as e:
                st.error(f"Error processing image: {e}")
        elif ext == "pdf":
            # Attempt to extract text using your OCR function
            extracted_text = extract_text_from_file(file_path)
            # Define a list of keywords expected for relevance (e.g., for Linear Algebra)
            expected_keywords = ['linear algebra', 'matrix', 'vector', 'eigen']
            if not any(keyword in extracted_text.lower() for keyword in expected_keywords):
                # If text extraction is insufficient, instruct the model to use its vision model
                additional_messages.append(
                    UserMessage("The extracted text from the PDF is insufficient or not relevant. Please apply your vision model to analyze the document visually and extract key data (such as diagrams, tables, or section headings) that are pertinent to the subject.")
                )
            else:
                additional_messages.append(
                    UserMessage(f"Extracted text from PDF: {extracted_text}")
                )
    
    # Build retrieval context from your database (e.g., revision notes, Q&A, etc.)
    retrieval_context = get_rag_context(selected_subject)
    
    # Build the prompt message combining retrieval context and user query placeholder
    prompt_text = (
        f"You are an expert revision assistant for the GATE exam.\n"
        f"Subject: {selected_subject}\n"
        f"Retrieved Context:\n{retrieval_context}\n"
        f"User Query: "
    )
    user_query = st.text_input("Enter your query (e.g., 'Give me daily revision points for Calculus'):")
    
    if user_query:
        # Prepare the message sequence to send to the model
        messages = [
            SystemMessage(prompt_text),
            UserMessage(user_query)
        ]
        if additional_messages:
            messages.extend(additional_messages)
        
        # Retrieve your GitHub token (PAT) from the environment
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            st.error("GitHub token not found in environment variables.")
            return
        
        # Configure the client for the RAG model (Llama-3.2-90B-Vision-Instruct)
        endpoint = "https://models.inference.ai.azure.com"
        model_name = "Llama-3.2-90B-Vision-Instruct"
        
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
            api_version="2024-12-01-preview"
        )
        
        with st.spinner("Generating response..."):
            try:
                response = client.complete(
                    messages=messages,
                    temperature=1.0,
                    top_p=1.0,
                    max_tokens=1000,
                    model=model_name
                )
                rag_reply = response.choices[0].message.content
                st.markdown("### RAG Assistant Response")
                st.markdown(rag_reply)
            except Exception as e:
                st.error(f"Error generating response: {e}")

def chat_assistant_page():
    st.title("Chat Assistant")
    st.subheader("Talk to your study data assistant using OpenAI o3-mini (GitHub-hosted)!")
    
    # Initialize chat history if not present
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Display previous conversation
    for msg in st.session_state.chat_history:
        st.chat_message(msg["role"]).write(msg["content"])
    
    user_input = st.chat_input("Enter your message:")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.chat_message("user").write(user_input)
        
        # Build messages for the conversation (include system prompt and history)
        messages = [SystemMessage("You are a helpful assistant who knows about my study sessions.")]
        for entry in st.session_state.chat_history:
            if entry["role"] == "user":
                messages.append(UserMessage(entry["content"]))
            else:
                messages.append(AssistantMessage(entry["content"]))
        
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            st.error("GitHub token not found in environment variables.")
            return
        
        # Configure the client for the chat model (o3-mini)
        endpoint = "https://models.inference.ai.azure.com"
        model_name = "o3-mini"
        
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(token),
            api_version="2024-12-01-preview"
        )
        
        with st.spinner("Generating response..."):
            try:
                response = client.complete(
                    messages=messages,
                    temperature=1.0,
                    top_p=1.0,
                    # max_tokens=1000,
                    model=model_name
                )
                assistant_reply = response.choices[0].message.content
                st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply})
                st.chat_message("assistant").write(assistant_reply)
            except Exception as e:
                st.error(f"Error generating response: {e}")

# ------------------------
# 6. Main App Navigation
# ------------------------

def main():
    st.set_page_config(page_title="GATE DA 2026 Dashboard", layout="wide")
    
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
        "RAG Assistant": rag_assistant_page  # Combined RAG page
    }
    
    selection = st.sidebar.radio("Navigation", list(pages.keys()))
    pages[selection]()

if __name__ == '__main__':
    main()