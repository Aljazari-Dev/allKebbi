# server.py — Kebbi Dashboard (split version)
import os

from flask import Flask, request, jsonify, redirect, url_for, render_template_string
from urllib.parse import unquote_plus
import datetime
from collections import Counter
import requests
from app.config import (
    SETTINGS_PATH, ROBOTS_PATH, STAGES_PATH,
    QUIZ_PATH, QUIZ_STATS_PATH, ATTENDANCE_PATH,
    PROGRESS_PATH, save_json, now_iso, DEFAULT_SUBJECTS, new_id
)

from app.storage import (
    SETTINGS,                      # ← هذا اللي ينقصك
    ROBOTS, STAGES, QUIZZES, QUIZ_STATS, ATTENDANCE, PROGRESS,
    ensure_stage_structure, get_students, set_students,
    mark_attendance, get_attendance_for_subject, get_attendance_history,
    add_quiz, delete_quiz, update_quiz_stats,
    generate_subject_questions, normalize_ans
)


from app.templates import (
    layout, HOME_HTML, STAGES_HTML, STAGE_PAGE_HTML,
    SECTION_DASH_HTML, STUDENTS_PAGE_HTML, SUBJECTS_PAGE_HTML,
    SUBJECT_PAGE_HTML, ATTENDANCE_SUBJECT_HTML, QUIZZES_SUBJECT_HTML,
    QUIZ_CREATE_HTML, QUIZ_GENERATE_HTML, QUIZ_AI_GENERATE_HTML,
    QUIZ_PREVIEW_HTML, QUIZ_STATS_HTML, QUIZ_SCORES_HTML,
    ATTENDANCE_VIEW_HTML, ANALYTICS_HTML, SETTINGS_HTML,
    SUBJECT_RAG_HTML
)

from app.ai_utils import classify_intent, lang_rule_system

from app.rag_utils import (
    subject_book_exists, save_uploaded_book,
    subject_rag_answer, run_book_rag, wrap_contexts
)


# ------------------ FLASK APP ------------------
app = Flask(__name__)

# ------------------ ROUTES ------------------


@app.route("/")
def home_page():
    ensure_stage_structure()
    return render_template_string(
        layout("Home", "home", HOME_HTML),
        robots=ROBOTS,
        stages=STAGES.keys(),
    )


# Robots endpoints
@app.route("/robot/add", methods=["POST"])
def robot_add():
    serial = (request.form.get("serial") or "").strip()
    name = (request.form.get("name") or "").strip()
    linked_stage = (request.form.get("linked_stage") or "").strip()
    linked_section = (request.form.get("linked_section") or "").strip()
    if not serial:
        return "Missing serial", 400
    ROBOTS[serial] = {
        "name": name,
        "linked_stage": linked_stage or None,
        "linked_section": linked_section or None,
        "active": True,
        "connected": False,
        "created_at": now_iso(),
    }
    save_json(ROBOTS_PATH, ROBOTS)
    return redirect(url_for("home_page"))


@app.route("/robot/toggle", methods=["POST"])
def robot_toggle():
    serial = (request.form.get("serial") or "").strip()
    if serial in ROBOTS:
        ROBOTS[serial]["active"] = not ROBOTS[serial].get("active", False)
        save_json(ROBOTS_PATH, ROBOTS)
    return redirect(url_for("home_page"))


@app.route("/robot/delete", methods=["POST"])
def robot_delete():
    serial = (request.form.get("serial") or "").strip()
    if serial in ROBOTS:
        del ROBOTS[serial]
        save_json(ROBOTS_PATH, ROBOTS)
    return redirect(url_for("home_page"))


# STAGES list
@app.route("/stages")
def stages_page():
    ensure_stage_structure()
    return render_template_string(
        layout("Stages", "stages", STAGES_HTML),
        stages=STAGES,
    )


# Stage page
@app.route("/stages/<stage>")
def stage_page(stage):
    s = STAGES.get(stage)
    if not s:
        return "Not found", 404
    return render_template_string(
        layout(stage, "stages", STAGE_PAGE_HTML),
        stage=stage,
        sections=s.get("sections", {}),
    )


# Section dashboard
@app.route("/stages/<stage>/<section>")
def section_dashboard(stage, section):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    students = sdata.get("students", [])
    subjects = sdata.get("subjects", DEFAULT_SUBJECTS[:])
    if "subject_students" not in sdata:
        sdata["subject_students"] = {s: [] for s in DEFAULT_SUBJECTS}
        save_json(STAGES_PATH, STAGES)
    return render_template_string(
        layout(f"{stage} — Section {section}", "stages", SECTION_DASH_HTML),
        stage=stage,
        section=section,
        students=students,
        subjects=subjects,
    )


# Students page
@app.route("/stages/<stage>/<section>/students", methods=["GET"])
def section_students_page(stage, section):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    students = sdata.get("students", [])
    return render_template_string(
        layout("Students", "stages", STUDENTS_PAGE_HTML),
        stage=stage,
        section=section,
        students=students,
    )


# Subjects page
@app.route("/stages/<stage>/<section>/subjects", methods=["GET"])
def section_subjects_page(stage, section):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    subjects = sdata.get("subjects", DEFAULT_SUBJECTS[:])
    if "subject_students" not in sdata:
        sdata["subject_students"] = {s: [] for s in subjects}
        save_json(STAGES_PATH, STAGES)
    return render_template_string(
        layout("Subjects", "stages", SUBJECTS_PAGE_HTML),
        stage=stage,
        section=section,
        subjects=subjects,
    )


