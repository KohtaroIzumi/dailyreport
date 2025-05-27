from flask import Flask, render_template, request
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
    # 氏名マスター取得
    res_name = requests.get(f"{SUPABASE_URL}/rest/v1/master_name?select=name", headers=HEADERS)
    names = [row["name"] for row in res_name.json()] if res_name.status_code == 200 else []

    # カテゴリーマスター取得
    res_cat = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)
    categories = res_cat.json() if res_cat.status_code == 200 else []

    # カテゴリ → 詳細 の辞書を作成
    category_map = {}
    for row in categories:
        cat = row["category"]
        det = row["detail"]
        if cat not in category_map:
            category_map[cat] = []
        category_map[cat].append(det)

    print("DEBUG: SUPABASE_API_KEY =", SUPABASE_API_KEY)
    print("DEBUG: category_map content:", category_map)

    return render_template("index.html", categories=categories, names=names, category_map=category_map)

@app.route("/master")
def master():
    # master_category の全件取得
    res = requests.get(f"{SUPABASE_URL}/rest/v1/master_category?select=category,detail", headers=HEADERS)

    category_map = {}
    if res.status_code == 200:
        rows = res.json()
        for row in rows:
            cat = row["category"]
            det = row["detail"]
            if cat not in category_map:
                category_map[cat] = []
            category_map[cat].append(det)
    else:
        print("ERROR: Failed to fetch master_category")
        print("Status:", res.status_code)
        print("Content:", res.text)

    return render_template("master.html", category_map=category_map)

if __name__ == "__main__":
    app.run(debug=True)