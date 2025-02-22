import os
import json
import sqlite3
import time
import datetime
import requests
import random
import pandas as pd
from io import BytesIO
import plotly.express as px
import streamlit as st
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

load_dotenv()
# engine = sqlalchemy.create_engine(DATABASE_URL)
supabase: Client = create_client(
    supabase_url=st.secrets["SUPABASE_URL"],
    supabase_key=st.secrets["SUPABASE_KEY"]
)
st.set_page_config(page_title="GATE DA 2026 Dashboard", layout="wide")

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

# DB_FILE = "data_hub.db"

# def get_db_connection():
#     """
#     Creates and returns a connection to your Supabase PostgreSQL database.
#     Ensure your DATABASE_URL in your Streamlit secrets is formatted like:
#       postgresql://username:password@host:port/dbname
#     """
#     DATABASE_URL = st.secrets["SUPABASE_URL"]
#     engine = create_engine(DATABASE_URL)
#     return engine.connect()

CREATE_TABLES_SQL = """
-- Create progress_logs table
CREATE TABLE IF NOT EXISTS progress_logs (
    id SERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    phase TEXT NOT NULL,
    subject TEXT NOT NULL,
    hours REAL NOT NULL,
    notes TEXT
);

-- Create schedule table
CREATE TABLE IF NOT EXISTS schedule (
    phase TEXT PRIMARY KEY,
    title TEXT,
    focus TEXT,
    schedule_json TEXT
);

-- Create question_bank table
CREATE TABLE IF NOT EXISTS question_bank (
    id SERIAL PRIMARY KEY,
    subject TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT
);

-- Create resources table
CREATE TABLE IF NOT EXISTS resources (
    id SERIAL PRIMARY KEY,
    subject TEXT,
    title TEXT,
    link TEXT,
    filename TEXT
);

-- Create study_goals table
CREATE TABLE IF NOT EXISTS study_goals (
    id SERIAL PRIMARY KEY,
    description TEXT,
    target_hours REAL,
    achieved_hours REAL
);

-- Create revision_notes table
CREATE TABLE IF NOT EXISTS revision_notes (
    id SERIAL PRIMARY KEY,
    subject TEXT NOT NULL,
    short_notes TEXT,
    formula TEXT
);
"""

def init_db():
    """Initializes the Supabase database by creating tables and inserting default schedule data."""
    try:
        # conn = get_db_connection()
        # Create tables
        # conn.execute(text(CREATE_TABLES_SQL))
        
        # Default schedule data (default phases)
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
        
        # Insert default schedule data if not already present
         # Insert default schedule data if not present
        # Insert default phases if they don't exist
        # Check and insert default phases
        for phase, details in default_phases.items():
            # Check if phase exists
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
        
# Initialize the database when the app starts
# init_db()
        
# def init_db():
#     conn = get_db_connection()
#     conn.execute("""
#         CREATE TABLE IF NOT EXISTS progress_logs (
#             id SERIAL PRIMARY KEY,
#             date TEXT NOT NULL,
#             phase TEXT NOT NULL,
#             subject TEXT NOT NULL,
#             hours REAL NOT NULL,
#             notes TEXT
#         );
#     """)
#     # Create schedule table
#     c.execute("""
#         CREATE TABLE IF NOT EXISTS schedule (
#             phase TEXT PRIMARY KEY,
#             title TEXT,
#             focus TEXT,
#             schedule_json TEXT
#         )
#     """)
#     # Create question_bank table (for GateOverflow questions)
#     c.execute("""
#         CREATE TABLE IF NOT EXISTS question_bank (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             subject TEXT NOT NULL,
#             question TEXT NOT NULL,
#             answer TEXT
#         )
#     """)
#     # Create resources table (for uploaded PDFs/images)
#     c.execute("""
#         CREATE TABLE IF NOT EXISTS resources (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             subject TEXT,
#             title TEXT,
#             link TEXT,
#             filename TEXT
#         )
#     """)
#     # Create study_goals table
#     c.execute("""
#         CREATE TABLE IF NOT EXISTS study_goals (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             description TEXT,
#             target_hours REAL,
#             achieved_hours REAL
#         )
#     """)
#     # Create revision_notes table
#     c.execute("""
#         CREATE TABLE IF NOT EXISTS revision_notes (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             subject TEXT NOT NULL,
#             short_notes TEXT,
#             formula TEXT
#         )
#     """)
#     conn.commit()
    