# Subject page
@app.route("/stages/<stage>/<section>/subjects/<subject>")
def subject_page(stage, section, subject):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    subjects = sdata.get("subjects", DEFAULT_SUBJECTS[:])
    if subject not in subjects:
        return "Subject not found", 404
    return render_template_string(
        layout(f"{subject}", "stages", SUBJECT_PAGE_HTML),
        stage=stage,
        section=section,
        subject=subject,
    )


@app.route(
    "/stages/<stage>/<section>/subjects/<subject>/attendance",
    methods=["GET"],
)
def attendance_subject_page(stage, section, subject):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404

    subj_map = sdata.get("subject_students")
    if subj_map is None:
        sdata["subject_students"] = {
            s: [] for s in sdata.get("subjects", DEFAULT_SUBJECTS[:])
        }
        subj_map = sdata["subject_students"]
        save_json(STAGES_PATH, STAGES)

    students = subj_map.get(subject, [])
    today = datetime.date.today().isoformat()
    attendance_today = get_attendance_for_subject(stage, section, today, subject)

    return render_template_string(
        layout("Attendance", "stages", ATTENDANCE_SUBJECT_HTML),
        stage=stage,
        section=section,
        subject=subject,
        students=students,
        attendance=attendance_today,
    )


# NEW: Subject RAG page
@app.route("/stages/<stage>/<section>/subjects/<subject>/book", methods=["GET", "POST"])
def subject_rag_page(stage, section, subject):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    subjects = sdata.get("subjects", DEFAULT_SUBJECTS[:])
    if subject not in subjects:
        return "Subject not found", 404

    has_book = subject_book_exists(stage, section, subject)
    question = ""
    answer = ""
    message = ""
    ctx_list = []

    if request.method == "POST":
        file = request.files.get("file")
        if file and file.filename:
            if not file.filename.lower().endswith(".docx"):
                message = "الرجاء رفع ملف بصيغة .docx فقط."
            else:
                ok, err = save_uploaded_book(file, stage, section, subject)
                if ok:
                    message = "تم رفع الكتاب ومعالجته بنجاح. يمكنك الآن طرح الأسئلة."
                    has_book = True
                else:
                    message = f"حدث خطأ أثناء معالجة الكتاب: {err}"
                    has_book = subject_book_exists(stage, section, subject)
        else:
            question = (request.form.get("question") or "").strip()
            if question:
                if not has_book:
                    message = "لم يتم رفع كتاب لهذه المادة بعد."
                else:
                    ans, retrieved, err = subject_rag_answer(
                        question, stage, section, subject
                    )
                    if err:
                        message = f"خطأ في استدعاء الذكاء الاصطناعي: {err}"
                    else:
                        answer = ans
                        ctx_list = wrap_contexts(retrieved)

    return render_template_string(
        layout("Book Assistant", "stages", SUBJECT_RAG_HTML),
        stage=stage,
        section=section,
        subject=subject,
        has_book=has_book,
        question=question,
        answer=answer,
        message=message,
        contexts=ctx_list,
    )


# Quizzes for a subject (list + create/generate)
@app.route("/stages/<stage>/<section>/<subject>/quizzes")
def quizzes_subject_page(stage, section, subject):
    sdata = STAGES.get(stage, {}).get("sections", {}).get(section)
    if sdata is None:
        return "Not found", 404
    qlist = []
    for qid, q in QUIZZES.get("quizzes", {}).items():
        meta = q.get("meta", {})
        if (
            meta.get("stage") == stage
            and meta.get("section") == section
            and str(meta.get("subject", "")).lower() == str(subject).lower()
        ):
            qlist.append(
                {
                    "quiz_id": qid,
                    "title": q.get("title", ""),
                    "count": len(q.get("questions", [])),
                }
            )
    return render_template_string(
        layout("Quizzes", "stages", QUIZZES_SUBJECT_HTML),
        stage=stage,
        section=section,
        subject=subject,
        quizzes=qlist,
    )


# Add / remove student
@app.route("/stages/<stage>/<section>/student/add", methods=["POST"])
def add_student(stage, section):
    name = (request.form.get("name") or "").strip()
    if not name:
        return redirect(
            url_for("section_students_page", stage=stage, section=section)
        )
    students = get_students(stage, section)
    if name not in students:
        students.append(name)
        set_students(stage, section, students)
    return redirect(url_for("section_students_page", stage=stage, section=section))


@app.route("/stages/<stage>/<section>/student/remove", methods=["POST"])
def remove_student(stage, section):
    name = (request.form.get("name") or "").strip()
    students = get_students(stage, section)
    if name in students:
        students.remove(name)
        set_students(stage, section, students)
    return redirect(url_for("section_students_page", stage=stage, section=section))


@app.route("/stages/<stage>/<section>/reset", methods=["POST"])
def section_reset(stage, section):
    set_students(stage, section, [])
    return redirect(url_for("stage_page", stage=stage))


# Attendance mark (works for section; optional subject forwarded)
@app.route("/stages/<stage>/<section>/attendance", methods=["POST"])
def attendance_mark(stage, section):
    form = request.form
    present_map = {}
    idx = 0
    while True:
        key_name = f"name_{idx}"
        key_present = f"present_{idx}"
        if key_name not in form:
            break
        name = form.get(key_name)
        present = form.get(key_present) is not None
        present_map[name] = present
        idx += 1
    date_str = datetime.date.today().isoformat()
    subject = (form.get("subject") or "").strip()
    mark_attendance(
        stage, section, date_str, present_map, subject=(subject or None)
    )
    if subject:
        return redirect(
            url_for("subject_page", stage=stage, section=section, subject=subject)
        )
    return redirect(url_for("section_students_page", stage=stage, section=section))


