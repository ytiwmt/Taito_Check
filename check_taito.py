import requests
from bs4 import BeautifulSoup
import re
import datetime
import os

VERSION = "v7.16-http-direct-stable"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    log(msg)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# パース
# =========================
def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    results = []

    for a in soup.select("a[id*='lnkKoma']"):
        txt = a.get_text(strip=True).replace("\xa0", "")
        m = re.search(r"(\d+)(○|△|×)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    return results


# =========================
# メイン（重要）
# =========================
def run():
    log(f"🚀 {VERSION}")

    session = requests.Session()

    # ① 初期ページ
    r = session.get("https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect")
    html = r.text

    # ※ここは本来フォームPOST再現が必要だが省略不可（要調整ポイント）
    # → 実運用では form_data 再構築が必要

    res1 = parse_html(html)
    log(f"1P: {res1}")

    # ここで本当はPOSTでページ遷移する必要あり
    # → Playwrightを捨てるなら完全HTTP再現が必要

    send(f"🏸 TEST {VERSION} / {len(res1)}件")


if __name__ == "__main__":
    run()
