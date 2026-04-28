import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v4.1-stable"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL_Taito:
        log(f"通知設定なし: {msg}")
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})


# =========================
# 解析ロジック
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
        log(f"{label}: ❌ 不正遷移")
        return "error"

    if not results:
        log(f"{label}: 🟡 空きなし")
        return "empty"

    log(f"{label}: 🟢 空きあり -> {results}")
    return "ok"


# =========================
# 安全クリック
# =========================
def safe_click(page, selector):
    el = page.locator(selector).first
    el.wait_for(state="attached", timeout=20000)
    el.click()
    page.wait_for_timeout(1200)


# =========================
# JSクリック（安定版）
# =========================
def js_click(page, element_id):
    page.evaluate(f"""
        const el = document.getElementById('{element_id}');
        if (el) el.click();
    """)


# =========================
# メイン
# =========================
def run_check():
    with sync_playwright() as p:
        log(f"🚀 Playwright {VERSION}")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            log(f"🔗 アクセス: {BASE_URL}")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # -------------------------
            # 遷移
            # -------------------------
            safe_click(page, "input[value='公共施設予約メニュー']")
            safe_click(page, "input[name='rbtnYoyaku']")
            safe_click(page, "input[value='次頁']")
            safe_click(page, "input[value='柳北スポーツプラザ']")

            safe_click(page, "input[name='ucPCFooter$btnForward']")
            safe_click(page, "input[name='rbCalendar'][value='カレンダー']")
            safe_click(page, "input[name='rbtnMonth'][value='1ヶ月']")
            safe_click(page, "input[name='ucPCFooter$btnForward']")

            page.wait_for_timeout(1500)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")
            body1 = page.inner_text("body")
            res1 = parse(extract_gym(body1))
            analyze(body1, res1, "1ページ")

            # =========================
            # 次ページ（安定版）
            # =========================
            log("⏭️ 次の期間")

            js_click(page, "btnNextPeriod")
            page.wait_for_timeout(2000)

            # =========================
            # 2ページ
            # =========================
            log("📑 2ページ目")
            body2 = page.inner_text("body")
            res2 = parse(extract_gym(body2))
            analyze(body2, res2, "2ページ")

            # =========================
            # 結果
            # =========================
            final = sorted(set(res1 + res2))
            log(f"📦 FINAL: {final}")

            send_discord("\n".join(final) if final else "空きなし")

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 終了")
            browser.close()


if __name__ == "__main__":
    run_check()
