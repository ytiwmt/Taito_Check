import os
import re
import time
import datetime
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

VERSION = "stable-v1"

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if not WEBHOOK_URL_Taito:
        log("Webhookなし")
        return
    requests.post(WEBHOOK_URL_Taito, json={"content": msg})


# -------------------------
# 重要：リンクから抽出
# -------------------------
def extract_slots(page):
    results = []

    links = page.locator("a")
    count = links.count()

    for i in range(count):
        try:
            text = links.nth(i).inner_text().strip()

            # 例: 11選択△ / 28× / 14○
            m = re.search(r'(\d{1,2}).*(○|△|×)', text)
            if m:
                results.append(f"{m.group(1)}{m.group(2)}")

        except:
            continue

    return results


def classify(results):
    if results is None:
        return "PARSE_FAILED"

    if len(results) == 0:
        return "PARSE_FAILED"

    ok = [r for r in results if "○" in r or "△" in r]
    ng = [r for r in results if "×" in r]

    if ok:
        return "AVAILABLE"

    if ng and not ok:
        return "EMPTY_OK"

    return "PARSE_FAILED"


# -------------------------
# Ajax待機（重要）
# -------------------------
def wait_update(page):
    try:
        page.wait_for_timeout(1200)  # このサイトはこれが一番安定
    except:
        pass


def run():
    with sync_playwright() as p:
        log(f"🚀 Playwright {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            log(f"🔗 {URL}")
            page.goto(URL)

            page.wait_for_url("**Wg_ModeSelect.aspx**")

            # -------------------------
            # 画面遷移
            # -------------------------
            page.click("input[value='公共施設予約メニュー']")
            page.click("input[value^='1. 空き照会']")
            page.click("input[value='次頁']")
            page.click("input[value='柳北スポーツプラザ']")

            page.click("input[name='ucPCFooter$btnForward']")

            page.click("input[name='rbCalendar'][value='カレンダー']")
            page.click("input[name='rbtnMonth'][value='1ヶ月']")
            page.click("input[name='ucPCFooter$btnForward']")

            wait_update(page)

            # -------------------------
            # 1ページ目
            # -------------------------
            log("📑 1ページ目")
            res1 = extract_slots(page)
            log(f"1ページ: {res1}")

            status1 = classify(res1)
            log(f"1ページ STATUS: {status1}")

            # -------------------------
            # 次ページ
            # -------------------------
            log("⏭️ 次の期間")

            page.evaluate("""
                document.getElementById('btnNextPeriod').click()
            """)

            # Ajax待ち（ここ超重要）
            wait_update(page)

            # -------------------------
            # 2ページ目
            # -------------------------
            log("📑 2ページ目")

            res2 = extract_slots(page)
            log(f"2ページ: {res2}")

            status2 = classify(res2)
            log(f"2ページ STATUS: {status2}")

            # -------------------------
            # 結果
            # -------------------------
            final = sorted(set(res1 + res2))

            log(f"📦 FINAL: {final}")

            if final:
                send("🏸 空きあり\n" + "\n".join(final))
            else:
                send("空きなし")

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            import traceback
            traceback.print_exc()

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
