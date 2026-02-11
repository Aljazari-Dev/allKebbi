# templates.py
from app.config import now_iso

# ------------------ UI: Purple Theme Templates ------------------
BASE_STYLES = """
<style>
:root{
  --brand:#6b21a8;
  --ink:#0b0b0d;
  --bg:#faf7ff;
  --card:#ffffff;
  --muted:#6b7280;
  --border:#edd6ff;
  --radius:14px;
}
*{box-sizing:border-box}
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial; background:var(--bg); color:var(--ink); margin:0}
.header{background:linear-gradient(90deg,var(--brand),#8b5cf6); color:white;padding:28px 16px;text-align:center}
.header h1{margin:0;font-size:28px;letter-spacing:1px}
.topnav{display:flex;gap:8px;justify-content:center;padding:12px;background:transparent;border-bottom:1px solid rgba(0,0,0,0.04)}
.topnav a{color:#f8f5ff;text-decoration:none;padding:8px 14px;border-radius:8px}
.topnav a.active{background:rgba(255,255,255,0.12)}
.container{max-width:1200px;margin:20px auto;padding:0 16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;margin-bottom:16px;box-shadow:0 8px 28px rgba(107,33,168,0.06)}
.btn{background:var(--brand);color:white;padding:10px 14px;border-radius:12px;text-decoration:none;border:0;cursor:pointer}
.btn.ghost{background:white;color:var(--brand);border:1px solid var(--border)}
.small{color:var(--muted);font-size:13px}
.table{width:100%;border-collapse:collapse;margin-top:10px}
.table th,.table td{padding:8px;border:1px solid var(--border);text-align:left}
.input, select, textarea{width:100%;padding:10px;border-radius:10px;border:1px solid var(--border)}
.row{display:flex;gap:10px;align-items:center}
.grid{display:grid;gap:16px}
.grid.cols-3{grid-template-columns:repeat(3,1fr)}
.grid.cols-2{grid-template-columns:repeat(2,1fr)}
.empty{padding:30px;text-align:center;color:var(--muted);border:1px dashed var(--border);border-radius:10px}
.footer{color:var(--muted);font-size:12px;text-align:center;margin-top:20px}
.big-tile{
  display:flex;flex-direction:column;justify-content:center;align-items:center;
  padding:24px;border-radius:12px;background:linear-gradient(180deg,rgba(107,33,168,0.06),rgba(139,92,246,0.03));
  border:1px solid var(--border);height:120px;text-align:center;cursor:pointer;
}
.big-tile h3{margin:0 0 6px}
.big-tile p{margin:0;color:var(--muted)}
.tile-link{text-decoration:none;color:inherit}
.section-card{display:block;text-decoration:none;color:inherit}
.subject-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.subject-tile{padding:18px;border-radius:12px;background:linear-gradient(180deg,rgba(107,33,168,0.03),rgba(139,92,246,0.02));border:1px solid var(--border);text-align:center;cursor:pointer}
.mono{font-family:monospace}
</style>
"""


def layout(page_title, active="home", body_html=""):
    nav = {
        "home": "Home",
        "stages": "Stages",
        "analytics": "Analytics",
        "settings": "Settings",
    }
    nav_html = "".join(
        [
            f'<a class="{{ "active" if key==active else "" }}" href="{{{{ url_for("{key}_page") }}}}">{label}</a>'
            for key, label in nav.items()
        ]
    )
    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{page_title}</title>
{BASE_STYLES}
</head>
<body>
  <div class="header">
    <h1>Kebbi Dashboard</h1>
    <div class="topnav">{nav_html}</div>
  </div>
  <div class="container">
    {body_html}
    <div class="footer">Kebbi Dashboard • Local • {now_iso()}</div>
  </div>
