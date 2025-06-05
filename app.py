from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from functools import wraps
import json

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
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

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in allowed_roles:
                return "403 Forbidden: アクセス権限がありません", 403
            return f(*args, **kwargs)
        return wrapper
    return decorator

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        password = request.form.get("password")

        url = f"{SUPABASE_URL}/rest/v1/master_name?employee_id=eq.{employee_id}&select=*"
        response = requests.get(url, headers=HEADERS)

        if response.status_code == 200 and response.json():
            user = response.json()[0]
            if user['password'] == password:
                session.update({
                    "logged_in": True,
                    "employee_id": user['employee_id'],
                    "name": user['name'],
                    "role": user['role'],
                    "must_reset_password": user['must_reset_password']
                })
                return redirect(url_for("reset_password" if user['must_reset_password'] else "index"))
            return render_template("login.html", error="入力内容に誤りがあります")
        return render_template("login.html", error="入力内容に誤りがあります")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/reset_password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "POST":
        new_password = request.form.get("new_password")
        employee_id = session.get("employee_id")
        if not employee_id or not new_password:
            return render_template("reset_password.html", error="入力内容に不備があります")

        url = f"{SUPABASE_URL}/rest/v1/master_name?employee_id=eq.{employee_id}"
        headers = {**HEADERS, "Content-Type": "application/json"}
        payload = {"password": new_password, "must_reset_password": False}
        res = requests.patch(url, headers=headers, json=payload)

        if res.status_code in [200, 204]:
            session["must_reset_password"] = False
            return redirect(url_for("index"))
        return render_template("reset_password.html", error="パスワードの更新に失敗しました")
    return render_template("reset_password.html")

@app.route("/")
@login_required
def index():
    today = datetime.now().strftime("%Y-%m-%d")

    res_name = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    names = [row["name"] for row in res_name.json()] if res_name.status_code == 200 else []

    res_cat = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    categories = res_cat.json() if res_cat.status_code == 200 else []

    category_map = {}
    for row in categories:
        cat, det = row["category"], row["detail"]
        category_map.setdefault(cat, []).append(det)

    return render_template("index.html", names=names, categories=categories, category_map=category_map,
                           role=session.get("role"), must_reset_password=session.get("must_reset_password"),
                           user_name=session.get("name"), today=today)

@app.route("/master")
@login_required
def master():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    categories = res.json() if res.status_code == 200 else []

    category_map = {}
    for row in categories:
        cat, det = row["category"], row["detail"]
        category_map.setdefault(cat, []).append(det)

    return render_template("master.html", master=categories, category_map=category_map)

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
            requests.post(f"{SUPABASE_URL}/rest/v1/daily_report",
                          headers={**HEADERS, "Content-Type": "application/json"}, json=payload)
        return jsonify({"message": "送信完了しました"})
    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"message": "送信エラー"}), 500

@app.route("/delete_task", methods=["DELETE"])
@login_required
def delete_task():
    task_id = request.args.get("id")
    if not task_id:
        return jsonify({"error": "IDが無し"}), 400

    url = f"{SUPABASE_URL}/rest/v1/daily_report?id=eq.{task_id}"
    res = requests.delete(url, headers=HEADERS)
    if res.status_code in [200, 204]:
        return jsonify({"message": "削除成功"})
    return jsonify({"error": "削除失敗"}), 500

