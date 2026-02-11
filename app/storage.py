# storage.py
import datetime
import re
import random
from collections import Counter

from app.config import (
    SETTINGS_PATH, ROBOTS_PATH, STAGES_PATH, QUIZ_PATH,
    QUIZ_STATS_PATH, ATTENDANCE_PATH, PROGRESS_PATH,
    DEFAULT_SETTINGS, DEFAULT_STAGES, DEFAULT_SUBJECTS,
    load_json, save_json, new_id
)

# ------------------ GLOBAL STATE (LOADED FROM DISK) ------------------
SETTINGS   = load_json(SETTINGS_PATH, DEFAULT_SETTINGS.copy())
ROBOTS     = load_json(ROBOTS_PATH, {})
STAGES     = load_json(STAGES_PATH, DEFAULT_STAGES.copy())
QUIZZES    = load_json(QUIZ_PATH, {"active_id": None, "quizzes": {}})
QUIZ_STATS = load_json(QUIZ_STATS_PATH, {})
ATTENDANCE = load_json(ATTENDANCE_PATH, {})
PROGRESS   = load_json(PROGRESS_PATH, {})

# ------------------ STAGES / STUDENTS HELPERS ------------------


def ensure_stage_structure():
    global STAGES
    changed = False
    for s in ["Stage 1", "Stage 2", "Stage 3"]:
        if s not in STAGES:
            STAGES[s] = {
                "sections": {"A": _new_section(), "B": _new_section()}
            }
            changed = True
        else:
            if "sections" not in STAGES[s]:
                STAGES[s]["sections"] = {
                    "A": _new_section(),
                    "B": _new_section()
                }
                changed = True
            for sec in ("A", "B"):
                if sec not in STAGES[s]["sections"]:
                    STAGES[s]["sections"][sec] = _new_section()
                    changed = True
                else:
                    secobj = STAGES[s]["sections"][sec]
                    if "subjects" not in secobj:
                        secobj["subjects"] = DEFAULT_SUBJECTS[:]
                        changed = True
                    if "subject_students" not in secobj:
                        secobj["subject_students"] = {x: [] for x in DEFAULT_SUBJECTS}
                        changed = True
                    else:
                        for sub in DEFAULT_SUBJECTS:
                            if sub not in secobj["subject_students"]:
                                secobj["subject_students"][sub] = []
                                changed = True
    if changed:
        save_json(STAGES_PATH, STAGES)


def _new_section():
    return {
        "students": [],
        "subjects": DEFAULT_SUBJECTS[:],
        "subject_students": {s: [] for s in DEFAULT_SUBJECTS},
    }


def get_students(stage, section):
    return STAGES.get(stage, {}).get("sections", {}).get(section, {}).get(
        "students", []
    )


def set_students(stage, section, students):
    STAGES.setdefault(stage, {}).setdefault(
        "sections", {}
    ).setdefault(section, _new_section())["students"] = students
    save_json(STAGES_PATH, STAGES)


def add_student_to_section(stage, section, name):
    sec = STAGES.setdefault(stage, {}).setdefault(
        "sections", {}
    ).setdefault(section, _new_section())
    lst = sec.setdefault("students", [])
    if name not in lst:
        lst.append(name)
        save_json(STAGES_PATH, STAGES)
        return True
    return False


def add_student_to_subject(stage, section, subject, name):
    sec = STAGES.setdefault(stage, {}).setdefault(
        "sections", {}
    ).setdefault(section, _new_section())
    subjmap = sec.setdefault("subject_students", {})
    lst = subjmap.setdefault(subject, [])
    if name not in lst:
        lst.append(name)
        save_json(STAGES_PATH, STAGES)
        return True
    return False


# ------------------ ATTENDANCE (subject-level + legacy) ------------------


def mark_attendance(stage, section, date_str, present_map, subject=None):
    """
    إذا subject مُعطاة -> خزّن في مساحة '__subjects__' لكل مادة
    وإلا -> خزّن بالشكل القديم (قسم كامل)
    present_map: dict {student: bool}
    """
    secnode = ATTENDANCE.setdefault(date_str, {}).setdefault(
        stage, {}
    ).setdefault(section, {})
    if subject:
        subnode = secnode.setdefault("__subjects__", {}).setdefault(subject, {})
        subnode.update(present_map)
    else:
        secnode.update(present_map)
    save_json(ATTENDANCE_PATH, ATTENDANCE)


def get_attendance_for_subject(stage, section, date_str, subject):
    secnode = ATTENDANCE.get(date_str, {}).get(stage, {}).get(section, {})
    subnode = secnode.get("__subjects__", {}).get(subject, {})
    return dict(subnode)


def get_attendance_history(stage, section, subject=None):
    hist = {}
    for date in sorted(ATTENDANCE.keys(), reverse=True):
        secnode = ATTENDANCE.get(date, {}).get(stage, {}).get(section, {})
        if subject:
            subnode = secnode.get("__subjects__", {}).get(subject, {})
            if subnode:
                hist[date] = subnode
        else:
            row = {k: v for k, v in secnode.items() if k != "__subjects__"}
            if row:
                hist[date] = row
    return hist


# ------------------ QUIZZES / STATS ------------------