</body>
</html>
"""


# ------------------ TEMPLATES ------------------
HOME_HTML = """
<div class="card">
  <div class="row" style="justify-content:space-between">
    <div>
      <h2>Robots</h2>
      <div class="small">Manage physical Kebbi robots connected to this dashboard.</div>
    </div>
    <div>
      <button class="btn" onclick="document.getElementById('addRobot').style.display='block'">+ Add Robot</button>
    </div>
  </div>

  <div style="margin-top:12px">
    {% if robots %}
      <table class="table">
        <thead><tr><th>Serial</th><th>Name</th><th>Stage</th><th>Section</th><th>Active</th><th>Connected</th><th>Actions</th></tr></thead>
        <tbody>
          {% for serial, r in robots.items() %}
            <tr>
              <td><code>{{ serial }}</code></td>
              <td>{{ r.get('name','') }}</td>
              <td>{{ r.get('linked_stage','-') }}</td>
              <td>{{ r.get('linked_section','-') }}</td>
              <td>{{ 'Yes' if r.get('active') else 'No' }}</td>
              <td>{{ 'Yes' if r.get('connected') else 'No' }}</td>
              <td class="row">
                <form method="post" action="{{ url_for('robot_toggle') }}" style="display:inline">
                  <input type="hidden" name="serial" value="{{ serial }}">
                  <button class="btn ghost" type="submit">{{ 'Deactivate' if r.get('active') else 'Activate' }}</button>
                </form>
                <form method="post" action="{{ url_for('robot_delete') }}" style="display:inline" onsubmit="return confirm('Delete robot?')">
                  <input type="hidden" name="serial" value="{{ serial }}">
                  <button class="btn ghost" type="submit">Delete</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">No robots added yet. Add one to get started.</div>
    {% endif %}
  </div>
</div>

<div id="addRobot" class="card" style="display:none;margin-top:12px">
  <h3>Add Robot</h3>
  <form method="post" action="{{ url_for('robot_add') }}">
    <label>Serial Number</label>
    <input class="input" name="serial" placeholder="e.g. KEBBI-R-0001" required>
    <label>Name (optional)</label>
    <input class="input" name="name" placeholder="Classroom robot">
    <label>Link to Stage</label>
    <select class="input" name="linked_stage">
      <option value="">-- none --</option>
      {% for s in stages %}
        <option value="{{ s }}">{{ s }}</option>
      {% endfor %}
    </select>
    <label>Link to Section</label>
    <input class="input" name="linked_section" placeholder="A or B">
    <div class="row section" style="margin-top:10px">
      <button class="btn" type="submit">Add Robot</button>
      <button class="btn ghost" type="button" onclick="document.getElementById('addRobot').style.display='none'">Cancel</button>
    </div>
  </form>
</div>
"""

STAGES_HTML = """
<div style="display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
  {% for sname, sdata in stages.items() %}
    <a class="tile-link" href="{{ url_for('stage_page', stage=sname) }}">
      <div class="card big-tile">
        <h3>{{ sname }}</h3>
        <p>{{ sdata.sections|length }} sections • Click to open</p>
      </div>
    </a>
  {% endfor %}
</div>
"""

STAGE_PAGE_HTML = """
<div class="card" style="margin-bottom:14px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }}</h2>
      <div class="small">Click a section card to open its dashboard (Students & Subjects)</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('stages_page') }}">Back</a></div>
  </div>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px">
  {% for sec, secdata in sections.items() %}
    <a class="section-card" href="{{ url_for('section_dashboard', stage=stage, section=sec) }}">
      <div class="card big-tile">
        <h3>Section {{ sec }}</h3>
        <p>Students: {{ secdata.students|length }} • Subjects: {{ secdata.subjects|length }}</p>
      </div>
    </a>
  {% endfor %}
</div>
"""

SECTION_DASH_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }} — Section {{ section }}</h2>
      <div class="small">Choose: Students or Subjects</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('stage_page', stage=stage) }}">Back</a></div>
  </div>

  <div style="margin-top:12px" class="grid cols-2">
    <a class="tile-link" href="{{ url_for('section_students_page', stage=stage, section=section) }}">
      <div class="big-tile">
        <h3>Students</h3>
        <p>View & Add ({{ students|length }})</p>
      </div>
    </a>

    <a class="tile-link" href="{{ url_for('section_subjects_page', stage=stage, section=section) }}">
      <div class="big-tile">
        <h3>Subjects</h3>
        <p>{{ subjects|length }} subjects</p>
      </div>
    </a>
  </div>
</div>
"""

STUDENTS_PAGE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }} — Section {{ section }} — Students</h2>
      <div class="small">Total students: <b>{{ students|length }}</b></div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('section_dashboard', stage=stage, section=section) }}">Back</a></div>
  </div>

  <div style="margin-top:12px">
    <form method="post" action="{{ url_for('add_student', stage=stage, section=section) }}" style="display:flex;gap:8px">
      <input class="input" name="name" placeholder="Student name" required>
      <button class="btn" type="submit">Add</button>
    </form>
  </div>

  <div style="margin-top:12px">
    {% if students %}
      <table class="table">
        <thead><tr><th>#</th><th>Name</th><th>Actions</th></tr></thead>
        <tbody>
          {% for s in students %}
            <tr>
              <td>{{ loop.index }}</td>
              <td>{{ s }}</td>
              <td>
                <form method="post" action="{{ url_for('remove_student', stage=stage, section=section) }}" style="display:inline">
                  <input type="hidden" name="name" value="{{ s }}">
                  <button class="btn ghost" type="submit">Remove</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">No students yet</div>
    {% endif %}
  </div>
