import os
import requests
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


def send(msg):
    print(msg)
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


def scan(page):
    results = []

    links = page.locator("a[id*='lnkKoma']").all()
    for l in links:
        try:
            txt = l.inner_text().replace("\xa0", "").strip()
        except:
            continue

        import re
        m = re.search(r"(\d+)(○|△|×|抽選)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    return results


def full_flow(page):
    page.goto(BASE_URL)

    page.locator("input[value='公共施設予約メニュー']").click()
    page.locator("input[value^='1. 空き照会']").click()
    page.locator("input[value='次頁']").click()
    page.locator("input[value*='柳北']").first.click()

    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.locator("input[value='カレンダー']").click()
    page.locator("input[value='1ヶ月']").click()

    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.wait_for_timeout(2000)

    return page


def next_available(page):
    body = page.inner_text("body")

    # ★重要：次期間存在チェック
    if "次の期間を表示" not in body and "btnNextPeriod" not in body:
        return False

    btn = page.locator("#btnNextPeriod")
    return btn.count() > 0


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        try:
            # =====================
            # CURRENT
            # =====================
            page1 = browser.new_page()
            print("=== CURRENT ===")

            page1 = full_flow(page1)
            current = scan(page1)
            print(f"[SCAN] CURRENT: {len(current)}件")
            page1.close()

            # =====================
            # NEXT
            # =====================
            page2 = browser.new_page()
            print("=== NEXT ===")

            page2 = full_flow(page2)

            if next_available(page2):
                print("⏭️ 次期間あり → クリック")

                page2.locator("#btnNextPeriod").click()
                page2.wait_for_timeout(3000)

                next_data = scan(page2)
                print(f"[SCAN] NEXT: {len(next_data)}件")

            else:
                print("⏭️ 次期間なし → スキップ")
                next_data = []

            page2.close()

            # =====================
            # 集約
            # =====================
            final = sorted(
                list(set(current + next_data)),
                key=lambda x: int("".join([c for c in x if c.isdigit()]))
            )

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ 空き情報\n" + "\n".join(final)
            else:
                msg = "空きなし"

            send(msg)

        finally:
            browser.close()


if __name__ == "__main__":
    run()
