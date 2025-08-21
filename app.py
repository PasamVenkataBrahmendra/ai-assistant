from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, Response, stream_with_context
import os
import time
import json
import re
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder=".", template_folder=".")
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-12345")

# Gemini API (optional)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"

# Personalities
PERSONALITIES = {
    "friendly": {
        "prefix": "You are a friendly and enthusiastic AI assistant. Respond in a warm, caring way with emojis.",
        "greetings": ["Hey there! 😊", "Hello friend! 🌟", "Hi! How can I brighten your day?"],
        "emoji": "😊"
    },
    "professional": {
        "prefix": "You are a professional and formal AI assistant. Respond in a business-like manner.",
        "greetings": ["Good day.", "How may I assist you?", "Welcome. How can I help?"],
        "emoji": "💼"
    },
    "quirky": {
        "prefix": "You are a quirky and fun AI assistant. Respond with humor, robot sounds, and playful language.",
        "greetings": ["Beep boop! 🤖", "Greetings, human! 👽", "robot noises Hello! 🎵"],
        "emoji": "🤖"
    },
    "coder": {
        "prefix": "You are an expert programmer and code reviewer. Focus on technical accuracy, best practices, and detailed explanations.",
        "greetings": ["Ready to code! 💻", "Let's debug some code! 🔧", "What programming challenge can I help with?"],
        "emoji": "💻"
    }
}

def require_login():
    return 'user' in session

@app.route("/")
def index():
    if not require_login():
        return redirect(url_for("login"))
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        if email and password:
            session["user"] = email
            flash("Logged in successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        phone = request.form.get("phone")
        if email and password:
            session["user"] = email
            flash("Account created successfully!", "success")
            return redirect(url_for("index"))
        else:
            flash("Please fill all required fields", "warning")
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        flash("If an account exists with this email, you will receive password reset instructions", "info")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")

@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if request.method == "POST":
        flash("Password has been reset (demo).", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html")

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    return render_template("500.html"), 500

# Language detection
def detect_programming_language(code: str) -> str:
    patterns = {
        'python': [r'\bdef\s+\w+', r'\bimport\s+\w+', r'\bfrom\s+\w+\s+import', r'print\('],
        'javascript': [r'\bfunction\s+\w+', r'\b(var|let|const)\s+\w+', r'console\.log', r'=>', r'document\.'],
        'java': [r'\bpublic\s+class\s+\w+', r'\bpublic\s+static\s+void\s+main', r'System\.out\.print'],
        'c': [r'#include\s*<\w+\.h>', r'\bint\s+main\s*\(', r'\bprintf\s*\('],
        'cpp': [r'#include\s*<', r'\bstd::', r'\bcout\s*<<'],
        'csharp': [r'using\s+System', r'\bnamespace\s+\w+', r'\bclass\s+\w+', r'Console\.Write'],
        'php': [r'<\?php', r'\becho\s+', r'\$\w+\s*='],
        'sql': [r'\bSELECT\b', r'\bINSERT\b', r'\bUPDATE\b', r'\bDELETE\b'],
        'html': [r'<!DOCTYPE html>', r'<html', r'</html>'],
        'css': [r'[a-z-]+\s*:\s*[^;]+;', r'\.\w+\s*{', r'#\w+\s*{'],
        'bash': [r'#!/bin/bash', r'\becho\b', r'\bapt-get\b'],
        'react': [r'from\s+["\']react', r'\buse(State|Effect)\b', r'<[A-Z]\w+'],
        'flask': [r'from\s+flask\s+import', r'@app\.route']
    }
    for lang, pats in patterns.items():
        if any(re.search(p, code, flags=re.IGNORECASE) for p in pats):
            return lang
    return "auto"

def build_prompt(mode: str, personality: str, text: str, code_text: str = "", language: str = "auto") -> str:
    persona = PERSONALITIES.get(personality, PERSONALITIES["friendly"])["prefix"]
    now = datetime.datetime.utcnow().isoformat()
    if mode == "debug":
        if language == "auto":
            language = detect_programming_language(code_text or text)
        return f"{persona}\nTime(UTC): {now}\nAnalyze and fix the following {language} code with step-by-step reasoning and a corrected version:\n\n{code_text or text}"
    return f"{persona}\nTime(UTC): {now}\nUser said:\n{text}"

def sse_chunks(text: str):
    for chunk in re.findall(r'.{1,120}', text, flags=re.S):
        yield chunk
        time.sleep(0.02)

def generate_from_gemini(prompt: str):
    if not GEMINI_API_KEY:
        yield from sse_chunks("No GEMINI_API_KEY set. Streaming demo so UI works.\n\n" + prompt[:600])
        return
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        d = r.json()
        text = ""
        candidates = d.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                text = parts[0].get("text", "")
        if not text:
            text = "(Empty response)"
        yield from sse_chunks(text)
    except requests.exceptions.RequestException as e:
        yield from sse_chunks(f"[LLM error] {e}")

@app.route("/api/stream", methods=["POST"])
def api_stream():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    mode = data.get("mode", "chat")
    personality = data.get("personality", "friendly")
    message = (data.get("message") or "").strip()
    code_text = data.get("code", "")
    language = data.get("language", "auto")

    prompt = build_prompt(mode, personality, message, code_text, language)

    def event_stream():
        yield "event:start\ndata: {}\n\n"
        for chunk in generate_from_gemini(prompt):
            safe = chunk.replace("\n", "\\n")
            yield f"data: {safe}\n\n"
        yield "event:end\ndata: {}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(force=True) or {}
    code = data.get("code", "")
    language = data.get("language", "auto")
    if language == "auto":
        language = detect_programming_language(code)
    prompt = build_prompt("debug", "coder", "", code_text=code, language=language)

    if not GEMINI_API_KEY:
        return jsonify({"language": language, "analysis": f"(Mock) Detected {language}. Add GEMINI_API_KEY for real analysis."})

    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        d = r.json()
        txt = ""
        candidates = d.get("candidates", [])
        if candidates and "content" in candidates[0]:
            parts = candidates[0]["content"].get("parts", [])
            if parts:
                txt = parts[0].get("text", "")
        return jsonify({"language": language, "analysis": txt})
    except requests.exceptions.RequestException as e:
        return jsonify({"language": language, "analysis": f"Error: {e}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