</div>
"""

SUBJECTS_PAGE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }} — Section {{ section }} — Subjects</h2>
      <div class="small">Choose a subject (8 subjects)</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('section_dashboard', stage=stage, section=section) }}">Back</a></div>
  </div>

  <div style="margin-top:12px" class="subject-grid">
    {% for subj in subjects %}
      <a class="tile-link" href="{{ url_for('subject_page', stage=stage, section=section, subject=subj) }}">
        <div class="subject-tile">
          <h3>{{ subj }}</h3>
          <p class="small">Open subject options</p>
        </div>
      </a>
    {% endfor %}
  </div>
</div>
"""

SUBJECT_PAGE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }} / {{ section }} — {{ subject }}</h2>
      <div class="small">Choose action</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('section_subjects_page', stage=stage, section=section) }}">Back</a></div>
  </div>

  <div style="margin-top:12px" class="grid cols-2">
    <a class="tile-link" href="{{ url_for('attendance_subject_page', stage=stage, section=section, subject=subject) }}">
      <div class="big-tile">
        <h3>Attendance</h3>
        <p>Record today's attendance</p>
      </div>
    </a>
    <a class="tile-link" href="{{ url_for('quizzes_subject_page', stage=stage, section=section, subject=subject) }}">
      <div class="big-tile">
        <h3>Quizzes</h3>
        <p>View or create quizzes</p>
      </div>
    </a>
    <a class="tile-link" href="{{ url_for('subject_rag_page', stage=stage, section=section, subject=subject) }}">
      <div class="big-tile">
        <h3>Book Assistant</h3>
        <p>Upload Word book & ask questions</p>
      </div>
    </a>
  </div>
</div>
"""

ATTENDANCE_SUBJECT_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>Attendance — {{ stage }} / {{ section }} — {{ subject }}</h2>
      <div class="small">Record today's attendance</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('subject_page', stage=stage, section=section, subject=subject) }}">Back</a></div>
  </div>

  <form method="post" action="{{ url_for('attendance_mark', stage=stage, section=section) }}" style="margin-top:12px">
    <input type="hidden" name="subject" value="{{ subject }}">
    <table class="table">
      <thead><tr><th>#</th><th>Name</th><th>Present</th></tr></thead>
      <tbody>
        {% for s in students %}
          <tr>
            <td>{{ loop.index }}</td>
            <td>{{ s }}</td>
            <td><input type="checkbox" name="present_{{ loop.index0 }}" {% if attendance.get(s) %}checked{% endif %}></td>
            <input type="hidden" name="name_{{ loop.index0 }}" value="{{ s }}">
          </tr>
        {% endfor %}
      </tbody>
    </table>
    <div style="margin-top:12px">
      <button class="btn" type="submit">Save Attendance</button>
      <a class="btn ghost" href="{{ url_for('attendance_view_subject', stage=stage, section=section, subject=subject) }}">View History</a>
    </div>
  </form>
</div>
"""