#     # Insert default schedule data if not already present.
#     default_phases = {
#         "Phase 1": {
#             "title": "Foundations (Months 1–2)",
#             "focus": "Engineering Mathematics & Discrete Mathematics",
#             "table": [
#                 ["Monday", "7:00-9:00 PM", "Theory Lecture", "Calculus Fundamentals"],
#                 ["Tuesday", "7:00-9:00 PM", "Problem-Solving", "Calculus: Worked examples and derivations"],
#                 ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Linear Algebra Basics: Vector spaces, matrices, operations"],
#                 ["Thursday", "7:00-9:00 PM", "Problem-Solving", "Linear Algebra: Determinants, eigenvalues"],
#                 ["Friday", "7:00-9:00 PM", "Weekly Recap & Quiz", "Combined Topics: Quick tests and self-assessment"],
#                 ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Live lecture reinforcing fundamentals"],
#                 ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "In-depth lecture on Calculus/Linear Algebra"],
#                 ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Exercises and sample problems"],
#                 ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Comprehensive problem sets"],
#                 ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Full-length practice test and error analysis"]
#             ]
#         },
#         "Phase 2": {
#             "title": "Advanced Mathematics & Probability/Statistics (Months 3–4)",
#             "focus": "Advanced Probability & Statistics topics (counting, axioms, distributions, optimization, hypothesis testing) with Go Classes sessions for clarifications.",
#             "table": [
#                 ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
#                 ["Monday", "7:00-9:00 PM", "Theory Lecture", "Counting Techniques & Probability Basics: Permutations, combinations, axioms"],
#                 ["Tuesday", "7:00-9:00 PM", "Problem-Solving", "Probability Concepts: Sample spaces, independence, events"],
#                 ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Random Variables & Distributions: Discrete (Bernoulli, Binomial) and Continuous (Uniform, Exponential)"],
#                 ["Thursday", "7:00-9:00 PM", "Practice & Exercises", "Statistical Inference: Conditional probability, Bayes' theorem"],
#                 ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: CLT, confidence intervals, z-test, t-test, chi-squared test"],
#                 ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Session on key problem areas in probability/statistics"],
#                 ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Advanced Topics: In-depth derivations and optimization techniques"],
#                 ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Challenging problems and test-style questions"],
#                 ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined exercises and review"],
#                 ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Timed tests with detailed error analysis"]
#             ]
#         },
#         "Phase 3": {
#             "title": "Programming, Data Structures, Algorithms & Database Management (Months 5–7)",
#             "focus": "Python programming, core data structures and algorithms, and database management fundamentals, with supplementary Go Classes sessions for coding and database concepts.",
#             "table": [
#                 ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
#                 ["Monday", "7:00-9:00 PM", "Theory Lecture", "Python Programming & Basic Data Structures: Syntax, data types, stacks, queues"],
#                 ["Tuesday", "7:00-9:00 PM", "Coding Practice", "Data Structures: Implementation of linked lists, arrays, etc."],
#                 ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Algorithms: Search algorithms (linear, binary) and basic sorting"],
#                 ["Thursday", "7:00-9:00 PM", "Problem-Solving", "Hands-On: Coding exercises on trees, hash tables, etc."],
#                 ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: Quick quizzes and conceptual coding reviews"],
#                 ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Live session on coding challenges and database queries"],
#                 ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Database Management: ER-model, relational algebra, SQL, normalization"],
#                 ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Hands-on coding and SQL query practices"],
#                 ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined coding challenges and algorithm problem sets"],
#                 ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Full-length tests with detailed walkthroughs"]
#             ]
#         },
#         "Phase 4": {
#             "title": "Machine Learning & Artificial Intelligence (Months 8–10)",
#             "focus": "Supervised & unsupervised machine learning techniques and AI fundamentals, with interactive Go Classes sessions on advanced ML/AI topics.",
#             "table": [
#                 ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
#                 ["Monday", "7:00-9:00 PM", "Theory Lecture", "Supervised Learning: Regression (simple, multiple, ridge) & Classification (logistic, SVM, etc.)"],
#                 ["Tuesday", "7:00-9:00 PM", "Practical Implementation", "Supervised Learning: Python coding (k-nearest neighbors, decision trees)"],
#                 ["Wednesday", "7:00-9:00 PM", "Theory Lecture", "Neural Networks: Fundamentals of MLP and feed-forward architecture"],
#                 ["Thursday", "7:00-9:00 PM", "Coding Practice", "Unsupervised Learning: Clustering (k-means, hierarchical) and PCA implementations"],
#                 ["Friday", "7:00-9:00 PM", "Recap & Quiz", "Review: Bias-variance, cross-validation, and key ML/AI concepts"],
#                 ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Interactive session on ML/AI problem solving"],
#                 ["Saturday", "10:00 AM-12:00 PM", "Deep Study Session", "Artificial Intelligence: Search strategies, logic, reasoning under uncertainty"],
#                 ["Saturday", "1:00-4:00 PM", "Intensive Problem Solving", "Practice: Case studies and sample problems on ML/AI algorithms"],
#                 ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Mixed Topics: Comprehensive exercises integrating ML/AI concepts"],
#                 ["Sunday", "1:00-5:00 PM", "Mock Test & Revision", "Assessment: Full-length mock tests with in-depth error analysis"]
#             ]
#         },
#         "Phase 5": {
#             "title": "Revision, Practice & Mock Tests (Months 11–12)",
#             "focus": "Comprehensive revision of all subjects with intensive practice, mock tests, and error analysis. Final Go Classes sessions polish exam strategies.",
#             "table": [
#                 ["Day", "Time Slot", "Activity & Go Classes Integration", "Subject Focus & Details"],
#                 ["Monday", "7:00-9:00 PM", "Revision Session", "Quick review of Calculus, Linear Algebra, Discrete Math"],
#                 ["Tuesday", "7:00-9:00 PM", "Revision & Practice", "Probability & Statistics: Key formulas and targeted problems"],
#                 ["Wednesday", "7:00-9:00 PM", "Revision Session", "Programming & Algorithms: Code review and challenging problem solving"],
#                 ["Thursday", "7:00-9:00 PM", "Revision & Practice", "Database Management: SQL queries, normalization, ER-model refresh"],
#                 ["Friday", "7:00-9:00 PM", "Mixed Revision & Quiz", "Machine Learning & AI: Quick quizzes and concept reviews"],
#                 ["Saturday", "9:00-10:00 AM", "Go Classes Live Session", "Final review and strategy session"],
#                 ["Saturday", "10:00 AM-12:00 PM", "Full-Length Mock Test", "Simulated exam covering the entire syllabus"],
#                 ["Saturday", "1:00-4:00 PM", "Error Analysis & Revision", "Detailed review of mistakes and focus on weak areas"],
#                 ["Sunday", "9:00-12:00 PM", "Integrated Practice", "Combined problem sets for speed and accuracy"],
#                 ["Sunday", "1:00-5:00 PM", "Final Revision & Strategy", "Overall preparation: Strategy session, key summaries, and Q&A review"]
#             ]
#         },
#         "General Aptitude": {
#             "title": "General Aptitude",
#             "focus": "Quantitative, Logical, and Verbal skills",
#             "table": [
#                 ["Monday", "5:00-6:00 PM", "Practice", "Quantitative problems"],
#                 ["Wednesday", "5:00-6:00 PM", "Practice", "Logical reasoning puzzles"],
#                 ["Friday", "5:00-6:00 PM", "Practice", "Verbal ability and reading comprehension"]
#             ]
#         }
#     }
    
