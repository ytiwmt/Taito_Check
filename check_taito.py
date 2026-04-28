import requests
from bs4 import BeautifulSoup
import os
import re
import datetime

VERSION = "v5.0"

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
# ボタン（nameで押す）
# -------------------------
def click_button(soup, name):
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
# 日付選択（核心）
# -------------------------
def select_date(soup, year, month, day):
    log(f"📅 {year}/{month}/{day}")

    # カレンダー開く
    soup = open_calendar(soup)

    # ▼ここがポイント
    # 実際のターゲットは day_x_y のIDになるが、
    # ASP.NETは内部的に以下形式で受ける
    target = f"ucTermSetting$ceCalendar$day"

    # 実装差があるので argumentで日付を送る
    argument = f"{year}/{month}/{day}"

    soup = do_post(soup, {
        "__EVENTTARGET": target,
        "__EVENTARGUMENT": argument
    })

    return soup

# -------------------------
# メイン
# -------------------------
def run_check():
    log(f"🚀 HTTP {VERSION}")

    # 入口
    soup = BeautifulSoup(session.get(BASE_URL).text, "html.parser")

    # -------------------------
    # 遷移
    # -------------------------
    soup = click_button(soup, "rbtnYoyaku")
    soup = click_button(soup, "rbtnYoyaku")  # 空き照会

    soup = click_button(soup, "btnNext")  # 次頁（環境で違う可能性あり）
    soup = click_button(soup, "btnShisetsu")  # 柳北

    # -------------------------
    # 表示設定
    # -------------------------
    soup = click_button(soup, "ucPCFooter$btnForward")

    soup = do_post(soup, {
        "rbCalendar": "カレンダー",
        "rbtnMonth": "1ヶ月"
    })

    soup = click_button(soup, "ucPCFooter$btnForward")

    # -------------------------
    # 4月
    # -------------------------
    soup_apr = select_date(soup, 2026, 4, 1)
    text_apr = soup_apr.get_text()
    res_apr = parse(extract_gym(text_apr))
    log(f"4月: {res_apr}")

    # -------------------------
    # 5月
    # -------------------------
    soup_may = select_date(soup, 2026, 5, 1)
    text_may = soup_may.get_text()
    res_may = parse(extract_gym(text_may))
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
