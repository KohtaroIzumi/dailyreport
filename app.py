from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import requests
from functools import wraps
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}",
    "Content-Type": "application/json"
}

NOTICE_VERSION = os.getenv("NOTICE_VERSION", "20250101")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")

# decorator

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def notice_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("notice_seen") or session.get("notice_version") != NOTICE_VERSION:
            return redirect(url_for("notice"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ACCESS_PASSWORD:
            session['logged_in'] = True
            session['notice_seen'] = False  # 強制的にお知らせを再表示
            return redirect(url_for("notice"))
        return render_template("login.html", error="パスワードが間違っています")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
@notice_required
def index():
    names = fetch_names()
    categories, category_map = fetch_categories()
    return render_template("index.html", names=names, categories=categories, category_map=category_map)

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    data = request.get_json()
    tasks = data.get("tasks", [])
    for task in tasks:
        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/daily_report",
            headers=HEADERS,
            data=json.dumps(task)
        )
    return ("", 204)

@app.route("/master")
@login_required
@notice_required
def master():
    categories, _ = fetch_categories()
    grouped = {}
    for item in categories:
        cat = item['category']
        grouped.setdefault(cat, []).append(item['detail'])
    return render_template("master.html", grouped=grouped)

@app.route("/notice")
@login_required
def notice():
    return render_template("notice.html", version=NOTICE_VERSION)

@app.route("/acknowledge_notice", methods=["POST"])
@login_required
def acknowledge_notice():
    try:
        confirm = request.form.get("confirm")
        if confirm == "on":
            session["notice_seen"] = True
            session["notice_version"] = NOTICE_VERSION
        return redirect(url_for("index"))
    except Exception as e:
        print("Error in acknowledge_notice:", e)
        return "Internal Server Error", 500

@app.route("/skip_notice", methods=["POST"])
@login_required
def skip_notice():
    try:
        session["notice_seen"] = False
        return redirect(url_for("index"))
    except Exception as e:
        print("Error in skip_notice:", e)
        return "Internal Server Error", 500

@app.route("/preview_api")
@login_required
def preview_api():
    selected_date = request.args.get("date")
    selected_name = request.args.get("name")

    if not selected_date or not selected_name:
        return jsonify({"monthly_hours": 0})

    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    start = dt.replace(day=1).strftime("%Y-%m-%d")
    if dt.month == 12:
        end = dt.replace(year=dt.year + 1, month=1, day=1).strftime("%Y-%m-%d")
    else:
        end = dt.replace(month=dt.month + 1, day=1).strftime("%Y-%m-%d")

    query_url = (
        f"{SUPABASE_URL}/rest/v1/daily_report"
        f"?name=eq.{selected_name}"
        f"&report_date=gte.{start}"
        f"&report_date=lt.{end}"
    )

    res = requests.get(query_url, headers=HEADERS)
    total = 0
    if res.status_code == 200:
        rows = res.json()
        for r in rows:
            total += float(r.get("hours", 0))
    else:
        print("ERROR: Failed to fetch monthly hours:", res.status_code, res.text)

    return jsonify({"monthly_hours": total})

def fetch_names():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/master_name", headers=HEADERS)
    if response.status_code == 200:
        return [item["name"] for item in response.json()]
    return []

def fetch_categories():
    response = requests.get(f"{SUPABASE_URL}/rest/v1/master_category", headers=HEADERS)
    if response.status_code == 200:
        category_data = response.json()
        categories = list({item["category"] for item in category_data})
        category_map = {}
        for item in category_data:
            cat = item["category"]
            detail = item["detail"]
            category_map.setdefault(cat, []).append(detail)
        return category_data, category_map
    return [], {}

if __name__ == '__main__':
    app.run(debug=True)