#     for phase, details in default_phases.items():
#         c = conn.cursor()
#         c.execute("SELECT COUNT(*) FROM schedule WHERE phase = ?", (phase,))
#         if c.fetchone()[0] == 0:
#             c.execute("""
#                 INSERT INTO schedule (phase, title, focus, schedule_json)
#                 VALUES (?, ?, ?, ?)
#             """, (phase, details["title"], details["focus"], json.dumps(details["table"])))
#     conn.commit()
#     conn.close()

# init_db()  # Initialize database/tables

# -----------------------
# 2. Database CRUD Helpers
# -----------------------

def insert_progress_log(date_str, phase, subject, hours, notes):
    data = {
        "date": date_str,
        "phase": phase,
        "subject": subject,
        "hours": hours,
        "notes": notes
    }
    result = supabase.table("progress_logs").insert(data).execute()
    if result.error:
        st.error(f"Error inserting progress log: {result.error}")

def get_progress_logs():
    """Retrieves all progress logs."""
    try:
        response = supabase.table('progress_logs').select('*').order('date', desc=False).execute()
        return response.data if hasattr(response, 'data') else []
    except Exception as e:
        st.error(f"Error fetching progress logs: {str(e)}")
        return []


def update_schedule_db(phase, new_table):
    data = {"schedule_json": json.dumps(new_table)}
    result = supabase.table("schedule").update(data).eq("phase", phase).execute()
    if result.error:
        st.error(f"Error updating schedule: {result.error}")

def get_all_schedules():
    """
    Retrieves all schedules from the Supabase database
    """
    try:
        response = supabase.table('schedule').select('*').execute()
        
        # Initialize empty schedules dictionary
        schedules = {}
        
        # Check if we have data in the response
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
        
def insert_progress_log(date_str, phase, subject, hours, notes):
    """Inserts a new progress log."""
    try:
        response = supabase.table('progress_logs').insert({
            'date': date_str,
            'phase': phase,
            'subject': subject,
            'hours': float(hours),
            'notes': notes
        }).execute()
        
        if not response.error:
            return True
        else:
            st.error(f"Error logging progress: {response.error}")
            return False
    except Exception as e:
        st.error(f"Error inserting progress log: {str(e)}")
        return False

