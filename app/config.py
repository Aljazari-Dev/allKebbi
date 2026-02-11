# config.py
import os
import json
import datetime
import random
import string
import threading
import re

# ------------------ CONFIG & STORAGE PATHS ------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(PROJECT_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

SUBJECT_RAG_DIR = os.environ.get("SUBJECT_RAG_DIR", os.path.join(PROJECT_DIR, "subject_rag_books"))
os.makedirs(SUBJECT_RAG_DIR, exist_ok=True)


SETTINGS_PATH   = os.path.join(DATA_DIR, "settings.json")
ROBOTS_PATH     = os.path.join(DATA_DIR, "robots.json")
STAGES_PATH     = os.path.join(DATA_DIR, "stages.json")
QUIZ_PATH       = os.path.join(DATA_DIR, "quizzes.json")
QUIZ_STATS_PATH = os.path.join(DATA_DIR, "quiz_stats.json")
ATTENDANCE_PATH = os.path.join(DATA_DIR, "attendance.json")
PROGRESS_PATH   = os.path.join(DATA_DIR, "progress.json")

SUBJECT_RAG_DIR = os.path.join(PROJECT_DIR, "subject_rag_books")
os.makedirs(SUBJECT_RAG_DIR, exist_ok=True)

FILE_LOCK = threading.Lock()

# ------------------ DEFAULTS ------------------
DEFAULT_SETTINGS = {
    "api_key": "",
    "model": "gpt-3.5-turbo",
    "system_prompt": (
        "ROLE & IDENTITY:\n"
        "- You are Kebbi, a classroom assistant robot.\n"
        "- Reply language: English.\n"
    ),
    "temperature": 0.3,
    "max_tokens": 400,
    "always_correct": False
}

ROUTER_SYSTEM_PROMPT = """
You are an intent router for a school robot.

You MUST return a valid JSON object ONLY, no extra text.

Your job:
1) Read the student message.
2) Decide which intent applies:
   - "greeting"          -> greetings like مرحبا, أهلاً, السلام عليكم
   - "subject_question"  -> questions about the school subject/book (physics, chemistry, biology, math, etc.)
   - "robot_info"        -> questions about the robot abilities or what it can do
   - "chitchat"          -> small talk, how are you, thank you, jokes, etc.
   - "other"             -> anything else

3) For greeting / robot_info / chitchat:
   - Write a SHORT reply (max 2 sentences) in the same language of the user.
   - reply should NOT be about the book content.
4) For subject_question:
   - Just set "need_rag": true and leave "assistant_reply" empty.

Return JSON with fields:
{
  "intent": "...",
  "need_rag": true/false,
  "assistant_reply": "..."
}

Examples:

User: "مرحبا"
{
  "intent": "greeting",
  "need_rag": false,
  "assistant_reply": "مرحباً! أنا روبوت مساعد للطلاب، اكدر أجاوبك عن أسئلة المادة اللي تدرسها."
}

User: "مرحبا شنو أقسام الحركة الجزيئية؟"
{
  "intent": "subject_question",
  "need_rag": true,
  "assistant_reply": ""
}

User: "شنو تكدر تسوي؟"
{
  "intent": "robot_info",
  "need_rag": false,
  "assistant_reply": "أكدر أجاوب أسئلتك عن المواد الدراسية، وأشرحلك المواضيع بطريقة بسيطة، وبالعربي أو الإنكليزي."
}
"""

# 8 subjects per section (exactly)
DEFAULT_SUBJECTS = [
    "Arabic",
    "English",
    "Mathematics",
    "Science",
    "History",
    "Geography",
    "Computer",
    "Religion"
]


def new_section_template():
    # section structure with subject_students mapping
    return {
        "students": [],
        "subjects": DEFAULT_SUBJECTS[:],
        "subject_students": {s: [] for s in DEFAULT_SUBJECTS}
    }


# Default structure of stages: Stage 1..3, each with sections A/B and 8 subjects
DEFAULT_STAGES = {
    "Stage 1": {"sections": {"A": new_section_template(), "B": new_section_template()}},
    "Stage 2": {"sections": {"A": new_section_template(), "B": new_section_template()}},
    "Stage 3": {"sections": {"A": new_section_template(), "B": new_section_template()}},
}

# ------------------ RAG CONFIG (per-subject Word book) ------------------
SUBJECT_RAG_DIR = "subject_rag_books"
os.makedirs(SUBJECT_RAG_DIR, exist_ok=True)

RAG_MODEL_NAME = "intfloat/multilingual-e5-base"
RAG_TOP_K = 8

# ------------------ GENERIC HELPERS ------------------


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, obj):
    with FILE_LOCK:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)


def new_id(prefix="id"):
    return prefix + "_" + "".join(
        random.choices(string.ascii_lowercase + string.digits, k=6)
    )


def now_iso():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
