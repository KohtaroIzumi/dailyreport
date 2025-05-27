from flask import Flask, render_template, request, jsonify
import os
import requests
from dotenv import load_dotenv

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
        date_str = data.get("date")
        name = data.get("name")
        comment = data.get("comment")
        tasks = data.get("tasks", [])

        for task in tasks:
            payload = {
                "date": date_str,
                "name": name,
                "category": task.get("category"),
                "detail": task.get("detail"),
                "hours": float(task.get("hours", 0)),
                "comment": comment
            }
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/daily_report",
                headers={**HEADERS, "Content-Type": "application/json"},
                json=payload
            )
            print("DEBUG: Supabase response:", res.status_code, res.text)

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
            cat = row["category"]
            det = row["detail"]
            category_map.setdefault(cat, []).append(det)
    else:
        print("ERROR: master fetch failed", res.status_code, res.text)

    return render_template("master.html", category_map=category_map)

if __name__ == "__main__":
    app.run(debug=True)