def get_progress_logs():
    """Retrieves all progress logs."""
    try:
        response = supabase.table('progress_logs').select('*').execute()
        return response.data if not response.error else []
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
        # Get current goal data
        response = supabase.table("study_goals").select("*").eq('id', goal_id).execute()
        if hasattr(response, 'data') and response.data:
            current_goal = response.data[0]
            new_achieved = float(current_goal['achieved_hours']) + float(additional_hours)
            
            # Update the goal
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
    """
    Retrieves all revision notes from the database.
    Returns a list of notes or empty list if none found.
    """
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
    """
    Combine text from question bank, revision notes, and resources for a given subject.
    """
    context_parts = []
    
    try:
        # Questions from question bank
        questions = get_all_questions()
        subject_questions = [q for q in questions if q["subject"].lower() == selected_subject.lower()]
        if subject_questions:
            q_text = "\n".join([
                f"Q: {q['question']}\nA: {q['answer'] if q['answer'] else 'No answer provided'}" 
                for q in subject_questions
            ])
            context_parts.append("Question Bank:\n" + q_text)
        
        # Revision notes
        notes = get_revision_notes()
        subject_notes = [n for n in notes if n["subject"].lower() == selected_subject.lower()]
        if subject_notes:
            n_text = "\n".join([
                f"Note: {n['short_notes']}\nFormula: {n['formula']}" 
                for n in subject_notes
            ])
            context_parts.append("Revision Notes:\n" + n_text)
        
        # Resources (uploaded PDFs/images)
        resources = get_all_resources()
        subject_resources = [
            r for r in resources 
            if r["subject"] and r["subject"].lower() == selected_subject.lower() 
            and r["filename"]
        ]
        
        for r in subject_resources:
            if os.path.exists(r["filename"]):
                extracted = extract_text_from_file(r["filename"])
                if extracted:
                    context_parts.append(f"Resource ({r['title']}):\n" + extracted)
        
        return "\n\n".join(context_parts)
    
    except Exception as e:
        st.error(f"Error building RAG context: {str(e)}")
        return ""

# ------------------------
# 5. Streamlit App Pages
# ------------------------


def dashboard_page():
    st.title("GATE DA 2026 Dashboard")
    st.subheader("Overview of Your Study Progress")
    
    # Get schedules with error handling
    try:
        schedules = get_all_schedules()
        phase_options = list(schedules.keys()) if schedules else ['Phase 1']  # Provide default if empty
        
        with st.form("study_session_form"):
            session_date = st.date_input("Date", datetime.date.today())
            selected_phase = st.selectbox("Select Phase", phase_options)
            selected_subject = st.selectbox("Select Subject", SUBJECT_LIST)
            hours = st.number_input("Hours Studied", min_value=0.0, step=0.5)
            notes = st.text_area("Notes / Reflection")
            submitted = st.form_submit_button("Log Session")
            
            if submitted:
                try:
                    date_str = session_date.strftime("%Y-%m-%d")
                    # Insert using Supabase client
                    response = supabase.table('progress_logs').insert({
                        'date': date_str,
                        'phase': selected_phase,
                        'subject': selected_subject,
                        'hours': float(hours),
                        'notes': notes
                    }).execute()
                    
                    if hasattr(response, 'data') and response.data:
                        st.success("Study session logged successfully!")
                    else:
                        st.error("Error logging session: No data returned")
                except Exception as e:
                    st.error(f"Error logging session: {str(e)}")
    
    except Exception as e:
        st.error(f"Error loading dashboard: {str(e)}")
        return

    # Display existing logs
    try:
        logs_response = supabase.table('progress_logs').select('*').execute()
        if hasattr(logs_response, 'data') and logs_response.data:
            st.header("Study Sessions Log")
            df_logs = pd.DataFrame(logs_response.data)
            st.dataframe(df_logs)
    except Exception as e:
        st.error(f"Error loading logs: {str(e)}")    
        