@app.route("/stages/<stage>/<section>/attendance/view")
def attendance_view(stage, section):
    students = get_students(stage, section)
    history = get_attendance_history(stage, section)
    return render_template_string(
        layout("Attendance History", "stages", ATTENDANCE_VIEW_HTML),
        stage=stage,
        section=section,
        students=students,
        history=history,
    )


# QUIZZES: list all (disabled)
@app.route("/quizzes")
def quizzes_list_page():
    return (
        jsonify(
            {
                "ok": False,
                "error": "global quizzes listing is disabled. Use subject-specific endpoints.",
            }
        ),
        404,
    )


# Create quiz for subject (manual)
@app.route("/quizzes/create/<stage>/<section>/<subject>", methods=["GET", "POST"])
def quiz_create_for_subject(stage, section, subject):
    if request.method == "GET":
        return render_template_string(
            layout("Create Quiz", "stages", QUIZ_CREATE_HTML),
            stage=stage,
            section=section,
            subject=subject,
        )
    title = (request.form.get("title") or "").strip()
    bulk = (request.form.get("bulk") or "").strip()
    questions = []
    for ln in bulk.splitlines():
        if "::" in ln:
            q, a = ln.split("::", 1)
            questions.append(
                {"id": new_id("q"), "q": q.strip(), "a": a.strip()}
            )
    if questions:
        add_quiz(
            {"title": title, "questions": questions},
            {"stage": stage, "section": section, "subject": subject},
        )
    return redirect(
        url_for("quizzes_subject_page", stage=stage, section=section, subject=subject)
    )


# Generate auto (fallback non-AI)
@app.route("/quizzes/generate/<stage>/<section>/<subject>", methods=["GET", "POST"])
def quiz_generate_for_subject(stage, section, subject):
    if request.method == "GET":
        return render_template_string(
            layout("Generate Quiz", "stages", QUIZ_GENERATE_HTML),
            stage=stage,
            section=section,
            subject=subject,
        )
    title = (request.form.get("title") or f"Auto {subject} Quiz").strip()
    try:
        count = int(request.form.get("count", "10"))
    except Exception:
        count = 10
    shuffle_flag = request.form.get("shuffle", "1") == "1"
    questions = generate_subject_questions(
        subject, count=count, shuffle=shuffle_flag
    )
    if not questions:
        questions = [
            {"id": new_id("q"), "q": "What is 1+1?", "a": "2"}
        ]
    add_quiz(
        {"title": title, "questions": questions},
        {"stage": stage, "section": section, "subject": subject},
    )
    return redirect(
        url_for("quizzes_subject_page", stage=stage, section=section, subject=subject)
    )


# Generate with AI from teacher input
@app.route("/quizzes/generate_ai/<stage>/<section>/<subject>", methods=["GET", "POST"])
def quiz_generate_ai_for_subject(stage, section, subject):
    from app.storage import generate_subject_questions  # to avoid circular import
    from app.ai_utils import openai_chat_completion

    if request.method == "GET":
        return render_template_string(
            layout("Generate Quiz with AI", "stages", QUIZ_AI_GENERATE_HTML),
            stage=stage,
            section=section,
            subject=subject,
        )
    lesson = (request.form.get("lesson") or "").strip()
    title = (request.form.get("title") or f"AI-generated {subject} Quiz").strip()
    try:
        count = int(request.form.get("count", "8"))
    except Exception:
        count = 8
    difficulty = (request.form.get("difficulty") or "medium").strip().lower()
    qtype = (request.form.get("qtype") or "short").strip()

    system_prompt = SETTINGS.get("system_prompt", "")
    prompt = f"""You are an assistant that generates short classroom quizzes.

Subject: {subject}
Lesson / teacher description:
{lesson}

Requirements:
- Generate exactly {count} questions (or as close as possible).
- Difficulty: {difficulty}.
- Question format: if qtype is 'short' produce lines in the format:
    Question :: Answer
  If qtype is 'mcq' produce lines in the format:
    Question :: CorrectAnswer :: ChoiceA | ChoiceB | ChoiceC | ChoiceD
- Try to match the language of the subject (Arabic questions in Arabic for Arabic subject).
- Keep each question short and the answer concise.
- Do NOT include numbering or extra commentary, only the lines described above, one per line.

Return only the questions in the requested format.
"""
    ai_text, err = openai_chat_completion(system_prompt, prompt)
    if err:
        fallback_questions = generate_subject_questions(
            subject, count=count, shuffle=True
        )
        add_quiz(
            {"title": title + " (fallback)", "questions": fallback_questions},
            {"stage": stage, "section": section, "subject": subject},
        )
        body = (
            "<div class='card'><h3>AI Generation Error</h3>"
            f"<div class='small'>{err}</div>"
            f"<div style='margin-top:8px'><a class='btn' href='{url_for('quizzes_subject_page', stage=stage, section=section, subject=subject)}'>Back to quizzes</a></div></div>"
        )
        return render_template_string(layout("AI Generation Error", "stages", body))

    qas = parse_ai_output_to_qa(ai_text, qtype=qtype)
    if not qas:
        fallback_questions = generate_subject_questions(
            subject, count=count, shuffle=True
        )
        add_quiz(
            {"title": title + " (fallback)", "questions": fallback_questions},
            {"stage": stage, "section": section, "subject": subject},
        )
        body = (
            "<div class='card'><h3>AI returned no parsable Q/A</h3>"
            "<div class='small'>Stored fallback quiz.</div>"
            f"<div style='margin-top:8px'><a class='btn' href='{url_for('quizzes_subject_page', stage=stage, section=section, subject=subject)}'>Back to quizzes</a></div></div>"
        )
        return render_template_string(layout("AI Parsing Error", "stages", body))

    if len(qas) > count:
        qas = qas[:count]
    elif len(qas) < count:
        extra = generate_subject_questions(
            subject, count=(count - len(qas)), shuffle=True
        )
        qas.extend(extra)

    add_quiz(
        {"title": title, "questions": qas},
        {"stage": stage, "section": section, "subject": subject},
    )
    return redirect(
        url_for("quizzes_subject_page", stage=stage, section=section, subject=subject)
    )


