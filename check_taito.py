import requests
from bs4 import BeautifulSoup
import os
import re
import datetime

VERSION = "v6.1"

BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"
WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

session = requests.Session()

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def send_discord(msg):
    if not WEBHOOK_URL:
        log(msg)
        return
    requests.post(WEBHOOK_URL, json={"content": msg})

# =========================
# hidden取得
# =========================
def get_hidden(soup):
    data = {}
    for k in ["__VIEWSTATE", "__EVENTVALIDATION", "__VIEWSTATEGENERATOR"]:
        tag = soup.find("input", {"name": k})
        data[k] = tag["value"] if tag else ""
    return data

# =========================
# POST
# =========================
def post(soup, extra):
    data = get_hidden(soup)
    data.update(extra)
    r = session.post(BASE_URL, data=data)
    return BeautifulSoup(r.text, "html.parser")

# =========================
# ボタン
# =========================
def click(soup, name):
    return post(soup, {name: ""})

# =========================
# カレンダー開く
# =========================
def open_calendar(soup):
    log("📅 カレンダー開く")
    return post(soup, {
        "__EVENTTARGET": "ucTermSetting$btnCalendar",
        "__EVENTARGUMENT": ""
    })

# =========================
# EVENT完全抽出（ここが核心）
# =========================
def extract_event_map(soup):
    html = str(soup)

    # EVENT一覧
    events = re.findall(r"__doPostBack\('([^']+)'", html)

    # 日付一覧（表示順）
    days = []
    for div in soup.find_all("div"):
        title = div.get("title", "")
        if re.match(r"\d{4}年\d{1,2}月\d{1,2}日", title):
            days.append(title)

    # 安全マッピング（順序一致前提）
    mapping = {}
    for i in range(min(len(days), len(events))):
        mapping[days[i]] = events[i]

    log(f"📊 EVENT数: {len(events)} / 日付数: {len(days)}")
    return mapping

# =========================
# 日付選択
# =========================
def select_date(soup, y, m, d):
    target = f"{y}年{m}月{d}日"
    log(f"📅 {target}")

    soup = open_calendar(soup)

    mapping = extract_event_map(soup)

    if target not in mapping:
        log(f"❌ 日付未検出: {target}")
        return soup

    event = mapping[target]
    log(f"➡ EVENTTARGET: {event}")

    return post(soup, {
        "__EVENTTARGET": event,
        "__EVENTARGUMENT": ""
    })

# =========================
# 解析
# =========================
def extract_gym(text):
    if "体育館" not in text:
        return ""
    part = text.split("体育館", 1)[1]
    if "庭球場" in part:
        part = part.split("庭球場", 1)[0]
    return part

def parse(text):
    text = re.sub(r"\s+", " ", text)
    res = []
    cur = None
    tokens = text.split()

    for i in range(len(tokens) - 1):
        t = tokens[i]
        n = tokens[i + 1]

        if t.isdigit() and 1 <= int(t) <= 12:
            cur = t
            continue

        if t.isdigit() and n in ["○", "△"]:
            if cur:
                res.append(f"{cur}/{t} {n}")

    return res

# =========================
# メイン
# =========================
def run_check():
    log(f"🚀 HTTP {VERSION}")

    soup = BeautifulSoup(session.get(BASE_URL).text, "html.parser")

    # 遷移（必要最小限）
    soup = click(soup, "rbtnYoyaku")
    soup = click(soup, "rbtnYoyaku")

    soup = click(soup, "btnNext")
    soup = click(soup, "btnShisetsu")

    soup = click(soup, "ucPCFooter$btnForward")

    soup = post(soup, {
        "rbCalendar": "カレンダー",
        "rbtnMonth": "1ヶ月"
    })

    soup = click(soup, "ucPCFooter$btnForward")

    # =========================
    # 4月
    # =========================
    soup_apr = select_date(soup, 2026, 4, 1)
    res_apr = parse(extract_gym(soup_apr.get_text()))
    log(f"4月: {res_apr}")

    # =========================
    # 5月
    # =========================
    soup_may = select_date(soup, 2026, 5, 1)
    res_may = parse(extract_gym(soup_may.get_text()))
    log(f"5月: {res_may}")

    # =========================
    # 結果
    # =========================
    final = sorted(set(res_apr + res_may))
    log(f"📦 FINAL: {final}")

    if final:
        msg = "@everyone\n🏸 柳北スポーツプラザ\n" + "\n".join(final)
    else:
        msg = "🏸 空きなし"

    send_discord(msg)

if __name__ == "__main__":
    run_check()