def analytics_page():
    st.title("Progress Analytics")
    
    try:
        # Get progress logs
        logs_response = supabase.table('progress_logs').select('*').execute()
        
        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study session data available for analytics.")
            return
        
        logs = logs_response.data
        
        # Convert logs to DataFrame and sort by date
        df_logs = pd.DataFrame(logs)
        df_logs["date"] = pd.to_datetime(df_logs["date"])
        df_logs.sort_values("date", inplace=True)

        # Create tabs for different analysis views
        tab1, tab2, tab3 = st.tabs(["Progress Summary", "Time Analysis", "Subject Analysis"])
        
        with tab1:
            st.header("Progress Summary")
            
            # Overall statistics
            total_hours = df_logs["hours"].sum()
            total_days = len(df_logs["date"].unique())
            avg_hours_per_day = total_hours / total_days if total_days > 0 else 0
            
            # Create summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Study Hours", f"{total_hours:.1f}")
            with col2:
                st.metric("Days Studied", total_days)
            with col3:
                st.metric("Avg Hours/Day", f"{avg_hours_per_day:.1f}")
            
            # Subject-wise summary table
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
            
            # Analysis type selector
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
                
            else:  # Cumulative Progress
                df_logs["cumulative_hours"] = df_logs["hours"].cumsum()
                fig = px.line(df_logs, x="date", y="cumulative_hours",
                             title="Cumulative Study Hours")
                st.plotly_chart(fig, use_container_width=True, key='tab_cumulative')

        with tab3:
            st.header("Subject Analysis")
            
            # Subject selection for detailed analysis
            selected_subject = st.selectbox("Select Subject for Detailed Analysis", 
                                          df_logs["subject"].unique())
            
            # Filter data for selected subject
            subject_data = df_logs[df_logs["subject"] == selected_subject]
            
            # Subject metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Hours", f"{subject_data['hours'].sum():.1f}")
            with col2:
                st.metric("Number of Sessions", len(subject_data))
            with col3:
                avg_session = subject_data["hours"].mean()
                st.metric("Avg Hours/Session", f"{avg_session:.1f}")
            
            # Progress over time for selected subject
            fig = px.line(subject_data, x="date", y="hours",
                         title=f"{selected_subject} - Study Hours Over Time")
            st.plotly_chart(fig, use_container_width=True, key='tab3')
            
            # Session details table
            st.subheader("Session Details")
            session_details = subject_data[["date", "phase", "hours", "notes"]].sort_values("date", ascending=False)
            st.dataframe(session_details)

    except Exception as e:
        st.error(f"Error in analytics: {str(e)}")
        return
        
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

    # Add question form
    with st.form("question_bank_form"):
        subject = st.selectbox("Subject", SUBJECT_LIST)  # Use the global SUBJECT_LIST
        question_text = st.text_area("Question")
        answer_text = st.text_area("Answer / Pattern (optional)")
        submit = st.form_submit_button("Add Question")
        
        if submit:
            if subject and question_text:
                if insert_question(subject, question_text, answer_text):
                    st.success("Question added successfully!")
                    st.rerun()  # Refresh the page to show the new question
            else:
                st.error("Please provide both a subject and a question.")

    # Display existing questions
    try:
        questions = get_all_questions()
        if questions:
            st.header("Existing Questions")
            
            # Add search/filter functionality
            search_term = st.text_input("Search questions (by subject or content):")
            
            # Convert to DataFrame
            df_questions = pd.DataFrame(questions)
            
            # Apply search filter if provided
            if search_term:
                mask = (
                    df_questions['subject'].str.contains(search_term, case=False, na=False) |
                    df_questions['question'].str.contains(search_term, case=False, na=False) |
                    df_questions['answer'].str.contains(search_term, case=False, na=False)
                )
                df_questions = df_questions[mask]

            # Group by subject
            subjects = df_questions['subject'].unique()
            
            for subject in subjects:
                with st.expander(f"{subject} ({len(df_questions[df_questions['subject'] == subject])} questions)"):
                    subject_questions = df_questions[df_questions['subject'] == subject]
                    
                    for _, row in subject_questions.iterrows():
                        st.markdown("---")
                        st.markdown(f"**Question:** {row['question']}")
                        if row['answer']:
                            st.markdown(f"**Answer:** {row['answer']}")
                        
                        # Add delete button for each question
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

    # Create tabs for different resource management sections
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
                            # Create uploads directory if it doesn't exist
                            upload_folder = "uploads"
                            os.makedirs(upload_folder, exist_ok=True)
                            
                            # Save the file
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
            # Add search/filter functionality
            search_term = st.text_input("Search resources (by subject or title):")
            
            # Convert to DataFrame
            df_resources = pd.DataFrame(resources)
            
            # Apply search filter if provided
            if search_term:
                mask = (
                    df_resources['subject'].str.contains(search_term, case=False, na=False) |
                    df_resources['title'].str.contains(search_term, case=False, na=False)
                )
                df_resources = df_resources[mask]

            # Group by subject
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
                        
                        # Add delete button
                        if st.button(f"Delete Resource {row['id']}", key=f"del_res_{row['id']}"):
                            if delete_resource(row['id']):
                                # Also delete the file if it exists
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

    # Create tabs for different goal management sections
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
            # Convert to DataFrame for easier manipulation
            df_goals = pd.DataFrame(goals)
            df_goals = df_goals.sort_values('achieved_hours', ascending=False)

            # Overall progress summary
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

            # Individual goals
            st.subheader("Individual Goals")
            for _, goal in df_goals.iterrows():
                with st.expander(f"Goal: {goal['description']}"):
                    progress = (goal['achieved_hours'] / goal['target_hours'] * 100) if goal['target_hours'] > 0 else 0
                    
                    # Progress bar
                    st.progress(min(float(progress) / 100, 1.0))
                    
                    # Goal details
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Target Hours", f"{goal['target_hours']:.1f}")
                    with col2:
                        st.metric("Achieved Hours", f"{goal['achieved_hours']:.1f}")
                    with col3:
                        st.metric("Progress", f"{progress:.1f}%")
                    
                    # Update achieved hours
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
    st.subheader("View Your Study Sessions Grouped by Date")

    try:
        # Get progress logs
        logs_response = supabase.table('progress_logs').select('*').order('date', desc=False).execute()
        
        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study sessions logged yet.")
            return
        
        logs = logs_response.data
        
        # Convert to DataFrame
        df_logs = pd.DataFrame(logs)
        df_logs['date'] = pd.to_datetime(df_logs['date'])
        
        # Add month-year column for grouping
        df_logs['month_year'] = df_logs['date'].dt.strftime('%B %Y')
        
        # Get unique months
        months = sorted(df_logs['month_year'].unique(), reverse=True)  # Most recent first
        
        # Create month tabs
        if len(months) > 0:
            month_tabs = st.tabs(months)
            
            for i, month in enumerate(months):
                with month_tabs[i]:
                    month_data = df_logs[df_logs['month_year'] == month]
                    
                    # Group by date and sort in reverse chronological order
                    dates = sorted(month_data['date'].dt.date.unique(), reverse=True)
                    
                    for date_idx, date in enumerate(dates):
                        date_data = month_data[month_data['date'].dt.date == date]
                        
                        # Calculate daily summary
                        total_hours = date_data['hours'].sum()
                        subjects_covered = date_data['subject'].nunique()
                        
                        with st.expander(f"{date.strftime('%A, %B %d, %Y')} - {total_hours:.1f} hours, {subjects_covered} subjects"):
                            # Create columns for better organization
                            for _, session in date_data.iterrows():
                                col1, col2, col3 = st.columns([2, 1, 1])
                                with col1:
                                    st.write(f"**Subject:** {session['subject']}")
                                    if session['notes']:
                                        st.write(f"*Notes:* {session['notes']}")
                                with col2:
                                    st.write(f"**Hours:** {session['hours']}")
                                with col3:
                                    st.write(f"**Phase:** {session['phase']}")
                                st.markdown("---")
                            
                            # Daily summary metrics
                            st.markdown("### Daily Summary")
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Hours", f"{total_hours:.1f}")
                            with col2:
                                st.metric("Subjects Covered", subjects_covered)
                            with col3:
                                avg_hours = total_hours / len(date_data)
                                st.metric("Avg Hours/Session", f"{avg_hours:.1f}")
                            
                            # Show subject breakdown
                            subject_hours = date_data.groupby('subject')['hours'].sum()
                            
                            # Create a bar chart for subject distribution with unique key
                            fig = px.bar(
                                x=subject_hours.index,
                                y=subject_hours.values,
                                title="Hours by Subject",
                                labels={'x': 'Subject', 'y': 'Hours'}
                            )
                            
                            # Add unique key for each plotly chart
                            chart_key = f"chart_{month}_{date_idx}"
                            st.plotly_chart(fig, use_container_width=True, key=chart_key)
                            
                            # Option to delete sessions
                            if st.button(f"Delete All Sessions for {date}", key=f"del_{date}"):
                                try:
                                    # Get IDs of sessions for this date
                                    session_ids = date_data['id'].tolist()
                                    for session_id in session_ids:
                                        response = supabase.table('progress_logs').delete().eq('id', session_id).execute()
                                    st.success(f"Deleted all sessions for {date}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error deleting sessions: {str(e)}")

        # Add monthly summary in sidebar
        st.sidebar.markdown("## Monthly Summary")
        for month in months:
            month_data = df_logs[df_logs['month_year'] == month]
            total_month_hours = month_data['hours'].sum()
            total_month_sessions = len(month_data)
            total_month_subjects = month_data['subject'].nunique()
            
            st.sidebar.markdown(f"**{month}**")
            st.sidebar.markdown(f"- Total Hours: {total_month_hours:.1f}")
            st.sidebar.markdown(f"- Sessions: {total_month_sessions}")
            st.sidebar.markdown(f"- Subjects: {total_month_subjects}")
            st.sidebar.markdown("---")

        # Add overall summary at the top
        st.sidebar.markdown("## Overall Summary")
        total_hours = df_logs['hours'].sum()
        total_sessions = len(df_logs)
        total_subjects = df_logs['subject'].nunique()
        avg_hours_per_session = total_hours / total_sessions if total_sessions > 0 else 0
        
        st.sidebar.metric("Total Study Hours", f"{total_hours:.1f}")
        st.sidebar.metric("Total Sessions", total_sessions)
        st.sidebar.metric("Total Subjects", total_subjects)
        st.sidebar.metric("Avg Hours/Session", f"{avg_hours_per_session:.1f}")

    except Exception as e:
        st.error(f"Error in calendar view: {str(e)}")
        return