def parse_ai_output_to_qa(text, qtype="short"):
    if not text:
        return []
    from app.config import new_id
    qas = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split("::")]
        if len(parts) >= 2:
            q = parts[0]
            a = parts[1]
            entry = {"id": new_id("q"), "q": q, "a": a}
            if len(parts) >= 3:
                choices = parts[2]
                import re as _re

                choices_list = [
                    c.strip() for c in _re.split(r"\||,", choices) if c.strip()
                ]
                entry["choices"] = choices_list
            qas.append(entry)
        else:
            if "?" in line and "-" in line:
                qpart, apart = line.split("-", 1)
                qas.append(
                    {"id": new_id("q"), "q": qpart.strip(), "a": apart.strip()}
                )
    return qas


@app.route("/quizzes/preview/<quiz_id>")
def quiz_preview(quiz_id):
    q = QUIZZES.get("quizzes", {}).get(quiz_id)
    if not q:
        return "Not found", 404
    meta = q.get("meta", {})
    return render_template_string(
        layout("Quiz Preview", "stages", QUIZ_PREVIEW_HTML),
        quiz=q,
        quiz_id=quiz_id,
        meta=meta,
    )


@app.route("/quizzes/stats/<quiz_id>")
def quiz_stats_page(quiz_id):
    q = QUIZZES.get("quizzes", {}).get(quiz_id)
    if not q:
        return "Not found", 404
    stats = QUIZ_STATS.get(quiz_id, {})
    totals = {
        "total_attempts": stats.get("total_attempts", 0),
        "total_correct": stats.get("total_correct", 0),
        "total_wrong": stats.get("total_wrong", 0),
        "acc": round(
            (100.0 * stats.get("total_correct", 0) / stats.get("total_attempts", 1)),
            1,
        )
        if stats.get("total_attempts", 0)
        else 0.0,
    }
    rows = []
    for qitem in q.get("questions", []):
        qid = qitem["id"]
        qstats = stats.get("questions", {}).get(qid, {})
        common = (
            ", ".join(
                [
                    f"{k}:{v}"
                    for k, v in Counter(qstats.get("wrongs", {})).most_common(3)
                ]
            )
            if qstats
            else ""
        )
        rows.append(
            {
                "q": qitem["q"],
                "attempts": qstats.get("attempts", 0),
                "correct": qstats.get("correct", 0),
                "wrong": qstats.get("wrong", 0),
                "common": common,
            }
        )
    return render_template_string(
        layout("Quiz Stats", "stages", QUIZ_STATS_HTML),
        quiz=q,
        quiz_id=quiz_id,
        totals=totals,
        rows=rows,
    )


@app.route("/quizzes/delete/<quiz_id>", methods=["POST"])
def quiz_delete(quiz_id):
    ok = delete_quiz(quiz_id)
    return redirect(url_for("quizzes_list_page"))


@app.route("/quizzes/scores/<quiz_id>")
def quiz_scores_page(quiz_id):
    q = QUIZZES.get("quizzes", {}).get(quiz_id)
    if not q:
        return "Not found", 404
    meta = q.get("meta", {})
    stage = meta.get("stage")
    section = meta.get("section")
    subject = meta.get("subject")
    students = []
    if stage and section:
        students = get_students(stage, section)
    rows = []
    for s in students:
        rec = PROGRESS.get(s, {}).get("completed", {}).get(quiz_id)
        if rec:
            rows.append(
                {
                    "student": s,
                    "score": rec.get("score"),
                    "total": rec.get("total"),
                    "finished_at": rec.get("finished_at"),
                }
            )
        else:
            rows.append(
                {
                    "student": s,
                    "score": None,
                    "total": None,
                    "finished_at": None,
                }
            )
    return render_template_string(
        layout("Quiz Scores", "stages", QUIZ_SCORES_HTML),
        quiz=q,
        quiz_id=quiz_id,
        meta=meta,
        rows=rows,
    )


