import base64
import json
import os
import re
import socket
import ipaddress
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file

load_dotenv()
BASE = Path(__file__).resolve().parent

# Support both the intended folder structure (templates/static/data)
# and a flat GitHub upload where those files ended up in the repo root.
TEMPLATES_DIR = BASE / "templates" if (BASE / "templates" / "index.html").exists() else BASE
STATIC_DIR = BASE / "static" if (BASE / "static" / "style.css").exists() else BASE
DATA_DIR = BASE / "data" if (BASE / "data" / "profile.json").exists() else BASE

PROFILE_PATH = DATA_DIR / "profile.json"
PHOTO_PATH = DATA_DIR / "profile_photo.jpg"
PHOTO_META_PATH = DATA_DIR / "profile_photo_meta.json"

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
    static_url_path="/static",
)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")


def load_profile():
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))


def save_profile(data):
    PROFILE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer"]):
        tag.decompose()
    text = "\n".join(x.strip() for x in soup.stripped_strings if x.strip())
    return re.sub(r"\n{3,}", "\n\n", text)[:18000]


def fetch_job_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("הקישור חייב להתחיל ב-http:// או https://")
    if not parsed.hostname:
        raise ValueError("קישור לא תקין")
    # Basic SSRF protection for public deployments: block local/private targets.
    try:
        for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError("לא ניתן לקרוא כתובת מקומית/פרטית")
    except socket.gaierror as exc:
        raise ValueError(f"לא ניתן לפתור את כתובת האתר: {exc}")
    headers = {"User-Agent": "Mozilla/5.0 (CV Tailor/1.0)"}
    r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
    r.raise_for_status()
    return clean_page_text(r.text)


def image_to_data_url(file_storage):
    raw = file_storage.read()
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("התמונה גדולה מדי. מקסימום 8MB.")
    mime = file_storage.mimetype or "image/jpeg"
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("יש להעלות JPG, PNG או WEBP.")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def demo_result(profile, job_text, lang):
    text = (job_text or "").lower()
    areas = []
    mapping = [
        (("לוגיסט", "מחסן", "משלוח", "warehouse", "logistics"), "לוגיסטיקה ומחסן"),
        (("מכירות", "sales", "אולם", "showroom", "ליסינג"), "מכירות וניהול לקוחות"),
        (("חנות", "סניף", "retail", "store"), "ניהול קמעונאי"),
        (("עוזר", "assistant", "מנכ", "ceo"), "תפעול ותמיכה ניהולית"),
        (("קפה", "בריסט", "מסעד", "food", "catering"), "אירוח, מזון ואירועים"),
    ]
    for keys, label in mapping:
        if any(k in text for k in keys):
            areas.append(label)
    if not areas:
        areas = ["ניהול, תפעול ומכירות"]
    he = lang != "en"
    headline = " | ".join(areas[:3]) if he else "Management | Operations | Sales"
    exp = []
    for e in profile["experience"][:6]:
        exp.append({
            "company": e["company"],
            "role": e["role_he"] if he else e["role_en"],
            "dates": e["dates"],
            "bullets": e["facts"][:3],
        })
    return {
        "needs_clarification": False,
        "questions": [],
        "job": {"title": "משרה מותאמת" if he else "Target role", "company": "", "requirements": []},
        "match": {"score": 72, "strengths": areas, "gaps": ["מצב הדגמה – חיבור API ייתן ניתוח מלא ומדויק יותר"]},
        "cv": {
            "language": "he" if he else "en",
            "headline": headline,
            "summary": "מנהל עם ניסיון רב-תחומי בניהול אנשים, תפעול, מכירות ולוגיסטיקה, עם יכולת עבודה בסביבה דינמית והובלת משימות מקצה לקצה." if he else "Manager with cross-functional experience in people leadership, operations, sales and logistics, able to drive end-to-end execution in dynamic environments.",
            "skills": profile["skills"][:7],
            "experience": exp,
            "education": profile["education"],
            "languages": profile["languages"],
        },
        "cover_message": "מצורפים קורות החיים שלי, מותאמים למשרה. אשמח לשוחח ולהרחיב על הניסיון הרלוונטי." if he else "Please find my tailored CV attached. I would be glad to discuss the role and my relevant experience."
    }


CV_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["needs_clarification", "questions", "job", "match", "cv", "cover_message"],
    "properties": {
        "needs_clarification": {"type": "boolean"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "job": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "company", "requirements"],
            "properties": {
                "title": {"type": "string"},
                "company": {"type": "string"},
                "requirements": {"type": "array", "items": {"type": "string"}}
            }
        },
        "match": {
            "type": "object",
            "additionalProperties": False,
            "required": ["score", "strengths", "gaps"],
            "properties": {
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "gaps": {"type": "array", "items": {"type": "string"}}
            }
        },
        "cv": {
            "type": "object",
            "additionalProperties": False,
            "required": ["language", "headline", "summary", "skills", "experience", "education", "languages"],
            "properties": {
                "language": {"type": "string", "enum": ["he", "en"]},
                "headline": {"type": "string"},
                "summary": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}, "maxItems": 9},
                "experience": {
                    "type": "array",
                    "maxItems": 7,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["company", "role", "dates", "bullets"],
                        "properties": {
                            "company": {"type": "string"},
                            "role": {"type": "string"},
                            "dates": {"type": "string"},
                            "bullets": {"type": "array", "items": {"type": "string"}, "maxItems": 4}
                        }
                    }
                },
                "education": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                "languages": {"type": "array", "items": {"type": "string"}, "maxItems": 6}
            }
        },
        "cover_message": {"type": "string"}
    }
}


