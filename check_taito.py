import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v4.0"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def send_discord(msg):
    if not WEBHOOK_URL_Taito:
        log(msg)
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})

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

def analyze(text, results, label):
    if "不正な遷移" in text:
        log(f"{label}: ❌ エラー")
        return "error"

    if not results:
        log(f"{label}: 🟡 空きなし")
        return "empty"

    log(f"{label}: 🟢 {results}")
    return "ok"

# =========================
# 日付クリック関数
# =========================
def select_date(page, year, month, day):
    log(f"📅 {year}/{month}/{day} を選択")

    # カレンダー開く
    page.locator("input[name='ucTermSetting$btnCalendar']").click()
    page.wait_for_selector("div.ajax__calendar_day")

    # titleで指定（最安定）
    target = f"{year}年{month}月{day}日"
    page.locator(f"div[title='{target}']").click()

    # 更新待ち
    page.wait_for_timeout(2000)

# =========================
# メイン
# =========================
def run_check():
    with sync_playwright() as p:
        log(f"🚀 Playwright {VERSION}")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # -------------------------
            # 入口
            # -------------------------
            page.goto(BASE_URL)
            page.wait_for_url("**Wg_ModeSelect.aspx**")

            # -------------------------
            # 遷移（元ルート）
            # -------------------------
            page.locator("input[value='公共施設予約メニュー']").click()
            page.wait_for_selector("input[value^='1. 空き照会']")

            page.locator("input[value^='1. 空き照会']").click()
            page.wait_for_selector("input[value='次頁']")

            page.locator("input[value='次頁']").click()
            page.wait_for_selector("input[value='柳北スポーツプラザ']")

            page.locator("input[value='柳北スポーツプラザ']").click()
            page.wait_for_selector("input[name='ucPCFooter$btnForward']")

            # -------------------------
            # 表示設定
            # -------------------------
            page.locator("input[name='ucPCFooter$btnForward']").click()
            page.wait_for_selector("input[name='rbCalendar']")

            page.locator("input[name='rbCalendar'][value='カレンダー']").click()
            page.locator("input[name='rbtnMonth'][value='1ヶ月']").click()

            page.locator("input[name='ucPCFooter$btnForward']").click()
            page.wait_for_selector("text=体育館")

            # =========================
            # 4月
            # =========================
            select_date(page, 2026, 4, 1)

            log("📑 4月")
            body_apr = page.inner_text("body")
            res_apr = parse(extract_gym(body_apr))
            analyze(body_apr, res_apr, "4月")

            # =========================
            # 5月
            # =========================
            select_date(page, 2026, 5, 1)

            log("📑 5月")
            body_may = page.inner_text("body")
            res_may = parse(extract_gym(body_may))
            analyze(body_may, res_may, "5月")

            # =========================
            # 結果
            # =========================
            final = sorted(set(res_apr + res_may))
            log(f"📦 FINAL: {final}")

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ\n"
                msg += "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send_discord(msg)

        except Exception as e:
            log(f"🔥 エラー: {e}")

        finally:
            browser.close()
            log("🔒 終了")

if __name__ == "__main__":
    run_check()