# Submit quiz answers API (robot/mobile)
@app.route("/quizzes/submit/<quiz_id>", methods=["POST"])
def quiz_submit(quiz_id):
    data = request.get_json(force=True, silent=True) or {}
    student = data.get("student")
    answers = data.get("answers", [])
    if not student:
        return jsonify({"ok": False, "error": "missing student"}), 400
    quiz = QUIZZES.get("quizzes", {}).get(quiz_id)
    if not quiz:
        return jsonify({"ok": False, "error": "invalid quiz_id"}), 400
    score = 0
    for a in answers:
        qid = a.get("qid")
        ans = str(a.get("answer", ""))
        qobj = next(
            (it for it in quiz.get("questions", []) if it.get("id") == qid), None
        )
        if not qobj:
            continue
        correct_ans = str(qobj.get("a", ""))
        correct = normalize_ans(ans) == normalize_ans(correct_ans)
        update_quiz_stats(
            quiz_id, qid, correct, wrong_answer=(ans if not correct else None)
        )
        if correct:
            score += 1
    PROGRESS.setdefault(student, {}).setdefault("completed", {})[quiz_id] = {
        "score": score,
        "total": len(quiz.get("questions", [])),
        "finished_at": now_iso(),
    }
    save_json(PROGRESS_PATH, PROGRESS)
    return jsonify(
        {"ok": True, "score": score, "total": len(quiz.get("questions", []))}
    )


# ANALYTICS
@app.route("/analytics")
def analytics_page():
    per_stage = {}
    total_students = 0
    for sname, sdata in STAGES.items():
        cnt = 0
        for sec, secdata in sdata.get("sections", {}).items():
            cnt += len(secdata.get("students", []))
        per_stage[sname] = cnt
        total_students += cnt
    today = datetime.date.today().isoformat()
    attendance_today = ATTENDANCE.get(today, {})
    present = 0
    checked = 0
    for sname, sdata in attendance_today.items():
        for sec, secmap in sdata.items():
            for st, val in secmap.items():
                checked += 1
                if val:
                    present += 1
    pct = round((100.0 * present / checked), 1) if checked else 0.0
    total_quiz_attempts = sum(
        v.get("total_attempts", 0) for v in QUIZ_STATS.values()
    )
    totals = {
        "total_students": total_students,
        "attendance_pct": pct,
        "total_quiz_attempts": total_quiz_attempts,
        "per_stage": per_stage,
    }
    return render_template_string(
        layout("Analytics", "analytics", ANALYTICS_HTML),
        totals=totals,
    )


# SETTINGS
@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    global SETTINGS
    if request.method == "POST":
        api_key = (request.form.get("api_key") or "").strip()
        model = (request.form.get("model") or "").strip()
        try:
            temperature = float(request.form.get("temperature") or "0.3")
        except Exception:
            temperature = 0.3
        try:
            max_tokens = int(request.form.get("max_tokens") or "400")
        except Exception:
            max_tokens = 400
        system_prompt = (request.form.get("system_prompt") or "").strip()
        always_correct = request.form.get("always_correct", "0").strip() == "1"
        SETTINGS.update(
            {
                "api_key": api_key,
                "model": model,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "system_prompt": system_prompt,
                "always_correct": always_correct,
            }
        )
        save_json(SETTINGS_PATH, SETTINGS)
        return redirect(url_for("settings_page"))
    return render_template_string(
        layout("Settings", "settings", SETTINGS_HTML), **SETTINGS
    )


# Convenience redirects
@app.route("/stages/<stage>/<section>/quiz_create")
def quiz_create_redirect(stage, section):
    subj = (
        STAGES.get(stage, {})
        .get("sections", {})
        .get(section, {})
        .get("subjects", [DEFAULT_SUBJECTS[0]])[0]
    )
    return redirect(
        url_for("quiz_create_for_subject", stage=stage, section=section, subject=subj)
    )


@app.route("/stages/<stage>/<section>/quiz_generate")
def quiz_generate_redirect(stage, section):
    subj = (
        STAGES.get(stage, {})
        .get("sections", {})
        .get(section, {})
        .get("subjects", [DEFAULT_SUBJECTS[0]])[0]
    )
    return redirect(
        url_for("quiz_generate_for_subject", stage=stage, section=section, subject=subj)
    )


@app.route("/stages/<stage>/<section>/quiz_generate_ai")
def quiz_generate_ai_redirect(stage, section):
    subj = (
        STAGES.get(stage, {})
        .get("sections", {})
        .get(section, {})
        .get("subjects", [DEFAULT_SUBJECTS[0]])[0]
    )
    return redirect(
        url_for(
            "quiz_generate_ai_for_subject", stage=stage, section=section, subject=subj
        )
    )


# ------------------ Mobile API endpoints (robot + JSON) ------------------


@app.route("/api/robot/heartbeat", methods=["POST"])
def api_robot_heartbeat():
    data = request.get_json(silent=True) or {}
    serial = (data.get("serial") or "").strip()
    if not serial:
        return jsonify({"ok": False, "error": "missing serial"}), 400
    now = now_iso()
    r = ROBOTS.get(serial)
    if not r:
        ROBOTS[serial] = {
            "name": serial,
            "linked_stage": None,
            "linked_section": None,
            "active": True,
            "connected": True,
            "created_at": now,
            "last_seen": now,
        }
    else:
        r["connected"] = True
        r["active"] = True
        r["last_seen"] = now
    save_json(ROBOTS_PATH, ROBOTS)
    return jsonify({"ok": True, "serial": serial, "connected": True, "last_seen": now})


@app.route("/api/robot/disconnect", methods=["POST"])
def api_robot_disconnect():
    data = request.get_json(silent=True) or {}
    serial = (data.get("serial") or "").strip()
    if not serial:
        return jsonify({"ok": False, "error": "missing serial"}), 400
    if serial in ROBOTS:
        ROBOTS[serial]["connected"] = False
        save_json(ROBOTS_PATH, ROBOTS)
    return jsonify({"ok": True, "serial": serial, "connected": False})


