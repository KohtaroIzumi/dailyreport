from flask import Flask, render_template, request, jsonify, session, redirect, url_for
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

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password")
        if password == ACCESS_PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="パスワードが違います")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    res_name = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    names = [row["name"] for row in res_name.json()] if res_name.status_code == 200 else []

    res_cat = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    categories = res_cat.json() if res_cat.status_code == 200 else []

    category_map = {}
    for row in categories:
        cat = row["category"]
        det = row["detail"]
        category_map.setdefault(cat, []).append(det)

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
        print("ERROR:", str(e))
        return jsonify({"message": "送信エラー"}), 500

@app.route("/master")
@login_required
def master():
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
        res.raise_for_status()
        rows = res.json()
        category_map = {}
        for row in rows:
            cat = row.get("category")
            det = row.get("detail")
            if cat and det:
                category_map.setdefault(cat, []).append(det)
        return render_template("master.html", category_map=category_map)
    except Exception as e:
        print("ERROR in /master:", e)
        return "サーバー内部エラー（/master で例外が発生しました）", 500

@app.route("/preview")
@login_required
def preview():
    selected_date = request.args.get("date")
    selected_name = request.args.get("name", "").strip()

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
    total = 0
    if res.status_code == 200:
        rows = res.json()
        for r in rows:
            total += float(r.get("hours", 0))
    return jsonify({"monthly_hours": total})

@app.route("/graph")
@login_required
def graph():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    names = [r["name"] for r in res.json()] if res.status_code == 200 else []
    return render_template("graph.html", names=names)

@app.route("/graph_data")
@login_required
def graph_data():
    name = request.args.get("name")
    year = request.args.get("year")
    month = request.args.get("month")

    if not year or not month:
        return jsonify({"error": "年月が必要です"}), 400

    try:
        name = name.strip() if name else None  # ← ここが重要
        start = f"{year}-{month.zfill(2)}-01"
        if month == "12":
            end = f"{int(year)+1}-01-01"
        else:
            end = f"{year}-{str(int(month)+1).zfill(2)}-01"

        filters = [f"report_date=gte.{start}", f"report_date=lt.{end}"]
        if name:
            filters.append(f"name=eq.{name}")
        filter_str = "&".join(filters)

        url = f"{SUPABASE_URL}/rest/v1/daily_report?{filter_str}"
        res = requests.get(url, headers=HEADERS)
        data = res.json() if res.status_code == 200 else []

        return jsonify(data)
    except Exception as e:
        print("ERROR in /graph_data:", e)
        return jsonify({"error": "内部処理エラー"}), 500

if __name__ == "__main__":
    app.run(debug=True)