def generate_with_openai(profile, job_text, screenshot_data_url, lang, extra_notes):
    from openai import OpenAI
    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")

    instructions = """
You are a rigorous CV tailoring engine. Your goal is to create a one-page, ATS-friendly CV tailored to the supplied job while remaining completely truthful.

NON-NEGOTIABLE RULES:
1. Use only facts in CANDIDATE_PROFILE plus facts explicitly supplied in EXTRA_USER_FACTS. Never invent employers, dates, education, certifications, software, achievements, team size, revenue, KPIs or responsibilities.
2. You may rephrase and prioritize existing facts to match the role, but may not inflate them.
3. If a major job requirement is not supported, set needs_clarification=true and ask concise questions that could resolve the gap. Do not write the missing skill into the CV unless the user supplied it.
4. Missing or uncertain dates must stay described as unknown/approximate; never guess.
5. Prioritize the 4–7 most relevant experiences. Keep bullets concise and achievement-oriented without fake numbers.
6. The CV should fit approximately one A4 page. Summary: 3–5 lines. Skills: 6–9. Experience: max 4 bullets per role.
7. If language=auto, use the primary language of the job ad. If language=he, output Hebrew. If language=en, output English.
8. Photo is handled by the app and is locked. Do not make suggestions to alter or retouch it.
9. The match score is descriptive only: how much of the job appears supported by the profile. Do not hide gaps.
10. cover_message should be a short natural WhatsApp/email message for sending the CV.
"""
    prompt = f"""
TARGET_LANGUAGE: {lang}

CANDIDATE_PROFILE:
{json.dumps(profile, ensure_ascii=False, indent=2)}

JOB_TEXT_OR_URL_CONTENT:
{job_text[:18000]}

EXTRA_USER_FACTS / ANSWERS:
{extra_notes or 'None'}

Analyze the job, identify its real requirements, assess supported fit, ask for missing facts when necessary, and produce the tailored CV.
"""
    content = [{"type": "input_text", "text": prompt}]
    if screenshot_data_url:
        content.append({"type": "input_image", "image_url": screenshot_data_url, "detail": "high"})
        content.append({"type": "input_text", "text": "The attached screenshot is part of the job advertisement. Read it carefully and include its requirements in the analysis."})

    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
        text={
            "format": {
                "type": "json_schema",
                "name": "tailored_cv",
                "strict": True,
                "schema": CV_SCHEMA
            }
        }
    )
    return json.loads(response.output_text)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/profile-photo")
def profile_photo():
    mime = "image/jpeg"
    if PHOTO_META_PATH.exists():
        try:
            mime = json.loads(PHOTO_META_PATH.read_text(encoding="utf-8")).get("mime", mime)
        except Exception:
            pass
    return send_file(PHOTO_PATH, mimetype=mime, max_age=0)


@app.get("/api/profile")
def get_profile():
    return jsonify(load_profile())


@app.post("/api/profile")
def update_profile():
    data = request.get_json(force=True)
    save_profile(data)
    return jsonify({"ok": True})


@app.post("/api/profile-photo")
def update_photo():
    photo = request.files.get("photo")
    if not photo:
        return jsonify({"error": "לא התקבלה תמונה"}), 400
    if photo.mimetype not in {"image/jpeg", "image/png", "image/webp"}:
        return jsonify({"error": "פורמט תמונה לא נתמך"}), 400
    raw = photo.read()
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"error": "התמונה גדולה מדי"}), 400
    PHOTO_PATH.write_bytes(raw)
    PHOTO_META_PATH.write_text(json.dumps({"mime": photo.mimetype}), encoding="utf-8")
    return jsonify({"ok": True, "url": "/profile-photo?v=2"})


@app.post("/api/generate")
def generate():
    try:
        profile = load_profile()
        job_text = (request.form.get("job_text") or "").strip()
        job_url = (request.form.get("job_url") or "").strip()
        lang = request.form.get("language", "auto")
        extra_notes = (request.form.get("extra_notes") or "").strip()
        screenshot = request.files.get("screenshot")
        screenshot_data_url = image_to_data_url(screenshot) if screenshot and screenshot.filename else None

        url_text = ""
        if job_url:
            try:
                url_text = fetch_job_url(job_url)
            except Exception as exc:
                url_text = f"[Could not fetch job URL automatically: {exc}]\nURL: {job_url}"
        combined = "\n\n".join(x for x in [job_text, url_text] if x).strip()
        if not combined and not screenshot_data_url:
            return jsonify({"error": "יש להעלות צילום מסך, להדביק קישור או לתאר את המשרה."}), 400

        if not os.getenv("OPENAI_API_KEY"):
            result = demo_result(profile, combined, lang)
            result["demo_mode"] = True
            return jsonify(result)

        result = generate_with_openai(profile, combined, screenshot_data_url, lang, extra_notes)
        result["demo_mode"] = False
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.get("/health")
def health():
    return jsonify({"ok": True, "api": bool(os.getenv("OPENAI_API_KEY"))})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