@app.route("/save_draft", methods=["POST"])
@login_required
def save_draft():
    try:
        data = request.json
        employee_id = session.get("employee_id")
        date = data.get("date")
        tasks = data.get("tasks", [])
        if not employee_id or not date:
            return jsonify({"error": "社員IDまたは日付が不正です"}), 400

        get_url = f"{SUPABASE_URL}/rest/v1/daily_draft?employee_id=eq.{employee_id}&date=eq.{date}"
        get_res = requests.get(get_url, headers=HEADERS)
        payload = {"employee_id": employee_id, "date": date, "draft_json": tasks}
        headers_with_type = {**HEADERS, "Content-Type": "application/json"}

        if get_res.status_code == 200 and get_res.json():
            patch_url = get_url
            patch_res = requests.patch(patch_url, headers=headers_with_type, json=payload)
            return jsonify({"message": "一時保存を更新しました"}) if patch_res.status_code in [200, 204] else jsonify({"error": "上書き失敗"}), 500
        else:
            post_url = f"{SUPABASE_URL}/rest/v1/daily_draft"
            post_res = requests.post(post_url, headers=headers_with_type, json=payload)
            return jsonify({"message": "一時保存しました"}) if post_res.status_code in [200, 201, 204] else jsonify({"error": "保存に失敗しました"}), 500
    except Exception as e:
        print("ERROR in /save_draft:", str(e))
        return jsonify({"error": "内部エラー"}), 500

@app.route("/load_draft", methods=["GET"])
@login_required
def load_draft():
    try:
        employee_id = session.get("employee_id")
        date = request.args.get("date")
        if not employee_id or not date:
            return jsonify({"error": "パラメータ不正"}), 400

        url = f"{SUPABASE_URL}/rest/v1/daily_draft?employee_id=eq.{employee_id}&date=eq.{date}&select=draft_json"
        res = requests.get(url, headers=HEADERS)
        return jsonify({"tasks": res.json()[0]["draft_json"]}) if res.status_code == 200 and res.json() else jsonify({"tasks": []})
    except Exception as e:
        print("ERROR in /load_draft:", str(e))
        return jsonify({"error": "読み込み失敗"}), 500

@app.route("/preview")
@login_required
def preview():
    selected_date = request.args.get("date")
    selected_name = request.args.get("name", "").strip()
    if not selected_date or not selected_name:
        return render_template("preview.html", tasks=[], datadate=selected_date, name=selected_name)

    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    start = dt.replace(day=1).strftime("%Y-%m-%d")
    end = (dt.replace(year=dt.year + 1, month=1, day=1) if dt.month == 12 else dt.replace(month=dt.month + 1, day=1)).strftime("%Y-%m-%d")

    query_url = f"{SUPABASE_URL}/rest/v1/daily_report?name=eq.{selected_name}&report_date=gte.{start}&report_date=lt.{end}"
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
    end = (dt.replace(year=dt.year + 1, month=1, day=1) if dt.month == 12 else dt.replace(month=dt.month + 1, day=1)).strftime("%Y-%m-%d")

    query_url = f"{SUPABASE_URL}/rest/v1/daily_report?name=eq.{selected_name}&report_date=gte.{start}&report_date=lt.{end}"
    res = requests.get(query_url, headers=HEADERS)
    total = sum(float(r.get("hours", 0)) for r in res.json()) if res.status_code == 200 else 0
    return jsonify({"monthly_hours": total})

@app.route("/graph")
@login_required
@role_required(["Manager", "Admin"])
def graph():
    return render_template("graph.html")

@app.route("/graph_data")
@login_required
@role_required(["Manager", "Admin"])
def graph_data():
    name = request.args.get("name")
    year = request.args.get("year")
    month = request.args.get("month")
    if not year or not month:
        return jsonify({"error": "年月が必要です"}), 400

    name = name.strip() if name else None
    start = f"{year}-{month.zfill(2)}-01"
    end = f"{int(year)+1}-01-01" if month == "12" else f"{year}-{str(int(month)+1).zfill(2)}-01"
    filters = [f"report_date=gte.{start}", f"report_date=lt.{end}"]
    if name:
        filters.append(f"name=eq.{name}")
    url = f"{SUPABASE_URL}/rest/v1/daily_report?{'&'.join(filters)}"
    res = requests.get(url, headers=HEADERS)
    return jsonify(res.json()) if res.status_code == 200 else jsonify([])

@app.route("/api/names")
@login_required
@role_required(["Manager", "Admin"])
def api_names():
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    return jsonify([r["name"] for r in res.json()]) if res.status_code == 200 else jsonify([])

if __name__ == "__main__":
    app.run(debug=True)