@app.route("/api/stages", methods=["GET"])
def api_get_stages():
    ensure_stage_structure()
    out = {}
    for sname, sdata in STAGES.items():
        out[sname] = {"sections": list(sdata.get("sections", {}).keys())}
    return jsonify({"ok": True, "stages": out})


@app.route("/api/subjects/<stage>/<section>", methods=["GET", "POST"])
def api_get_set_subjects(stage, section):
    if request.method == "GET":
        s = STAGES.get(stage, {}).get("sections", {}).get(section)
        if s is None:
            return jsonify({"ok": False, "error": "not found"}), 404
        subjects = s.get("subjects", DEFAULT_SUBJECTS[:])
        return jsonify(
            {"ok": True, "stage": stage, "section": section, "subjects": subjects}
        )
    data = request.get_json(silent=True) or {}
    subs = data.get("subjects")
    if not isinstance(subs, list):
        return jsonify({"ok": False, "error": "invalid subjects"}), 400
    sec = STAGES.setdefault(stage, {}).setdefault(
        "sections", {}
    ).setdefault(section, _section_default())
    sec["subjects"] = subs
    ss = sec.setdefault("subject_students", {})
    for sname in subs:
        ss.setdefault(sname, [])
    save_json(STAGES_PATH, STAGES)
    return jsonify({"ok": True, "stage": stage, "section": section, "subjects": subs})


def _section_default():
    return {
        "students": [],
        "subjects": DEFAULT_SUBJECTS[:],
        "subject_students": {s: [] for s in DEFAULT_SUBJECTS},
    }


@app.route("/api/subject_students/<stage>/<section>/<subject>", methods=["GET"])
def api_get_subject_students(stage, section, subject):
    s = STAGES.get(stage, {}).get("sections", {}).get(section)
    if s is None:
        return jsonify({"ok": False, "error": "not found"}), 404
    subjmap = s.get("subject_students", {})
    students = subjmap.get(subject, [])
    return jsonify(
        {"ok": True, "stage": stage, "section": section, "subject": subject, "students": students}
    )


@app.route("/api/lessons/<stage>/<section>/<subject>", methods=["GET"])
def api_get_lessons(stage, section, subject):
    stage = unquote_plus(stage)
    section = unquote_plus(section)
    subject = unquote_plus(subject)
    subj = (subject or "").strip()
    if subj.lower() in ("", "null", "none"):
        return jsonify(
            {"ok": True, "stage": stage, "section": section, "subject": None, "lessons": []}
        )

    items = []
    for qid, q in QUIZZES.get("quizzes", {}).items():
        meta = q.get("meta", {})
        if (
            meta.get("stage") == stage
            and meta.get("section") == section
            and str(meta.get("subject", "")).strip().lower() == subj.lower()
        ):
            items.append(
                {
                    "quiz_id": qid,
                    "title": q.get("title", ""),
                    "count": len(q.get("questions", [])),
                    "created_at": q.get("created_at"),
                }
            )
    return jsonify(
        {"ok": True, "stage": stage, "section": section, "subject": subj, "lessons": items}
    )


@app.route("/registration/mark", methods=["POST"])
def registration_mark():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    subject = (data.get("subject") or "").strip()
    serial = (data.get("serial") or "").strip()
    stage_hint = unquote_plus((data.get("stage") or "").strip())
    section_hint = unquote_plus((data.get("section") or "").strip())

    if not name:
        return jsonify({"ok": False, "error": "missing name"}), 400

    found_stage = None
    found_section = None

    if stage_hint and section_hint and STAGES.get(stage_hint, {}).get(
        "sections", {}
    ).get(section_hint):
        found_stage, found_section = stage_hint, section_hint

    if not found_stage and serial and serial in ROBOTS:
        r = ROBOTS.get(serial, {})
        if r.get("linked_stage") and r.get("linked_section"):
            found_stage = r.get("linked_stage")
            found_section = r.get("linked_section")

    if not found_stage and subject:
        subj_lower = subject.lower()
        for sname, sdata in STAGES.items():
            for secname, secdata in sdata.get("sections", {}).items():
                subs = [x.lower() for x in secdata.get("subjects", [])]
                if subj_lower in subs:
                    found_stage, found_section = sname, secname
                    break
            if found_stage:
                break

    if not found_stage:
        found_stage, found_section = "Stage 1", "A"

    secobj = STAGES.setdefault(found_stage, {}).setdefault(
        "sections", {}
    ).setdefault(found_section, _section_default())

    already_in_section = name in secobj.get("students", [])
    subjmap = secobj.setdefault("subject_students", {})
    if subject:
        s_list = subjmap.setdefault(subject, [])
        already_in_subject = name in s_list
    else:
        already_in_subject = False

    added_to_section = False
    added_to_subject = False
    if not already_in_section:
        secobj.setdefault("students", []).append(name)
        added_to_section = True

    if subject:
        s_list = subjmap.setdefault(subject, [])
        if name not in s_list:
            s_list.append(name)
            added_to_subject = True

    save_json(STAGES_PATH, STAGES)

    date_str = datetime.date.today().isoformat()
    mark_attendance(
        found_stage, found_section, date_str, {name: True}, subject=(subject or None)
    )

    registered_before = already_in_section or already_in_subject

    resp = {
        "ok": True,
        "stage": found_stage,
        "section": found_section,
        "name": name,
        "subject": subject or None,
        "added_to_section": added_to_section,
        "added_to_subject": added_to_subject,
        "registered_before": registered_before,
        "attendance_marked_for": date_str,
    }
    return jsonify(resp)


