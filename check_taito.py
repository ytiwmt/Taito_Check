import requests
import os
from playwright.sync_api import sync_playwright

WEBHOOK_URL_Taito = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

def log(msg):
    print(msg, flush=True)

def send_discord(message):
    if not WEBHOOK_URL_Taito:
        log("【Webhook未設定】")
        log(message)
        return
    try:
        requests.post(WEBHOOK_URL_Taito, json={"content": message}, timeout=10)
    except Exception as e:
        log(f"送信エラー: {e}")

def get_table_signature(page):
    """ページが変わったか判定するための署名"""
    try:
        text = page.locator("table").first.inner_text()
        return hash(text)
    except:
        return None

def scan_vacancy(page, label):
    log(f"--- {label} スキャン開始 ---")

    tables = page.locator("table").all()
    results = []

    for i, tbl in enumerate(tables):
        try:
            txt = tbl.inner_text()
        except:
            continue

        if "体育館" not in txt:
            continue

        log(f"[{label}] 対象テーブル検出 index={i}")

        for cell in tbl.locator("td").all():
            try:
                t = cell.inner_text().strip()
            except:
                continue

            if t in ["○", "△"]:
                row = cell.locator("xpath=..").inner_text()
                row = " ".join(row.split())
                results.append(row)

    log(f"[{label}] 件数: {len(results)}")
    return results


def navigate_base(page):
    """共通遷移"""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    page.locator("input[type='submit']", has_text="公共施設予約メニュー").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[type='submit']", has_text="空き照会").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[type='submit']", has_text="次頁").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    page.locator("input[type='submit']", has_text="柳北").first.wait_for(timeout=30000)
    page.locator("input[type='submit']", has_text="柳北").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[name='ucPCFooter$btnForward']").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[type='submit']", has_text="カレンダー").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[type='submit']", has_text="1ヶ月").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    page.locator("input[name='ucPCFooter$btnForward']").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)

    page.locator("span:has-text('体育館')").first.wait_for(timeout=20000)
    page.locator("span:has-text('体育館')").first.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(3000)


def run_check():
    headless = os.getenv("GITHUB_ACTIONS") == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        try:
            log("=== 1周目（現在月）===")
            navigate_base(page)

            sig1 = get_table_signature(page)
            log(f"1ページ署名: {sig1}")

            res1 = scan_vacancy(page, "1P")

            # -------------------------
            # 2周目（次期間）
            # -------------------------
            log("=== 次期間ボタン押下 ===")

            btn = page.locator("#btnNextPeriod")
            if btn.count() == 0:
                log("❌ btnNextPeriodが見つからない")
            else:
                btn.first.click()
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(3000)

                sig2 = get_table_signature(page)
                log(f"2ページ署名: {sig2}")

                if sig1 == sig2:
                    log("⚠️ ページ変化なし（＝遷移失敗）")
                else:
                    log("✅ ページ変化あり（遷移成功）")

                res2 = scan_vacancy(page, "2P")
                res1.extend(res2)

            # -------------------------
            # 結果
            # -------------------------
            final = list(dict.fromkeys(res1))

            log(f"最終件数: {len(final)}")

            if final:
                msg = "🏸 空きあり\n\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send_discord(msg)

        except Exception as e:
            log(f"エラー: {e}")
            page.screenshot(path="error.png", full_page=True)

        finally:
            browser.close()


if __name__ == "__main__":
    run_check()
