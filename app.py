import base64
import io
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
from flask import Flask, jsonify, render_template, request
from pypdf import PdfReader
from docx import Document

load_dotenv()
BASE = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE / "templates"), static_folder=str(BASE / "static"))
app.config["MAX_CONTENT_LENGTH"] = 14 * 1024 * 1024
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")


def clean_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "header", "footer"]):
        tag.decompose()
    text = "\n".join(x.strip() for x in soup.stripped_strings if x.strip())
    return re.sub(r"\n{3,}", "\n\n", text)[:20000]


def fetch_public_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("קישור לא תקין")
    try:
        for info in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise ValueError("לא ניתן לקרוא כתובת מקומית/פרטית")
    except socket.gaierror as exc:
        raise ValueError(f"לא ניתן לפתור את כתובת האתר: {exc}")
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (CV Match/2.0)"}, timeout=15, allow_redirects=True)
    r.raise_for_status()
    return clean_page_text(r.text)


def data_url_from_bytes(raw: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def extract_uploaded_cv(file_storage):
    if not file_storage or not file_storage.filename:
        return {"text": "", "attachment": None, "filename": ""}
    raw = file_storage.read()
    if len(raw) > 12 * 1024 * 1024:
        raise ValueError("קובץ קורות החיים גדול מדי. מקסימום 12MB.")
    name = file_storage.filename or "resume"
    ext = Path(name).suffix.lower()
    mime = file_storage.mimetype or "application/octet-stream"
    text = ""
    attachment = None

    if ext == ".pdf" or mime == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n".join((page.extract_text() or "") for page in reader.pages)[:30000]
        except Exception:
            text = ""
        # Attach the original PDF as well; this helps with image/scanned PDFs.
        attachment = {
            "type": "input_file",
            "filename": name,
            "file_data": base64.b64encode(raw).decode("ascii"),
        }
    elif ext == ".docx" or "wordprocessingml" in mime:
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())[:30000]
    elif ext in {".txt", ".md"} or mime.startswith("text/"):
        text = raw.decode("utf-8", errors="replace")[:30000]
    elif ext in {".jpg", ".jpeg", ".png", ".webp"} or mime.startswith("image/"):
        if mime not in {"image/jpeg", "image/png", "image/webp"}:
            mime = "image/jpeg"
        attachment = {"type": "input_image", "image_url": data_url_from_bytes(raw, mime), "detail": "high"}
    else:
        raise ValueError("פורמט קובץ לא נתמך. העלה PDF, DOCX, TXT, JPG, PNG או WEBP.")
    return {"text": text, "attachment": attachment, "filename": name}


def normalize_month(v):
    if not v:
        return ""
    v = str(v).strip()
    m = re.match(r"^(\d{4})(?:[-/.](\d{1,2}))?", v)
    if not m:
        return ""
    year = int(m.group(1))
    month = min(12, max(1, int(m.group(2) or 1)))
    return f"{year:04d}-{month:02d}"


def sort_profile(profile):
    def exp_key(e):
        current = bool(e.get("is_current"))
        end = normalize_month(e.get("end_date")) or ("9999-12" if current else "0000-01")
        start = normalize_month(e.get("start_date")) or "0000-01"
        return (1 if current else 0, end, start)
    profile["experience"] = sorted(profile.get("experience", []), key=exp_key, reverse=True)
    return profile


PROFILE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["personal", "summary_facts", "experience", "education", "languages", "skills", "certifications", "questions"],
    "properties": {
        "personal": {
            "type": "object", "additionalProperties": False,
            "required": ["name_he", "name_en", "phone", "email", "linkedin", "website", "location_he", "location_en"],
            "properties": {k: {"type": "string"} for k in ["name_he", "name_en", "phone", "email", "linkedin", "website", "location_he", "location_en"]}
        },
        "summary_facts": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "experience": {
            "type": "array", "maxItems": 30,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["company", "role_he", "role_en", "category", "start_date", "end_date", "is_current", "date_text_original", "location", "facts"],
                "properties": {
                    "company": {"type": "string"}, "role_he": {"type": "string"}, "role_en": {"type": "string"},
                    "category": {"type": "string", "enum": ["work", "military", "project", "volunteer", "other"]},
                    "start_date": {"type": "string"}, "end_date": {"type": "string"}, "is_current": {"type": "boolean"},
                    "date_text_original": {"type": "string"}, "location": {"type": "string"},
                    "facts": {"type": "array", "items": {"type": "string"}, "maxItems": 10}
                }
            }
        },
        "education": {
            "type": "array", "maxItems": 12,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["institution", "program", "start_date", "end_date", "details"],
                "properties": {"institution": {"type": "string"}, "program": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}, "details": {"type": "string"}}
            }
        },
        "languages": {
            "type": "array", "maxItems": 12,
            "items": {"type": "object", "additionalProperties": False, "required": ["name", "level"], "properties": {"name": {"type": "string"}, "level": {"type": "string"}}}
        },
        "skills": {"type": "array", "items": {"type": "string"}, "maxItems": 40},
        "certifications": {"type": "array", "items": {"type": "string"}, "maxItems": 20},
        "questions": {"type": "array", "items": {"type": "string"}, "maxItems": 12}
    }
}


