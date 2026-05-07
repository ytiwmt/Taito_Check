import requests
import os
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

        # 例: "11△", "3抽選", "10×"
        import re
        m = re.search(r"(\d+)(○|△|×|抽選)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    return results


def run_once(page, use_next=False):
    page.goto(BASE_URL)

    # ===== フルフロー（毎回リセット）=====
    page.locator("input[value='公共施設予約メニュー']").click()
    page.locator("input[value^='1. 空き照会']").click()
    page.locator("input[value='次頁']").click()
    page.locator("input[value*='柳北']").first.click()
    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.locator("input[value='カレンダー']").click()
    page.locator("input[value='1ヶ月']").click()
    page.locator("input[name='ucPCFooter$btnForward']").click()

    page.wait_for_timeout(2000)

    # ===== 1ページ目 =====
    res = scan(page)
    print(f"[SCAN] 1P: {len(res)}件")

    # ===== 次期間（必要な場合のみ）=====
    if use_next:
        btn = page.locator("#btnNextPeriod")
        if btn.count() > 0:
            btn.click()
            page.wait_for_timeout(2500)

            res2 = scan(page)
            print(f"[SCAN] 2P: {len(res2)}件")
            res += res2

    return res


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # ① 現在月
            print("=== CURRENT ===")
            current = run_once(page, use_next=False)

            # ② 次期間（完全リセットして再実行）
            print("=== NEXT ===")
            next_data = run_once(page, use_next=True)

            final = sorted(set(current + next_data), key=lambda x: int("".join(filter(str.isdigit, x))))

            if final:
                msg = "@everyone\n🏸 柳北スポーツプラザ 空き情報\n" + "\n".join(final)
            else:
                msg = "空きなし"

            send(msg)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
