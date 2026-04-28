import requests
from bs4 import BeautifulSoup
import os
import re
import datetime

VERSION = "v6.0"

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

# -------------------------
# hidden取得
# -------------------------
def get_hidden(soup):
    data = {}
    for name in ["__VIEWSTATE", "__EVENTVALIDATION", "__VIEWSTATEGENERATOR"]:
        tag = soup.find("input", {"name": name})
        data[name] = tag["value"] if tag else ""
    return data

# -------------------------
# POST
# -------------------------
def do_post(soup, extra):
    data = get_hidden(soup)
    data.update(extra)
    r = session.post(BASE_URL, data=data)
    return BeautifulSoup(r.text, "html.parser")

# -------------------------
# ボタン押し（nameベース）
# -------------------------
def click_by_name(soup, name):
    return do_post(soup, {name: ""})

# -------------------------
# 解析
# -------------------------
def extract_gym(text):
    if "体育館" not in text:
        return ""
    part = text.split("体育館", 1)[1]
    if "庭球場" in part:
        part = part.split("庭球場", 1)[0]
    return part

def parse(text):
    text = re.sub(r"\s+", " ", text)
    results = []
    current_month = None
    tokens = text.split()

    for i in range(len(tokens) - 1):
        t = tokens[i]
        n = tokens[i + 1]

        if t.isdigit() and 1 <= int(t) <= 12:
            current_month = t
            continue

        if t.isdigit() and n in ["○", "△"]:
            if current_month:
                results.append(f"{current_month}/{t} {n}")

    return results

# -------------------------
# カレンダー開く
# -------------------------
def open_calendar(soup):
    log("📅 カレンダー開く")
    return do_post(soup, {
        "__EVENTTARGET": "ucTermSetting$btnCalendar",
        "__EVENTARGUMENT": ""
    })

# -------------------------
# EVENTTARGET抽出（核心）
# -------------------------
def extract_calendar_targets(soup):
    targets = {}

    for a in soup.find_all("a"):
        href = a.get("href", "")
        title = a.get("title", "")

        if "__doPostBack" in href and "年" in title:
            m = re.search(r"__doPostBack\('([^']+)'", href)
            if m:
                event = m.group(1)
                targets[title] = event

    return targets

# -------------------------
# 日付選択（完全自動）
# -------------------------
def select_date(soup, year, month, day):
    target_title = f"{year}年{month}月{day}日"
    log(f"📅 {target_title}")

    # カレンダー開く
    soup = open_calendar(soup)

    # EVENT一覧取得
    targets = extract_calendar_targets(soup)

    if target_title not in targets:
        log(f"❌ ターゲットなし: {target_title}")
        return soup

    event = targets[target_title]
    log(f"➡ EVENTTARGET: {event}")

    # POST
    soup = do_post(soup, {
        "__EVENTTARGET": event,
        "__EVENTARGUMENT": ""
    })

    return soup

# -------------------------
# メイン
# -------------------------
def run_check():
    log(f"🚀 HTTP {VERSION}")

    soup = BeautifulSoup(session.get(BASE_URL).text, "html.parser")

    # -------------------------
    # 遷移（ここは環境依存なので調整前提）
    # -------------------------
    soup = click_by_name(soup, "rbtnYoyaku")
    soup = click_by_name(soup, "rbtnYoyaku")

    soup = click_by_name(soup, "btnNext")
    soup = click_by_name(soup, "btnShisetsu")

    soup = click_by_name(soup, "ucPCFooter$btnForward")

    soup = do_post(soup, {
        "rbCalendar": "カレンダー",
        "rbtnMonth": "1ヶ月"
    })

    soup = click_by_name(soup, "ucPCFooter$btnForward")

    # -------------------------
    # 4月
    # -------------------------
    soup_apr = select_date(soup, 2026, 4, 1)
    res_apr = parse(extract_gym(soup_apr.get_text()))
    log(f"4月: {res_apr}")

    # -------------------------
    # 5月
    # -------------------------
    soup_may = select_date(soup, 2026, 5, 1)
    res_may = parse(extract_gym(soup_may.get_text()))
    log(f"5月: {res_may}")

    # -------------------------
    # 結果
    # -------------------------
    final = sorted(set(res_apr + res_may))
    log(f"📦 FINAL: {final}")

    if final:
        msg = "@everyone\n🏸 柳北スポーツプラザ\n"
        msg += "\n".join(final)
    else:
        msg = "🏸 空きなし"

    send_discord(msg)

if __name__ == "__main__":
    run_check()