CV_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["needs_clarification", "questions", "job", "match", "cv", "cover_message"],
    "properties": {
        "needs_clarification": {"type": "boolean"},
        "questions": {"type": "array", "items": {"type": "string"}},
        "job": {"type": "object", "additionalProperties": False, "required": ["title", "company", "requirements"], "properties": {"title": {"type": "string"}, "company": {"type": "string"}, "requirements": {"type": "array", "items": {"type": "string"}}}},
        "match": {"type": "object", "additionalProperties": False, "required": ["score", "strengths", "gaps"], "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}, "strengths": {"type": "array", "items": {"type": "string"}}, "gaps": {"type": "array", "items": {"type": "string"}}}},
        "cv": {
            "type": "object", "additionalProperties": False,
            "required": ["language", "headline", "summary", "skills", "experience", "education", "languages"],
            "properties": {
                "language": {"type": "string", "enum": ["he", "en"]}, "headline": {"type": "string"}, "summary": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
                "experience": {"type": "array", "maxItems": 8, "items": {"type": "object", "additionalProperties": False, "required": ["company", "role", "dates", "bullets"], "properties": {"company": {"type": "string"}, "role": {"type": "string"}, "dates": {"type": "string"}, "bullets": {"type": "array", "items": {"type": "string"}, "maxItems": 4}}}},
                "education": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                "languages": {"type": "array", "items": {"type": "string"}, "maxItems": 8}
            }
        },
        "cover_message": {"type": "string"}
    }
}


def openai_client():
    if not os.getenv("OPENAI_API_KEY"):
        return None
    from openai import OpenAI
    return OpenAI()


def extract_profile_with_ai(current_profile, free_text, url_texts, cv_data):
    client = openai_client()
    if not client:
        raise RuntimeError("כדי לייבא ולסדר קורות חיים אוטומטית צריך להוסיף OPENAI_API_KEY ב-Vercel.")
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
    instructions = """
You are a rigorous resume-profile extraction engine. Convert the supplied materials into a factual structured candidate profile.
RULES:
- Never invent employers, dates, titles, skills, education, languages, achievements, or numbers.
- Preserve uncertainty. If a date is only a year, use YYYY-01 as start/end only when the year itself is explicit and keep the original wording in date_text_original. If a date is unknown, leave start_date/end_date empty.
- start_date and end_date use YYYY-MM when supported. is_current=true only if the source clearly says present/current/today.
- Separate work, military service, one-off projects and volunteering using category.
- Deduplicate overlapping facts from multiple sources.
- Merge with CURRENT_PROFILE rather than deleting verified existing facts unless the new source explicitly corrects them.
- Questions should ask only about important ambiguities or missing dates/details that would materially improve a CV.
- Output names/roles in both Hebrew and English only when translation is straightforward; do not embellish.
"""
    source_text = "\n\n".join([x for x in [free_text, "\n\n".join(url_texts), cv_data.get("text", "")] if x])[:45000]
    prompt = f"CURRENT_PROFILE:\n{json.dumps(current_profile or {}, ensure_ascii=False)}\n\nSOURCE_TEXT:\n{source_text or '[No extracted text; inspect attached file/image]'}"
    content = [{"type": "input_text", "text": prompt}]
    if cv_data.get("attachment"):
        content.append(cv_data["attachment"])
    resp = client.responses.create(
        model=model,
        instructions=instructions,
        input=[{"role": "user", "content": content}],
        text={"format": {"type": "json_schema", "name": "candidate_profile", "strict": True, "schema": PROFILE_SCHEMA}},
    )
    return sort_profile(json.loads(resp.output_text))


def display_dates(e, lang="he"):
    if e.get("date_text_original"):
        return e["date_text_original"]
    s, end = e.get("start_date", ""), e.get("end_date", "")
    if e.get("is_current"):
        end = "היום" if lang == "he" else "Present"
    return "–".join(x for x in [s, end] if x)


def demo_result(profile, job_text, lang):
    he = lang != "en"
    exps = []
    for e in profile.get("experience", [])[:7]:
        exps.append({"company": e.get("company", ""), "role": e.get("role_he" if he else "role_en", "") or e.get("role_he", ""), "dates": display_dates(e, "he" if he else "en"), "bullets": e.get("facts", [])[:3]})
    languages = [f"{x.get('name','')} – {x.get('level','')}" for x in profile.get("languages", [])]
    edu = [" — ".join(x for x in [e.get("program", ""), e.get("institution", "")] if x) for e in profile.get("education", [])]
    return {
        "needs_clarification": False, "questions": [],
        "job": {"title": "משרת יעד" if he else "Target role", "company": "", "requirements": []},
        "match": {"score": 65, "strengths": profile.get("skills", [])[:4], "gaps": ["מצב הדגמה: יש לחבר OpenAI API לניתוח אמיתי של המשרה"]},
        "cv": {"language": "he" if he else "en", "headline": "ניהול | תפעול | מכירות" if he else "Management | Operations | Sales", "summary": "תקציר מותאם ייווצר לאחר חיבור מנוע ה-AI." if he else "A tailored summary will be generated after the AI engine is connected.", "skills": profile.get("skills", [])[:9], "experience": exps, "education": edu, "languages": languages},
        "cover_message": "מצורפים קורות החיים שלי. אשמח לשוחח על המשרה." if he else "Please find my CV attached. I would be glad to discuss the role."
    }


