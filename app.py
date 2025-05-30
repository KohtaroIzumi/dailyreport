from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import json
import requests
from functools import wraps
from datetime import datetime, timedelta
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

@app.route('/preview_api')
@login_required
def preview_api():
    name = request.args.get("name")
    date_str = request.args.get("date")
    try:
        base_date = datetime.strptime(date_str, "%Y-%m-%d")
        month_start = base_date.replace(day=1).strftime("%Y-%m-%d")
        next_month = (base_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        month_end = next_month.strftime("%Y-%m-%d")
    except ValueError:
        return jsonify({"records": []})

    params = {
        "select": "*",
        "and": f"(name.eq.{name},date.gte.{month_start},date.lt.{month_end})"
    }
    response = requests.get(f"{SUPABASE_URL}/rest/v1/daily_report", headers=HEADERS, params=params)
    if response.status_code == 200:
        return jsonify({"records": response.json()})
    return jsonify({"records": []})

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