def add_quiz(quiz_obj, meta):
    qid = new_id("quiz")
    QUIZZES.setdefault("quizzes", {})[qid] = {
        "title": quiz_obj.get("title", ""),
        "questions": quiz_obj.get("questions", []),
        "meta": meta,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    QUIZZES["active_id"] = qid
    save_json(QUIZ_PATH, QUIZZES)
    return qid


def delete_quiz(quiz_id):
    if quiz_id in QUIZZES.get("quizzes", {}):
        del QUIZZES["quizzes"][quiz_id]
        save_json(QUIZ_PATH, QUIZZES)
        if quiz_id in QUIZ_STATS:
            del QUIZ_STATS[quiz_id]
            save_json(QUIZ_STATS_PATH, QUIZ_STATS)
        modified = False
        for user, udata in list(PROGRESS.items()):
            if "completed" in udata and quiz_id in udata["completed"]:
                del PROGRESS[user]["completed"][quiz_id]
                modified = True
        if modified:
            save_json(PROGRESS_PATH, PROGRESS)
        return True
    return False


def ensure_quiz_stats(quiz_id):
    if quiz_id not in QUIZ_STATS:
        QUIZ_STATS[quiz_id] = {
            "questions": {},
            "total_attempts": 0,
            "total_correct": 0,
            "total_wrong": 0,
        }
        save_json(QUIZ_STATS_PATH, QUIZ_STATS)


def update_quiz_stats(quiz_id, qid, correct, wrong_answer=None):
    ensure_quiz_stats(quiz_id)
    qs = QUIZ_STATS[quiz_id]["questions"].setdefault(
        qid, {"attempts": 0, "correct": 0, "wrong": 0, "wrongs": {}}
    )
    qs["attempts"] += 1
    if correct:
        qs["correct"] += 1
        QUIZ_STATS[quiz_id]["total_correct"] += 1
    else:
        qs["wrong"] += 1
        QUIZ_STATS[quiz_id]["total_wrong"] += 1
        if wrong_answer:
            qs["wrongs"][wrong_answer] = qs["wrongs"].get(wrong_answer, 0) + 1
    QUIZ_STATS[quiz_id]["total_attempts"] += 1
    save_json(QUIZ_STATS_PATH, QUIZ_STATS)


ART_NUM_MAP = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_ans(s):
    if s is None:
        return ""
    t = str(s).strip().lower()
    t = t.translate(ART_NUM_MAP)
    t = re.sub(
        r"[^\w\s\-\+\=x/آأإءؤئًٌٍَُِّٰٔٱٔ]", "", t
    )
    t = re.sub(r"\s+", " ", t).strip()
    return t


def build_subject_pool(subject):
    subject = str(subject).strip().lower()
    if subject in ("mathematics", "math"):
        return [("mul", None)]
    if subject == "arabic":
        return [
            ("إعراب 'الولدُ' في الجملة: 'الولدُ يقرأُ كتابًا'.", "الولدُ: مبتدأ"),
            ("إعراب 'يقرأُ' في الجملة: 'الولدُ يقرأُ كتابًا'.", "يقرأُ: فعل"),
            ("إعراب 'كتابًا' في الجملة: 'الولدُ يقرأُ كتابًا'.", "كتابًا: مفعول به"),
            ("إعراب 'السماءُ' في: 'السماءُ صافيةٌ'.", "السماءُ: مبتدأ"),
            ("إعراب 'صافيةٌ' في: 'السماءُ صافيةٌ'.", "صافيةٌ: خبر"),
        ]
    if subject == "english":
        return [
            (
                "Identify the part of speech of 'run' in: 'I run every morning.'",
                "verb",
            ),
            ("Identify the part of speech of 'beautiful' in: 'She is beautiful.'", "adjective"),
            ("Identify the part of speech of 'happiness' in: 'Happiness is important.'", "noun"),
        ]
    if subject == "science":
        return [
            ("What is H2O?", "Water"),
            ("What planet is known as the Red Planet?", "Mars"),
            ("What gas do plants absorb from the atmosphere?", "Carbon dioxide"),
        ]
    if subject == "history":
        return [
            ("Who discovered America (1492)?", "Christopher Columbus"),
            ("Which year did World War II end?", "1945"),
            ("Who was the first President of the United States?", "George Washington"),
        ]
    if subject == "geography":
        return [
            ("Capital of France?", "Paris"),
            ("Capital of Japan?", "Tokyo"),
            ("Capital of Egypt?", "Cairo"),
        ]
    if subject == "computer":
        return [
            ("What does CPU stand for?", "Central Processing Unit"),
            ("What does RAM stand for?", "Random Access Memory"),
            ("What is the primary language of web pages?", "HTML"),
        ]
    if subject == "religion":
        return [
            ("What is the holy book of Islam called?", "Quran"),
            ("How many daily prayers are there in Islam?", "Five"),
            ("What is the pilgrimage to Mecca called?", "Hajj"),
        ]
    return [
        ("What is 2+2?", "4"),
        ("What color is the sky on a clear day?", "Blue"),
    ]


def generate_subject_questions(subject, count=10, shuffle=True):
    pool = build_subject_pool(subject)
    questions = []
    subject_key = str(subject).strip().lower()
    if subject_key in ("mathematics", "math"):
        candidates = [(a, b, a * b) for a in range(1, 13) for b in range(1, 13)]
        random.shuffle(candidates)
        picked = candidates[: max(1, min(count, len(candidates)))]
        for a, b, c in picked:
            q_text = f"{a} × {b} = ?"
            questions.append({"id": new_id("q"), "q": q_text, "a": str(c)})
        if shuffle:
            random.shuffle(questions)
        return questions
    items = list(pool)
    if shuffle:
        random.shuffle(items)
    idx = 0
    while len(questions) < count:
        base_q, base_a = items[idx % len(items)]
        questions.append({"id": new_id("q"), "q": base_q, "a": base_a})
        idx += 1
        if idx > 1000:
            break
    return questions[:count]