QUIZZES_SUBJECT_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>Quizzes — {{ stage }} / {{ section }} — {{ subject }}</h2>
      <div class="small">Create or view quizzes for this subject</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('subject_page', stage=stage, section=section, subject=subject) }}">Back</a></div>
  </div>

  <div style="margin-top:12px" class="row" >
    <a class="btn" href="{{ url_for('quiz_create_for_subject', stage=stage, section=section, subject=subject) }}">Create Quiz</a>
    <a class="btn ghost" href="{{ url_for('quiz_generate_for_subject', stage=stage, section=section, subject=subject) }}">Generate (Auto)</a>
    <a class="btn ghost" href="{{ url_for('quiz_generate_ai_for_subject', stage=stage, section=section, subject=subject) }}">Generate (AI)</a>
  </div>

  <div style="margin-top:12px">
    {% if quizzes %}
      <table class="table">
        <thead><tr><th>#</th><th>ID</th><th>Title</th><th>#Q</th><th>Actions</th></tr></thead>
        <tbody>
          {% for q in quizzes %}
            <tr>
              <td>{{ loop.index }}</td>
              <td><code>{{ q.quiz_id }}</code></td>
              <td>{{ q.title }}</td>
              <td>{{ q.count }}</td>
              <td class="row">
                <a class="btn ghost" href="{{ url_for('quiz_preview', quiz_id=q.quiz_id) }}">Preview</a>
                <a class="btn ghost" href="{{ url_for('quiz_stats_page', quiz_id=q.quiz_id) }}">Stats</a>
                <a class="btn ghost" href="{{ url_for('quiz_scores_page', quiz_id=q.quiz_id) }}">Scores</a>

                <form method="post" action="{{ url_for('quiz_delete', quiz_id=q.quiz_id) }}" style="display:inline" onsubmit="return confirm('Delete quiz?')">
                  <button class="btn ghost" type="submit">Delete</button>
                </form>
              </td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">No quizzes for this subject yet.</div>
    {% endif %}
  </div>
</div>
"""

QUIZ_CREATE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Create Quiz — {{ stage }}/{{ section }} {% if subject %} / {{ subject }} {% endif %}</h2>
    <a class="btn ghost" href="{{ url_for('section_dashboard', stage=stage, section=section) }}">Back</a>
  </div>

  <form method="post" action="{{ url_for('quiz_create_for_subject', stage=stage, section=section, subject=subject) }}">
    <input type="hidden" name="subject" value="{{ subject }}">
    <label>Title</label>
    <input class="input" name="title" required>
    <label>Questions (one per line, use :: to separate question and answer)</label>
    <textarea class="input" name="bulk" rows="8" placeholder="2+3? :: 5"></textarea>
    <div style="margin-top:8px">
      <button class="btn" type="submit">Create & Activate</button>
    </div>
  </form>
</div>
"""

QUIZ_GENERATE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Generate Auto Quiz — {{ stage }}/{{ section }} {% if subject %} / {{ subject }} {% endif %}</h2>
    <a class="btn ghost" href="{{ url_for('section_dashboard', stage=stage, section=section) }}">Back</a>
  </div>

  <form method="post" action="{{ url_for('quiz_generate_for_subject', stage=stage, section=section, subject=subject) }}">
    <input type="hidden" name="subject" value="{{ subject }}">
    <label>Title</label>
    <input class="input" name="title" value="Auto {{ subject }} Quiz" required>
    <label>Count</label>
    <input class="input" name="count" value="10">
    <label>Shuffle</label>
    <select class="input" name="shuffle">
      <option value="1">Yes</option><option value="0">No</option>
    </select>
    <div style="margin-top:8px"><button class="btn" type="submit">Generate</button></div>
  </form>
  <div class="small" style="margin-top:8px">This generator creates subject-specific questions (e.g., multiplication for Mathematics, parsing for Arabic, capitals for Geography, etc.).</div>
</div>
"""

QUIZ_AI_GENERATE_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Generate Quiz with AI — {{ stage }}/{{ section }} {% if subject %} / {{ subject }} {% endif %}</h2>
    <a class="btn ghost" href="{{ url_for('section_dashboard', stage=stage, section=section) }}">Back</a>
  </div>

  <form method="post" action="{{ url_for('quiz_generate_ai_for_subject', stage=stage, section=section, subject=subject) }}">
    <input type="hidden" name="subject" value="{{ subject }}">
    <label>Lesson / Topic Description (what teacher types — the AI will generate questions from this)</label>
    <textarea class="input" name="lesson" rows="6" placeholder="Describe the lesson: key points, vocabulary, focus (e.g., past simple tense, irregular verbs)"></textarea>
    <label>Title (optional)</label>
    <input class="input" name="title" value="AI-generated {{ subject }} Quiz">
    <label>Count</label>
    <input class="input" name="count" value="8">
    <label>Difficulty (easy/medium/hard)</label>
    <select class="input" name="difficulty">
      <option value="easy">Easy</option>
      <option value="medium" selected>Medium</option>
      <option value="hard">Hard</option>
    </select>
    <label>Question type</label>
    <select class="input" name="qtype">
      <option value="short">Short answer</option>
      <option value="mcq">Multiple choice (AI will provide choices)</option>
    </select>
    <div style="margin-top:8px"><button class="btn" type="submit">Generate with AI</button></div>
  </form>

  <div class="small" style="margin-top:8px">Note: AI uses your OpenAI API key from Settings. The response must be in the format: one question per line either "Question :: Answer" or "Question :: Answer :: choice1 | choice2 | choice3 | choice4" for MCQ. The server will parse and store Q/A.</div>
</div>
"""

