import os
import re
import time
import requests
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v5-stable-state-machine"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


# =========================
# util
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send_discord(msg):
    if not WEBHOOK_URL_Taito:
        log("WEBHOOKなし")
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})


# =========================
# 状態解析（ここが本体）
# =========================
def parse_koma(page):
    cells = page.locator("a[id*='lnkKoma']")
    count = cells.count()

    if count == 0:
        return {
            "status": "PARSE_FAILED",
            "available": [],
            "empty": [],
            "raw": []
        }

    texts = cells.all_text_contents()

    available = []
    empty = []
    unknown = []

    for t in texts:
        t = t.replace("\xa0", "").strip()

        if t == "":
            continue

        if "○" in t or "△" in t:
            available.append(t)
        elif "×" in t:
            empty.append(t)
        else:
            unknown.append(t)

    # 判定
    if available:
        status = "AVAILABLE"
    elif empty and not available:
        status = "EMPTY_CONFIRMED"
    elif unknown:
        status = "UNKNOWN_FORMAT"
    else:
        status = "EMPTY_CONFIRMED"

    return {
        "status": status,
        "available": available,
        "empty": empty,
        "raw": texts
    }


# =========================
# 安定クリック
# =========================
def safe_click(page, selector, label):
    try:
        page.locator(selector).first.click()
        log(f"➡ {label}")
        page.wait_for_timeout(800)
    except Exception as e:
        log(f"🔥 click失敗 {label}: {e}")


# =========================
# メイン
# =========================
def run():
    with sync_playwright() as p:
        log(f"🚀 Playwright {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            log(f"🔗 {BASE_URL}")
            page.goto(BASE_URL, timeout=30000)

            # 初期遷移（最低限）
            safe_click(page, "input[value='公共施設予約メニュー']", "公共施設予約メニュー")
            safe_click(page, "input[value^='1. 空き照会']", "空き照会")
            safe_click(page, "input[value='次頁']", "次頁")

            # 施設選択（固定）
            safe_click(page, "input[value='柳北スポーツプラザ']", "施設")
            safe_click(page, "input[name='ucPCFooter$btnForward']", "進む")

            # カレンダー
            safe_click(page, "input[name='rbCalendar'][value='カレンダー']", "カレンダー")
            safe_click(page, "input[name='rbtnMonth'][value='1ヶ月']", "1ヶ月")
            safe_click(page, "input[name='ucPCFooter$btnForward']", "確定")

            page.wait_for_timeout(1500)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")
            r1 = parse_koma(page)

            log(f"1ページ: {r1['status']} / ○△={len(r1['available'])} / ×={len(r1['empty'])}")

            # =========================
            # 次ページ
            # =========================
            log("⏭️ 次の期間")
            try:
                page.locator("#btnNextPeriod").click()
            except:
                page.evaluate("__doPostBack('btnNextPeriod','')")

            page.wait_for_timeout(2000)

            # =========================
            # 2ページ
            # =========================
            log("📑 2ページ目")
            r2 = parse_koma(page)

            log(f"2ページ: {r2['status']} / ○△={len(r2['available'])} / ×={len(r2['empty'])}")

            # =========================
            # 結果統合
            # =========================
            all_ok = r1["available"] + r2["available"]

            if all_ok:
                msg = "@everyone\n🏸 空きあり\n"
                msg += "\n".join(all_ok)
            else:
                if r1["status"] == "PARSE_FAILED" or r2["status"] == "PARSE_FAILED":
                    msg = "⚠️ 取得失敗（ページ構造変化の可能性）"
                else:
                    msg = "🏸 空きなし（正常判定）"

            log(f"📦 FINAL: {all_ok}")
            send_discord(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