@app.get("/__routes")
def __routes():
    return {"routes": [str(r) for r in app.url_map.iter_rules()]}


# --- Simple in-memory sessions (not persisted) ---
SESSIONS = {}


@app.route("/stages/<stage>/<section>/subjects/<subject>/attendance/view")
def attendance_view_subject(stage, section, subject):
    students = get_students(stage, section)
    history = get_attendance_history(stage, section, subject=subject)
    return render_template_string(
        layout("Attendance History", "stages", ATTENDANCE_VIEW_HTML),
        stage=stage,
        section=section,
        students=students,
        history=history,
    )


@app.route("/quizzes/api/list")
def api_quizzes_list():
    raw_subj = (request.args.get("subject") or "").strip()
    subj = raw_subj.lower().strip()
    stage_filter = (request.args.get("stage") or "").strip()
    section_filter = (request.args.get("section") or "").strip()

    if not subj and not (stage_filter and section_filter):
        return jsonify({"ok": True, "quizzes": []})

    synonyms = {
        "math": "mathematics",
        "mathematics": "mathematics",
        "computer": "computer",
        "computing": "computer",
        "cs": "computer",
        "eng": "english",
        "english": "english",
        "arabic": "arabic",
        "science": "science",
        "history": "history",
        "geography": "geography",
        "religion": "religion",
    }

    def norm(s):
        return (s or "").strip().lower()

    def subject_matches(meta_subject, query_subj):
        if not query_subj:
            return True
        ms = norm(meta_subject)
        qs = norm(query_subj)
        if not ms or not qs:
            return False
        if ms == qs:
            return True
        if qs in synonyms and synonyms.get(qs) == ms:
            return True
        if ms in synonyms and synonyms.get(ms) == qs:
            return True
        if len(qs) >= 4 and (qs in ms or ms in qs):
            return True
        return False

    items = []
    for qid, q in QUIZZES.get("quizzes", {}).items():
        meta = q.get("meta", {}) or {}
        qstage = meta.get("stage") or ""
        qsection = meta.get("section") or ""
        qsubject = meta.get("subject") or ""
        if stage_filter and norm(qstage) != norm(stage_filter):
            continue
        if section_filter and norm(qsection) != norm(section_filter):
            continue
        if subj:
            if not subject_matches(qsubject, subj):
                title = q.get("title", "")
                if subj not in norm(title):
                    continue
        items.append(
            {
                "quiz_id": qid,
                "title": q.get("title", ""),
                "count": len(q.get("questions", [])),
                "meta": meta,
            }
        )
    return jsonify({"ok": True, "quizzes": items})


@app.route("/quizzes/api/active")
def api_quizzes_active():
    aid = QUIZZES.get("active_id")
    if not aid:
        return jsonify({"ok": True, "active": None})
    q = QUIZZES.get("quizzes", {}).get(aid)
    if not q:
        return jsonify({"ok": True, "active": None})
    return jsonify(
        {
            "ok": True,
            "active": {
                "quiz_id": aid,
                "title": q.get("title", ""),
                "count": len(q.get("questions", [])),
                "meta": q.get("meta", {}),
            },
        }
    )


@app.route("/quizzes/api/start", methods=["POST"])
def api_quizzes_start():
    data = request.get_json(silent=True) or {}
    quiz_id = (data.get("quiz_id") or "").strip()
    student = (data.get("student_name") or "").strip()
    q = QUIZZES.get("quizzes", {}).get(quiz_id)
    if not q:
        return jsonify({"ok": False, "error": "invalid_quiz_id"}), 400
    total = len(q.get("questions", []))
    if student:
        rec = PROGRESS.get(student, {}).get("completed", {}).get(quiz_id)
        if rec:
            return jsonify(
                {
                    "ok": False,
                    "already_done": True,
                    "score": rec.get("score", 0),
                    "total": rec.get("total", total),
                }
            )
    sid = f"sess_{len(SESSIONS)+1}"
    SESSIONS[sid] = {
        "quiz_id": quiz_id,
        "student": student or None,
        "index": 0,
        "score": 0,
        "total": total,
        "started_at": now_iso(),
    }
    return jsonify({"ok": True, "session_id": sid, "total": total})


@app.route("/quizzes/api/next")
def api_quizzes_next():
    sid = request.args.get("session_id", "").strip()
    s = SESSIONS.get(sid)
    if not s:
        return jsonify({"ok": False, "error": "invalid_session"}), 400
    quiz = QUIZZES.get("quizzes", {}).get(s["quiz_id"])
    if not quiz:
        return jsonify({"ok": False, "error": "invalid_quiz"}), 400
    idx = s["index"]
    total = s.get("total", 0)
    if idx >= total:
        return jsonify(
            {"ok": True, "done": True, "score": s.get("score", 0), "total": total}
        )
    qobj = quiz.get("questions", [])[idx]
    qtext = qobj.get("q", "")
    return jsonify(
        {
            "ok": True,
            "done": False,
            "question": qtext,
            "num": idx + 1,
            "total": total,
        }
    )