def download_reports_page():
    st.title("Download Reports")
    st.subheader("Study Session Reports and Analytics")

    try:
        # Get progress logs
        logs_response = supabase.table('progress_logs').select('*').order('date', ascending=False).execute()
        
        if not hasattr(logs_response, 'data') or not logs_response.data:
            st.info("No study sessions available to download.")
            return
        
        logs = logs_response.data
        
        # Convert to DataFrame
        df_logs = pd.DataFrame(logs)
        df_logs['date'] = pd.to_datetime(df_logs['date'])
        
        # Create different report types
        st.header("Available Reports")
        
        # 1. Basic Study Log
        st.subheader("1. Basic Study Log")
        st.dataframe(df_logs[['date', 'subject', 'phase', 'hours', 'notes']])
        
        csv_basic = df_logs.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Basic Study Log (CSV)",
            csv_basic,
            "study_sessions_basic.csv",
            "text/csv",
            key='download_basic'
        )

        # 2. Subject-wise Summary
        st.subheader("2. Subject-wise Summary")
        subject_summary = df_logs.groupby('subject').agg({
            'hours': ['sum', 'mean', 'count'],
            'date': 'nunique'
        }).round(2)
        subject_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions', 'Number of Days']
        st.dataframe(subject_summary)
        
        csv_subject = subject_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Subject Summary (CSV)",
            csv_subject,
            "subject_summary.csv",
            "text/csv",
            key='download_subject'
        )

        # 3. Daily Summary
        st.subheader("3. Daily Summary")
        daily_summary = df_logs.groupby('date').agg({
            'hours': ['sum', 'count'],
            'subject': 'nunique'
        }).round(2)
        daily_summary.columns = ['Total Hours', 'Number of Sessions', 'Subjects Covered']
        st.dataframe(daily_summary)
        
        csv_daily = daily_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Daily Summary (CSV)",
            csv_daily,
            "daily_summary.csv",
            "text/csv",
            key='download_daily'
        )

        # 4. Phase-wise Progress
        st.subheader("4. Phase-wise Progress")
        phase_summary = df_logs.groupby('phase').agg({
            'hours': ['sum', 'mean', 'count'],
            'subject': 'nunique',
            'date': 'nunique'
        }).round(2)
        phase_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions', 
                               'Unique Subjects', 'Number of Days']
        st.dataframe(phase_summary)
        
        csv_phase = phase_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Phase Summary (CSV)",
            csv_phase,
            "phase_summary.csv",
            "text/csv",
            key='download_phase'
        )

        # 5. Monthly Summary
        st.subheader("5. Monthly Summary")
        df_logs['month_year'] = df_logs['date'].dt.strftime('%Y-%m')
        monthly_summary = df_logs.groupby('month_year').agg({
            'hours': ['sum', 'mean', 'count'],
            'subject': 'nunique',
            'date': 'nunique'
        }).round(2)
        monthly_summary.columns = ['Total Hours', 'Avg Hours/Session', 'Number of Sessions',
                                 'Unique Subjects', 'Number of Days']
        st.dataframe(monthly_summary)
        
        csv_monthly = monthly_summary.to_csv().encode('utf-8')
        st.download_button(
            "Download Monthly Summary (CSV)",
            csv_monthly,
            "monthly_summary.csv",
            "text/csv",
            key='download_monthly'
        )

        # 6. Comprehensive Report
        st.subheader("6. Comprehensive Report")
        
        # Create Excel file with multiple sheets
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_logs.to_excel(writer, sheet_name='Study Sessions', index=False)
            subject_summary.to_excel(writer, sheet_name='Subject Summary')
            daily_summary.to_excel(writer, sheet_name='Daily Summary')
            phase_summary.to_excel(writer, sheet_name='Phase Summary')
            monthly_summary.to_excel(writer, sheet_name='Monthly Summary')
        
        st.download_button(
            "Download Comprehensive Report (Excel)",
            output.getvalue(),
            "comprehensive_study_report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key='download_comprehensive'
        )

        # Display overall statistics
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

    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")
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