QUIZ_PREVIEW_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Quiz Preview — {{ quiz.title }}</h2>
    <a class="btn ghost" href="{{ url_for('quizzes_list_page') }}">Back</a>
  </div>
  <div class="small">ID: <code>{{ quiz_id }}</code> • Meta: {{ meta }}</div>
  <div style="margin-top:12px">
    <table class="table">
      <thead><tr><th>#</th><th>Question</th><th>Answer / Choices</th></tr></thead>
      <tbody>
        {% for q in quiz.questions %}
          <tr><td>{{ loop.index }}</td><td>{{ q.q }}</td><td><code>{{ q.a }}</code>{% if q.get('choices') %}<div class="small">Choices: {{ q.choices }}</div>{% endif %}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
"""

QUIZ_STATS_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Quiz Stats — {{ quiz.title }}</h2>
    <a class="btn ghost" href="{{ url_for('quizzes_list_page') }}">Back</a>
  </div>
  <div style="margin-top:12px">
    <div class="small">Total Attempts: {{ totals.total_attempts }} • Correct: {{ totals.total_correct }} • Wrong: {{ totals.total_wrong }} • Accuracy: {{ totals.acc }}%</div>
    <div style="margin-top:12px">
      <table class="table">
        <thead><tr><th>#</th><th>Question</th><th>Attempts</th><th>Correct</th><th>Wrong</th><th>Common wrongs</th></tr></thead>
        <tbody>
          {% for r in rows %}
            <tr>
              <td>{{ loop.index }}</td>
              <td>{{ r.q }}</td>
              <td>{{ r.attempts }}</td>
              <td>{{ r.correct }}</td>
              <td>{{ r.wrong }}</td>
              <td><code>{{ r.common }}</code></td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>
</div>
"""

QUIZ_SCORES_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between">
    <h2>Quiz Scores — {{ quiz.title }}</h2>
    <a class="btn ghost" href="{{ url_for('quizzes_list_page') }}">Back</a>
  </div>
  <div class="small">ID: <code>{{ quiz_id }}</code> • Stage/Section/Subject: {{ meta.stage }} / {{ meta.section }} / {{ meta.subject }}</div>

  <div style="margin-top:12px">
    {% if rows %}
      <table class="table">
        <thead><tr><th>#</th><th>Student</th><th>Score</th><th>Total</th><th>Finished at</th></tr></thead>
        <tbody>
          {% for r in rows %}
            <tr>
              <td>{{ loop.index }}</td>
              <td>{{ r.student }}</td>
              <td>{{ r.score if r.score is not none else '-' }}</td>
              <td>{{ r.total if r.total is not none else '-' }}</td>
              <td class="small mono">{{ r.finished_at or '-' }}</td>
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">No students in this section/subject.</div>
    {% endif %}
  </div>
</div>
"""

ATTENDANCE_VIEW_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>Attendance History — {{ stage }} / {{ section }}</h2>
      <div class="small">Daily records</div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('section_subjects_page', stage=stage, section=section) }}">Back</a></div>
  </div>

  <div style="margin-top:12px">
    {% if history %}
      <table class="table">
        <thead><tr><th>Date</th>{% for s in students %}<th>{{ s }}</th>{% endfor %}</tr></thead>
        <tbody>
          {% for date, row in history.items() %}
            <tr>
              <td><code>{{ date }}</code></td>
              {% for s in students %}
                <td>{{ '✓' if row.get(s) else '' }}</td>
              {% endfor %}
            </tr>
          {% endfor %}
        </tbody>
      </table>
    {% else %}
      <div class="empty">No attendance records.</div>
    {% endif %}
  </div>
</div>
"""

