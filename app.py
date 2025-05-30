from flask import Flask, render_template, request, redirect, url_for, session
import os
import json
import requests
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_API_KEY")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
NOTICE_VERSION = os.getenv("NOTICE_VERSION")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    if session.get("notice_checked_version") != NOTICE_VERSION:
        return redirect(url_for("notice"))
    names = fetch_names()
    categories, category_map = fetch_categories()
    return render_template("index.html", names=names, categories=categories, category_map=category_map)

@app.route('/submit', methods=['POST'])
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

@app.route('/preview')
@login_required
def preview():
    date = request.args.get("date")
    name = request.args.get("name")
    if not date or not name:
        return "必要な情報が不足しています", 400

    yyyymm = "-".join(date.split("-")[:2])
    params = {
        "select": "*",
        "name": f"eq.{name}",
        "date": f"like.{yyyymm}-%"
    }
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    response = requests.get(f"{SUPABASE_URL}/rest/v1/daily_report?{query_string}", headers=HEADERS)
    if response.status_code != 200:
        return "データ取得に失敗しました", 500

    records = response.json()
    total_hours = sum(float(row.get("hours", 0)) for row in records)
    return render_template("preview.html", records=records, total_hours=total_hours, date=date, name=name)

@app.route('/master')
@login_required
def master():
    categories, _ = fetch_categories()
    grouped = {}
    for item in categories:
        cat = item['category']
        grouped.setdefault(cat, []).append(item['detail'])
    return render_template("master.html", grouped=grouped)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form['password']
        if password == ACCESS_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template("login.html", error="パスワードが間違っています")
    return render_template("login.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/notice')
@login_required
def notice():
    return render_template("notice.html", version=NOTICE_VERSION)

@app.route('/acknowledge_notice', methods=["POST"])
@login_required
def acknowledge_notice():
    if request.form.get("confirm"):
        session["notice_checked_version"] = NOTICE_VERSION
        return redirect(url_for("index"))
    return redirect(url_for("notice"))

@app.route('/skip_notice')
@login_required
def skip_notice():
    return redirect(url_for("index"))

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