@app.route("/quizzes/api/answer", methods=["POST"])
def api_quizzes_answer():
    data = request.get_json(silent=True) or {}
    sid = (data.get("session_id") or "").strip()
    ans = data.get("answer", "")
    s = SESSIONS.get(sid)
    if not s:
        return jsonify({"ok": False, "error": "invalid_session"}), 400
    quiz = QUIZZES.get("quizzes", {}).get(s["quiz_id"])
    if not quiz:
        return jsonify({"ok": False, "error": "invalid_quiz"}), 400
    idx = s["index"]
    if idx >= s.get("total", 0):
        return jsonify({"ok": False, "error": "already_done"}), 400
    qobj = quiz.get("questions", [])[idx]
    correct_expected = str(qobj.get("a", ""))
    correct_flag = normalize_ans(ans) == normalize_ans(correct_expected)
    update_quiz_stats(
        s["quiz_id"],
        qobj.get("id"),
        correct_flag,
        wrong_answer=(ans if not correct_flag else None),
    )
    if correct_flag:
        s["score"] = s.get("score", 0) + 1
    s["index"] = idx + 1
    remaining = s.get("total", 0) - s["index"]
    if s["index"] >= s.get("total", 0):
        student = s.get("student")
        if student:
            PROGRESS.setdefault(student, {}).setdefault(
                "completed", {}
            )[s["quiz_id"]] = {
                "score": s.get("score", 0),
                "total": s.get("total", 0),
                "finished_at": now_iso(),
            }
            save_json(PROGRESS_PATH, PROGRESS)
    return jsonify(
        {
            "ok": True,
            "correct": correct_flag,
            "expected": correct_expected,
            "remaining": remaining,
        }
    )


@app.route("/quizzes/api/finish")
def api_quizzes_finish():
    sid = request.args.get("session_id", "").strip()
    s = SESSIONS.get(sid)
    if not s:
        return jsonify({"ok": False, "error": "invalid_session"}), 400
    score = s.get("score", 0)
    total = s.get("total", 0)
    student = s.get("student")
    if student:
        PROGRESS.setdefault(student, {}).setdefault("completed", {})[
            s["quiz_id"]
        ] = {
            "score": score,
            "total": total,
            "finished_at": now_iso(),
        }
        save_json(PROGRESS_PATH, PROGRESS)
    return jsonify({"ok": True, "score": score, "total": total})


# CHAT endpoint (نفس المنطق القديم مع lang_rule_system)
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    user_text = (data.get("user_text") or "").strip()
    lang = (data.get("lang") or "en-US").strip()
    if not user_text:
        return jsonify({"reply": ""})

    api_key = SETTINGS.get("api_key", "").strip()
    if not api_key:
        return (
            jsonify(
                {
                    "reply": "Server is missing API key. Open /settings and set it."
                }
            ),
            500,
        )

    sys_prompt = SETTINGS.get("system_prompt") or ""
    lang_gate = lang_rule_system(lang)

    model = SETTINGS.get("model", "gpt-3.5-turbo")
    temperature = float(SETTINGS.get("temperature", 0.3))
    max_tokens = int(SETTINGS.get("max_tokens", 120))

    try:
        payload = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "system", "content": lang_gate},
                {"role": "user", "content": f"[lang={lang}] {user_text}"},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        if 200 <= r.status_code < 300:
            j = r.json()
            reply = (
                j.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            return jsonify({"reply": reply})
        else:
            return (
                jsonify(
                    {"reply": f"Upstream error {r.status_code}: {r.text[:300]}"}
                ),
                502,
            )
    except Exception as e:
        return jsonify({"reply": f"Server exception: {e}"}), 500


@app.route("/api/book/query/<stage>/<section>/<subject>", methods=["POST"])
def api_book_query(stage, section, subject):
    stage = unquote_plus(stage)
    section = unquote_plus(section)
    subject = unquote_plus(subject)

    payload = request.get_json(force=True) or {}
    question = (payload.get("question") or "").strip()
    lang = (payload.get("lang") or "ar-SA").strip()

    if not question:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "missing_question",
                    "msg": "لم يصل أي سؤال من الروبوت.",
                }
            ),
            400,
        )

    intent_data = classify_intent(question, lang=lang)
    intent = intent_data.get("intent")
    need_rag = bool(intent_data.get("need_rag", False))
    router_reply = (intent_data.get("assistant_reply") or "").strip()

    if not need_rag:
        return jsonify(
            {
                "ok": True,
                "reply": router_reply,
                "intent": intent,
                "from": "router",
                "stage": stage,
                "section": section,
                "subject": subject,
            }
        )

    rag_reply = run_book_rag(
        stage=stage,
        section=section,
        subject=subject,
        question=question,
        lang=lang,
    )

    return jsonify(
        {
            "ok": True,
            "reply": rag_reply,
            "intent": intent,
            "from": "rag",
            "stage": stage,
            "section": section,
            "subject": subject,
        }
    )


# ------------------ START ------------------
if __name__ == "__main__":
    ensure_stage_structure()
    save_json(SETTINGS_PATH, SETTINGS)
    save_json(ROBOTS_PATH, ROBOTS)
    save_json(STAGES_PATH, STAGES)
    save_json(QUIZ_PATH, QUIZZES)
    save_json(QUIZ_STATS_PATH, QUIZ_STATS)
    save_json(ATTENDANCE_PATH, ATTENDANCE)
    save_json(PROGRESS_PATH, PROGRESS)
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="0.0.0.0", port=port, debug=False)