ANALYTICS_HTML = """
<div class="card">
  <h2>Analytics</h2>
  <div class="small">Overview metrics across stages/sections</div>

  <div style="margin-top:12px" class="grid cols-3">
    <div class="card">
      <div class="small">Total Students</div>
      <div style="font-size:26px">{{ totals.total_students }}</div>
    </div>
    <div class="card">
      <div class="small">Today's Attendance %</div>
      <div style="font-size:26px">{{ totals.attendance_pct }}%</div>
    </div>
    <div class="card">
      <div class="small">Total Quizzes Taken</div>
      <div style="font-size:26px">{{ totals.total_quiz_attempts }}</div>
    </div>
  </div>

  <div class="card" style="margin-top:12px">
    <h3>Students per Stage</h3>
    <ul>
      {% for sname, cnt in totals.per_stage.items() %}
        <li>{{ sname }}: {{ cnt }}</li>
      {% endfor %}
    </ul>
  </div>
</div>
"""

SETTINGS_HTML = """
<div class="card">
  <h2>Settings — GPT / Kebbi</h2>
  <form method="post" action="{{ url_for('settings_page') }}">
    <label>OpenAI API Key</label>
    <input class="input" name="api_key" value="{{ api_key }}" placeholder="sk-...">
    <label>Model</label>
    <input class="input" name="model" value="{{ model }}">
    <label>Temperature</label>
    <input class="input" name="temperature" value="{{ temperature }}">
    <label>Max Tokens</label>
    <input class="input" name="max_tokens" value="{{ max_tokens }}">
    <label>System Prompt (used as base for AI generation)</label>
    <textarea class="input" name="system_prompt" rows="6">{{ system_prompt }}</textarea>
    <label>Always Correct? (0/1)</label>
    <input class="input" name="always_correct" value="{{ '1' if always_correct else '0' }}">
    <div style="margin-top:8px">
      <button class="btn" type="submit">Save Settings</button>
    </div>
  </form>

  <div style="margin-top:12px" class="small">
    To enable AI generation fill your OpenAI API key above. The AI generator expects the model to return Q&A lines in the format <code>Question :: Answer</code>. For MCQ, AI may append choices like <code>Question :: Answer :: A | B | C | D</code>.
  </div>
</div>
"""

SUBJECT_RAG_HTML = """
<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <div>
      <h2>{{ stage }} / {{ section }} — {{ subject }} — Book Assistant</h2>
      <div class="small">
        ارفع ملف Word خاص بهذه المادة (كتاب واحد فقط)، ثم اسأل أسئلة وسيجيب من نفس الكتاب فقط.
      </div>
    </div>
    <div><a class="btn ghost" href="{{ url_for('subject_page', stage=stage, section=section, subject=subject) }}">Back</a></div>
  </div>

  <div style="margin-top:12px">
    <div class="small">
      {% if has_book %}
        ✅ تم رفع كتاب لهذه المادة. يمكنك استبداله برفع ملف جديد، أو طرح سؤال الآن.
      {% else %}
        ⚠️ لم يتم رفع كتاب بعد لهذه المادة. ارفع ملف Word (.docx) أولاً.
      {% endif %}
    </div>
  </div>

  <div style="margin-top:12px;display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px">
    <div class="card">
      <h3>رفع / استبدال ملف Word</h3>
      <form method="post" enctype="multipart/form-data">
        <label class="small">ملف Word للمادة (docx فقط)</label>
        <input class="input" type="file" name="file" accept=".docx">
        <div style="margin-top:8px">
          <button class="btn" type="submit">Upload / Replace</button>
        </div>
      </form>
    </div>

    <div class="card">
      <h3>اسأل من الكتاب</h3>
      <form method="post">
        <label class="small">سؤالك:</label>
        <textarea class="input" name="question" rows="4" placeholder="اكتب سؤال الطالب هنا...">{{ question or "" }}</textarea>
        <div style="margin-top:8px">
          <button class="btn" type="submit" {% if not has_book %}disabled{% endif %}>Answer from Book</button>
        </div>
      </form>
    </div>
  </div>

  {% if message %}
    <div class="card" style="margin-top:12px">
      <div class="small">{{ message }}</div>
    </div>
  {% endif %}

  {% if answer %}
    <div class="card" style="margin-top:12px">
      <h3>جواب المعلم (معتمد على نص الكتاب):</h3>
      <div>{{ answer }}</div>
    </div>
  {% endif %}

  {% if contexts %}
    <div class="card" style="margin-top:12px">
      <h3 class="small">أقرب الفقرات من الكتاب (للمراجعة فقط):</h3>
      <div class="small">
        {% for c in contexts %}
          <p><b>فقرة #{{ c.index }}</b> (score={{ "%.3f"|format(c.score) }}):<br>{{ c.text }}</p>
          <hr>
        {% endfor %}
      </div>
    </div>
  {% endif %}
</div>
"""
