import requests
import os
from playwright.sync_api import sync_playwright

# --- 設定 ---
WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

def send_discord(message):
    if not WEBHOOK_URL_Taito:
        print("\n【Webhook未設定】")
        print(message)
        return

    try:
        res = requests.post(
            WEBHOOK_URL_Taito,
            json={"content": message},
            timeout=10
        )
        print(f"Discord status: {res.status_code}")
        if res.status_code != 204:
            print("送信失敗:", res.text)
    except Exception as e:
        print("Discord送信エラー:", e)


def run_check():
    headless = os.getenv("GITHUB_ACTIONS") == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        page = context.new_page()

        try:
            print("システムにアクセス中...")
            page.goto(BASE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 公共施設予約メニュー
            page.locator("input[type='submit']", has_text="公共施設予約メニュー").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 空き照会
            page.locator("input[type='submit']", has_text="空き照会").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 次頁
            page.locator("input[type='submit']", has_text="次頁").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 柳北スポーツプラザ（部分一致）
            print("施設選択待機中...")
            page.locator("input[type='submit']", has_text="柳北").first.wait_for(timeout=30000)
            page.locator("input[type='submit']", has_text="柳北").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 次へ
            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # カレンダー
            page.locator("input[name='rbCalendar']").first.check()
            page.wait_for_timeout(2000)

            # 1ヶ月
            page.locator("input[name='rbtnMonth']").first.check()
            page.wait_for_timeout(2000)

            # 次へ
            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            # 体育館
            page.locator("span:has-text('体育館')").first.wait_for(timeout=20000)
            page.locator("span:has-text('体育館')").first.click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(3000)

            print("体育館を選択しました。")

            all_vacant_info = []

            def scan_vacancy():
                tables = page.locator("table").all()
                for tbl in tables:
                    if "体育館" not in tbl.inner_text():
                        continue
                    for cell in tbl.locator("td").all():
                        text = cell.inner_text().strip()
                        if text in ["○", "△"]:
                            row_text = cell.locator("xpath=..").inner_text()
                            all_vacant_info.append(" ".join(row_text.split()))

            print("空き状況スキャン（現在期間）...")
            scan_vacancy()

            next_period = page.locator("a:has-text('次の期間')")
            if next_period.count() > 0:
                next_period.first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)

                print("空き状況スキャン（次期間）...")
                scan_vacancy()

            # --- メッセージ ---
            if all_vacant_info:
                body = "\n".join(list(dict.fromkeys(all_vacant_info)))

                if len(body) > 1800:
                    body = body[:1800] + "\n...(省略)"

                msg = "🏸 **柳北スポーツプラザ 体育館 空き情報**\n\n" + body
            else:
                msg = "🏸 **柳北スポーツプラザ 体育館 空き情報**\n\n空きはありません。"

            send_discord(msg)
            print("送信完了")

        except Exception as e:
            print(f"エラー発生: {e}")
            page.screenshot(path="debug_error.png", full_page=True)
            print("debug_error.png 保存")

        finally:
            browser.close()


if __name__ == "__main__":
    run_check()
