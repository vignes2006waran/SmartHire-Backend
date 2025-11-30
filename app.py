from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)

DB_NAME = "smarthire.db"


# --------------------------
# DB INITIALIZATION & SEEDING
# --------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # Jobs table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT,
            experience INTEGER,
            skills TEXT
        )
        """
    )

    # Applications table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            name TEXT,
            email TEXT,
            phone TEXT,
            experience INTEGER,
            skills TEXT,
            status TEXT DEFAULT 'Applied',
            FOREIGN KEY(job_id) REFERENCES jobs(id)
        )
        """
    )

    conn.commit()
    conn.close()


def seed_jobs():
    """Seed a few demo jobs if table is empty."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM jobs")
    count = c.fetchone()[0]

    if count == 0:
        jobs = [
            ("Python Backend Developer", "Chennai", 1, "Python,Flask,SQL"),
            ("Frontend Developer", "Remote", 0, "HTML,CSS,JavaScript"),
            ("Full Stack Engineer", "Bangalore", 2, "React,Node,SQL"),
        ]
        c.executemany(
            "INSERT INTO jobs (title, location, experience, skills) VALUES (?, ?, ?, ?)",
            jobs,
        )
        conn.commit()

    conn.close()


# --------------------------
# ROUTES
# --------------------------
@app.route("/jobs", methods=["GET"])
def get_jobs():
    """Return full job objects (used by your web UI or Apply flow)."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("SELECT id, title, location, experience, skills FROM jobs")
    rows = c.fetchall()
    conn.close()

    jobs = []
    for r in rows:
        jobs.append(
            {
                "id": r[0],
                "title": r[1],
                "location": r[2],
                "experience": r[3],
                "skills": r[4].split(",") if r[4] else [],
            }
        )
    return jsonify({"jobs": jobs})


@app.route("/jobs/search", methods=["POST"])
def search_jobs():
    """
    Search endpoint for Zoho bot.

    INPUT (from Zoho Webhook body):
        { "skill": "<string from visitor.skill>" }

    OUTPUT (for Zoho String list mapping):
        {
          "jobs": [
             "Python Backend Developer – Chennai (1 yr exp) | Skills: Python, Flask, SQL",
             "Frontend Developer – Remote (0 yr exp) | Skills: HTML, CSS, JavaScript"
          ]
        }
    """
    try:
        data = request.get_json() or {}
        skill = (data.get("skill") or "").strip().lower()

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT title, location, experience, skills FROM jobs")
        rows = c.fetchall()
        conn.close()

        result_strings = []

        for title, location, experience, skills in rows:
            title_lower = (title or "").lower()
            skills_text = skills or ""
            skills_lower = skills_text.lower()

            # If no skill provided, return all jobs
            # If skill provided, match in title or skills list
            if not skill or (skill in title_lower) or (skill in skills_lower):
                display = f"{title} – {location} ({experience} yr exp)"
                if skills_text:
                    display += f" | Skills: {skills_text}"
                result_strings.append(display)

        # IMPORTANT: always return a 200 with "jobs" as a STRING LIST.
        return jsonify({"jobs": result_strings})

    except Exception as e:
        # In case of any unexpected error, don't crash:
        # return empty list so Zoho still follows Success path.
        print("Error in /jobs/search:", e)
        return jsonify({"jobs": []})


@app.route("/apply", methods=["POST"])
def apply_job():
    """Store a job application."""
    data = request.json or {}

    job_id = data.get("job_id")
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    experience = int(data.get("experience") or 0)
    skills = data.get("skills") or ""

    if not job_id or not name or not email:
        return (
            jsonify({"success": False, "message": "Required fields missing"}),
            400,
        )

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO applications (job_id, name, email, phone, experience, skills)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (job_id, name, email, phone, experience, skills),
    )

    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Application submitted successfully!"})


@app.route("/my-applications", methods=["POST"])
def my_applications():
    """Return all applications for a given email (for 'My applications' bot flow)."""
    data = request.json or {}

    email = data.get("email")
    if not email:
        return (
            jsonify({"success": False, "message": "Email is required"}),
            400,
        )

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """
        SELECT a.id, j.title, a.status
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.email = ?
        """,
        (email,),
    )
    rows = c.fetchall()
    conn.close()

    apps = []
    for r in rows:
        apps.append(
            {
                "application_id": r[0],
                "job_title": r[1],
                "status": r[2],
            }
        )

    return jsonify({"success": True, "applications": apps})


@app.route("/health", methods=["GET"])
def health():
    """Simple health check for Render / debugging."""
    return jsonify({"status": "ok"})


# --------------------------
# MAIN
# --------------------------
if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        init_db()
        seed_jobs()
    else:
        init_db()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