# ------------------------
# New Combined Page: RAG Assistant
# ------------------------

def get_and_verify_token():
    """
    Prompts the user to enter a GitHub token and verifies it.
    Returns the verified token or None.
    """
    if "token" in st.session_state and st.session_state.token:
        return st.session_state.token

    token_input = st.text_input("Enter your GitHub Token:", type="password")
    
    if token_input:
        with st.spinner("Verifying token..."):
            try:
                # Test the token with a minimal GitHub API request
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
    st.subheader("Ask for subject/topic questions and revision points – all through a prompt!")
    
    selected_subject = st.selectbox("Select Subject", SUBJECT_LIST)
    
    st.markdown("#### Upload Revision Resource (PDF or Image)")
    uploaded_file = st.file_uploader(
        "Upload a file", 
        type=["pdf", "png", "jpg", "jpeg"], 
        key="rag_resource"
    )
    
    additional_messages = []
    
    if uploaded_file:
        try:
            # Create uploads directory if it doesn't exist
            upload_folder = "uploads"
            os.makedirs(upload_folder, exist_ok=True)
            
            # Save uploaded file
            file_path = os.path.join(upload_folder, uploaded_file.name)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success("Resource uploaded successfully!")
            
            # Process file based on type
            ext = uploaded_file.name.split('.')[-1].lower()
            if ext in ["png", "jpg", "jpeg"]:
                try:
                    image_url = ImageUrl.load(
                        image_file=file_path,
                        image_format=ext,
                        detail=ImageDetailLevel.LOW
                    )
                    additional_messages.append(ImageContentItem(image_url=image_url))
                except Exception as e:
                    st.error(f"Error processing image: {str(e)}")
                    
            elif ext == "pdf":
                extracted_text = extract_text_from_file(file_path)
                if extracted_text:
                    additional_messages.append(
                        UserMessage(f"Extracted text from PDF: {extracted_text}")
                    )
                else:
                    st.warning("No text could be extracted from the PDF.")
                    
        except Exception as e:
            st.error(f"Error handling uploaded file: {str(e)}")
    
    # Get context for RAG
    retrieval_context = get_rag_context(selected_subject)
    
    # Prepare prompt
    prompt_text = (
        f"You are an expert revision assistant for the GATE exam.\n"
        f"Subject: {selected_subject}\n"
        f"Retrieved Context:\n{retrieval_context}\n"
        f"User Query: "
    )
    
    # Get user query
    user_query = st.text_input(
        "Enter your query (e.g., 'Give me daily revision points for Calculus'):"
    )
    
    if user_query:
        # Verify token
        token = get_and_verify_token()
        if not token:
            st.error("Please provide a valid GitHub token to proceed.")
            return
        
        try:
            # Prepare messages
            messages = [
                SystemMessage(prompt_text),
                UserMessage(user_query)
            ]
            messages.extend(additional_messages)
            
            # Create client
            client = ChatCompletionsClient(
                endpoint="https://models.inference.ai.azure.com",
                credential=AzureKeyCredential(token),
                api_version="2024-12-01-preview"
            )
            
            # Get response
            with st.spinner("Generating response..."):
                response = client.complete(
                    messages=messages,
                    temperature=0.7,
                    top_p=0.95,
                    model="Llama-3.2-90B-Vision-Instruct"
                )
                
                if hasattr(response.choices[0].message, 'content'):
                    rag_reply = response.choices[0].message.content
                    st.markdown("### RAG Assistant Response")
                    st.markdown(rag_reply)
                else:
                    st.error("No response content received from the model.")
                    
        except Exception as e:
            st.error(f"Error generating response: {str(e)}")

