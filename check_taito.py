import requests
from playwright.sync_api import sync_playwright
import os
import datetime

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"
WEBHOOK = os.getenv("WEBHOOK_URL_Taito")


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def run():
    log("🚀 MINIMAL STABLE MODE")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(URL, wait_until="domcontentloaded")

            # ★ここだけ待つ（他は全部捨てる）
            page.wait_for_selector("input", timeout=30000)

            # 固定クリック（存在ベース）
            page.locator("input[value='公共施設予約メニュー']").first.click()

            page.wait_for_timeout(2000)

            page.locator("input[name='rbtnYoyaku']").first.click()
            page.wait_for_timeout(2000)

            page.locator("input[value='次頁']").first.click()
            page.wait_for_timeout(2000)

            page.locator("input[value='柳北スポーツプラザ']").first.click()
            page.wait_for_timeout(2000)

            page.locator("input[name='rbCalendar'][value='カレンダー']").first.click()
            page.locator("input[name='rbtnMonth'][value='1ヶ月']").first.click()

            page.locator("input[name='ucPCFooter$btnForward']").first.click()

            page.wait_for_timeout(3000)

            body = page.inner_text("body")

            log("📦 取得完了（ここまで到達できるか確認）")

            if WEBHOOK:
                requests.post(WEBHOOK, json={"content": "取得成功"})

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            browser.close()
            log("🔒 END")


if __name__ == "__main__":
    run()
