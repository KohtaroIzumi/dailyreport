from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD")
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}"
}

NOTICE_VERSION = "2025-05-30"  # ← 本日の日付が通知バージョン（将来的にはSupabaseから取得へ）

# -------- 認証とお知らせ確認のチェック --------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def notice_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        seen_version = session.get("notice_version")
        skipped = session.get("notice_skipped")
        if seen_version != NOTICE_VERSION and not skipped:
            return redirect(url_for("notice"))
        return f(*args, **kwargs)
    return decorated_function

# -------- ルート --------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form["password"]
        if password == ACCESS_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("notice"))
        else:
            return render_template("login.html", error="パスワードが間違っています。")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/notice")
@login_required
def notice():
    return render_template("notice.html", notice_version=NOTICE_VERSION)

@app.route("/acknowledge_notice", methods=["POST"])
@login_required
def acknowledge_notice():
    session["notice_version"] = NOTICE_VERSION
    session["notice_skipped"] = False
    return redirect(url_for("index"))

@app.route("/skip_notice", methods=["POST"])
@login_required
def skip_notice():
    session["notice_skipped"] = True
    return redirect(url_for("index"))

@app.route("/")
@login_required
@notice_required
def index():
    res_name = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    names = [row["name"] for row in res_name.json()] if res_name.status_code == 200 else []

    res_cat = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    categories = res_cat.json() if res_cat.status_code == 200 else []

    category_map = {}
    for row in categories:
        category_map.setdefault(row["category"], []).append(row["detail"])

    return render_template("index.html", names=names, categories=categories, category_map=category_map)

@app.route("/submit", methods=["POST"])
@login_required
def submit():
    try:
        data = request.json
        date_str = data.get("date")
        name = data.get("name")
        tasks = data.get("tasks", [])

        for task in tasks:
            payload = {
                "report_date": date_str,
                "name": name,
                "category": task.get("category"),
                "detail": task.get("detail"),
                "hours": float(task.get("hours", 0)),
                "comment": task.get("comment", "")
            }
            requests.post(
                f"{SUPABASE_URL}/rest/v1/daily_report",
                headers={**HEADERS, "Content-Type": "application/json"},
                json=payload
            )

        return jsonify({"message": "送信完了しました"})
    except Exception as e:
        return jsonify({"message": "送信エラー"}), 500

@app.route("/master")
@login_required
@notice_required
def master():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    category_map = {}
    if res.status_code == 200:
        for row in res.json():
            category_map.setdefault(row["category"], []).append(row["detail"])
    return render_template("master.html", category_map=category_map)

@app.route("/preview")
@login_required
@notice_required
def preview():
    selected_date = request.args.get("date")
    selected_name = request.args.get("name")

    if not selected_date or not selected_name:
        return render_template("preview.html", tasks=[], datadate=selected_date, name=selected_name)

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
    data = res.json() if res.status_code == 200 else []
    return render_template("preview.html", tasks=data, datadate=selected_date, name=selected_name)

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
    total = sum(float(row.get("hours", 0)) for row in res.json()) if res.status_code == 200 else 0
    return jsonify({"monthly_hours": total})

if __name__ == "__main__":
    app.run(debug=True)