def generate_with_openai(profile, job_text, screenshot_data_url, lang, extra_notes):
    client = openai_client()
    model = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
    instructions = """
You are a rigorous CV tailoring engine. Produce a one-page ATS-friendly CV tailored to the job while remaining completely truthful.
1. Use only facts in CANDIDATE_PROFILE plus EXTRA_USER_FACTS. Never invent dates, employers, qualifications, tools, metrics, team sizes or responsibilities.
2. Rephrase and prioritize supported facts. Do not inflate them.
3. If a major requirement is unsupported, set needs_clarification=true and ask a concise question instead of adding it.
4. Preserve uncertain dates rather than guessing.
5. Use 4–8 most relevant experiences, max 4 concise bullets each.
6. If language=auto, follow the job ad language; he=Hebrew; en=English.
7. Return a descriptive match score and transparent gaps.
8. Write a short natural cover/WhatsApp message.
"""
    prompt = f"TARGET_LANGUAGE: {lang}\n\nCANDIDATE_PROFILE:\n{json.dumps(profile, ensure_ascii=False)}\n\nJOB_TEXT:\n{job_text[:20000]}\n\nEXTRA_USER_FACTS:\n{extra_notes or 'None'}"
    content = [{"type": "input_text", "text": prompt}]
    if screenshot_data_url:
        content.append({"type": "input_image", "image_url": screenshot_data_url, "detail": "high"})
    resp = client.responses.create(model=model, instructions=instructions, input=[{"role": "user", "content": content}], text={"format": {"type": "json_schema", "name": "tailored_cv", "strict": True, "schema": CV_SCHEMA}})
    return json.loads(resp.output_text)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"ok": True, "api": bool(os.getenv("OPENAI_API_KEY")), "version": "2.0"})


@app.post("/api/profile/import")
def import_profile():
    try:
        current = json.loads(request.form.get("current_profile") or "{}")
        free_text = (request.form.get("free_text") or "").strip()
        raw_urls = (request.form.get("source_urls") or "").strip()
        cv_data = extract_uploaded_cv(request.files.get("cv_file"))
        url_texts = []
        for url in [x.strip() for x in re.split(r"[\n,]+", raw_urls) if x.strip()][:5]:
            try:
                url_texts.append(f"SOURCE URL: {url}\n{fetch_public_url(url)}")
            except Exception as exc:
                url_texts.append(f"SOURCE URL: {url}\n[Could not fetch automatically: {exc}]")
        if not free_text and not raw_urls and not cv_data.get("text") and not cv_data.get("attachment"):
            return jsonify({"error": "העלה קובץ קורות חיים, כתוב מידע חופשי או הוסף קישור."}), 400
        profile = extract_profile_with_ai(current, free_text, url_texts, cv_data)
        return jsonify({"profile": profile})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.post("/api/profile/normalize")
def normalize_profile():
    try:
        profile = request.get_json(force=True)
        return jsonify(sort_profile(profile))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/generate")
def generate():
    try:
        profile = json.loads(request.form.get("profile_json") or "{}")
        if not profile.get("personal"):
            return jsonify({"error": "קודם צריך לבנות ולשמור פרופיל מקצועי."}), 400
        job_text = (request.form.get("job_text") or "").strip()
        job_url = (request.form.get("job_url") or "").strip()
        lang = request.form.get("language", "auto")
        extra_notes = (request.form.get("extra_notes") or "").strip()
        screenshot = request.files.get("screenshot")
        shot_url = None
        if screenshot and screenshot.filename:
            raw = screenshot.read()
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("צילום המסך גדול מדי")
            mime = screenshot.mimetype or "image/jpeg"
            shot_url = data_url_from_bytes(raw, mime)
        url_text = ""
        if job_url:
            try:
                url_text = fetch_public_url(job_url)
            except Exception as exc:
                url_text = f"URL: {job_url}\n[Could not fetch automatically: {exc}]"
        combined = "\n\n".join(x for x in [job_text, url_text] if x).strip()
        if not combined and not shot_url:
            return jsonify({"error": "העלה צילום מסך, הדבק קישור או תאר את המשרה."}), 400
        if not openai_client():
            result = demo_result(sort_profile(profile), combined, lang)
            result["demo_mode"] = True
            return jsonify(result)
        result = generate_with_openai(sort_profile(profile), combined, shot_url, lang, extra_notes)
        result["demo_mode"] = False
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