def chat_assistant_page():
    st.title("Chat Assistant")
    st.subheader("Talk to your study data assistant using OpenAI o3-mini (GitHub-hosted)!")
    
    # Get and verify token
    token = get_and_verify_token()
    if not token:
        st.warning("Please enter and verify your GitHub token above to start chatting.")
        return
        
    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Display chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
    
    # Get user input
    user_input = st.chat_input("Enter your message:")
    
    if user_input:
        # Add user message to history
        st.session_state.chat_history.append({
            "role": "user", 
            "content": user_input
        })
        
        with st.chat_message("user"):
            st.write(user_input)
        
        try:
            # Create Azure OpenAI client
            client = ChatCompletionsClient(
                endpoint="https://models.inference.ai.azure.com",
                credential=AzureKeyCredential(token),
                api_version="2024-12-01-preview"
            )
            
            # Prepare messages
            messages = [
                SystemMessage("You are a helpful study assistant."),
                *[UserMessage(msg["content"]) if msg["role"] == "user" 
                  else AssistantMessage(msg["content"]) 
                  for msg in st.session_state.chat_history]
            ]
            
            # Get response
            with st.spinner("Thinking..."):
                response = client.complete(
                    messages=messages,
                    model="o3-mini"
                )
                
                assistant_reply = response.choices[0].message.content
                
                # Add assistant response to history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": assistant_reply
                })
                
                with st.chat_message("assistant"):
                    st.write(assistant_reply)
                    
        except Exception as e:
            st.error(f"Error: {str(e)}")

# # At the start of your app
# if 'token' not in st.session_state:
#     st.session_state.token = None

# # Add a function to clear token
# def clear_token():
#     st.session_state.token = None
#     st.session_state.chat_history = []

# # Add a button to clear token if needed
# if st.session_state.token:
#     if st.sidebar.button("Clear Token"):
#         clear_token()
# ------------------------
# 6. Main App Navigation
# ------------------------

def main():
    # st.set_page_config(page_title="GATE DA 2026 Dashboard", layout="wide")
    
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
    init_db()  # Initialize database
    main()
