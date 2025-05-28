from flask import Flask, render_template, request, jsonify
import os
import requests
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
app = Flask(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
HEADERS = {
    "apikey": SUPABASE_API_KEY,
    "Authorization": f"Bearer {SUPABASE_API_KEY}"
}

@app.route("/")
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
def submit():
    try:
        data = request.json
        print("DEBUG: 受信データ", data)

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
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/daily_report",
                headers={**HEADERS, "Content-Type": "application/json"},
                json=payload
            )
            print("DEBUG: Supabase応答", res.status_code, res.text)

        return jsonify({"message": "送信完了しました"})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"message": "送信エラー"}), 500

@app.route("/master")
def master():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    category_map = {}
    if res.status_code == 200:
        rows = res.json()
        for row in rows:
            category_map.setdefault(row["category"], []).append(row["detail"])
    return render_template("master.html", category_map=category_map)

@app.route("/preview")
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

    if res.status_code == 200:
        data = res.json()
    else:
        print("ERROR: Failed to fetch preview data:", res.status_code, res.text)
        data = []

    return render_template("preview.html", tasks=data, datadate=selected_date, name=selected_name)

@app.route("/preview_api")
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

if __name__ == "__main__":
    app.run(debug=True)