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
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            print("システムにアクセス中...")
            page.goto(BASE_URL, wait_until="networkidle")

            # 公共施設予約メニュー
            page.locator("input[type='submit'][value='公共施設予約メニュー']").first.wait_for(state="visible", timeout=20000)
            page.locator("input[type='submit'][value='公共施設予約メニュー']").first.click()
            page.wait_for_load_state("networkidle")

            # 空き照会
            page.locator("input[type='submit'][value^='1. 空き照会']").first.wait_for(state="visible", timeout=20000)
            page.locator("input[type='submit'][value^='1. 空き照会']").first.click()
            page.wait_for_load_state("networkidle")

            # 次頁
            page.locator("input[type='submit'][value='次頁']").first.wait_for(state="visible", timeout=15000)
            page.locator("input[type='submit'][value='次頁']").first.click()
            page.wait_for_load_state("networkidle")

            # 柳北スポーツプラザ
            page.locator("input[type='submit'][value='柳北スポーツプラザ']").first.wait_for(state="visible", timeout=20000)
            page.locator("input[type='submit'][value='柳北スポーツプラザ']").first.click()
            page.wait_for_load_state("networkidle")

            # 次へ
            page.locator("input[name='ucPCFooter$btnForward']").first.wait_for(state="visible", timeout=15000)
            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")

            # カレンダー表示
            page.locator("input[name='rbCalendar'][value='カレンダー']").first.wait_for(state="visible", timeout=15000)
            page.locator("input[name='rbCalendar'][value='カレンダー']").first.click()
            page.wait_for_load_state("networkidle")

            # 1ヶ月表示
            page.locator("input[name='rbtnMonth'][value='1ヶ月']").first.wait_for(state="visible", timeout=15000)
            page.locator("input[name='rbtnMonth'][value='1ヶ月']").first.click()
            page.wait_for_load_state("networkidle")

            # 次へ
            page.locator("input[name='ucPCFooter$btnForward']").first.wait_for(state="visible", timeout=15000)
            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")

            # 体育館選択
            page.locator("span:has-text('体育館')").first.wait_for(state="visible", timeout=15000)
            page.locator("span:has-text('体育館')").first.click()
            page.wait_for_load_state("networkidle")
            print("体育館を選択しました。")

            all_vacant_info = []

            # --- 空き取得 ---
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

            # 現在期間
            print("空き状況をスキャン中（現在期間）...")
            scan_vacancy()

            # 次期間
            next_period = page.locator("a:has-text('次の期間を表示 >')")
            if next_period.count() > 0:
                next_period.first.click()
                page.wait_for_load_state("networkidle")
                print("次の期間に移動しました。")
                print("空き状況をスキャン中（次の期間）...")
                scan_vacancy()

            # --- メッセージ作成 ---
            if all_vacant_info:
                body = "\n".join(list(dict.fromkeys(all_vacant_info)))

                # 2000文字対策
                if len(body) > 1800:
                    body = body[:1800] + "\n...(省略)"

                msg = "🏸 **柳北スポーツプラザ 体育館 空き情報**\n\n" + body
            else:
                msg = "🏸 **柳北スポーツプラザ 体育館 空き情報**\n\n空きはありません。"

            send_discord(msg)
            print("空き状況を Discord に送信しました。")

        except Exception as e:
            page.screenshot(path="debug_error.png")
            print(f"エラー発生: {e}")
            print("debug_error.png にスクリーンショットを保存しました。")

        finally:
            browser.close()


if __name__ == "__main__":
    run_check()