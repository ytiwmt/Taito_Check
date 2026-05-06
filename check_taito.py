import requests
import os
import re
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


def log(msg):
    print(msg, flush=True)


def send(msg):
    log("送信内容:\n" + msg)
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg}, timeout=10)
        except Exception as e:
            log(f"送信エラー: {e}")


# =========================
# ページ署名（遷移判定）
# =========================
def get_signature(page):
    try:
        txt = page.locator("table").first.inner_text()
        return hash(txt)
    except:
        return None


# =========================
# 抽出（修正版）
# =========================
def parse(page, label):
    log(f"--- {label} 解析開始 ---")

    results = []
    tables = page.locator("table").all()

    for i, tbl in enumerate(tables):
        try:
            t = tbl.inner_text()
        except:
            continue

        if "体育館" not in t:
            continue

        log(f"[{label}] テーブル検出 index={i}")

        for cell in tbl.locator("td").all():
            try:
                txt = cell.inner_text().strip()
            except:
                continue

            # ★ここが重要
            if re.search(r"(○|△)", txt):
                row = cell.locator("xpath=..").inner_text()
                row = " ".join(row.split())
                results.append(row)

    log(f"[{label}] 件数: {len(results)}")
    return results


# =========================
# 共通遷移
# =========================
def navigate(page):
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


# =========================
# 次ページ（POSTBACK確定版）
# =========================
def go_next(page):
    log("⏭️ 次ページ（POSTBACK直叩き）")

    before = get_signature(page)
    log(f"遷移前署名: {before}")

    try:
        page.evaluate("""
            __doPostBack('dlRepeat2$ctl00$tpItem2$Migrated_lnkNextSpan','')
        """)

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        after = get_signature(page)
        log(f"遷移後署名: {after}")

        if after is None:
            log("❌ テーブル取得不可 → 遷移失敗")
            return False

        if before == after:
            log("⚠️ 同一ページ → 遷移失敗")
            return False

        log("✅ 遷移成功")
        return True

    except Exception as e:
        log(f"❌ 遷移例外: {e}")
        return False


# =========================
# メイン
# =========================
def run():
    headless = os.getenv("GITHUB_ACTIONS") == "true"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, args=["--no-sandbox"])
        context = browser.new_context()
        page = context.new_page()

        try:
            log("=== 1ページ目 ===")
            navigate(page)

            res1 = parse(page, "1P")

            # =========================
            # 2ページ目
            # =========================
            if go_next(page):
                res2 = parse(page, "2P")
                res1.extend(res2)
            else:
                log("⚠️ 2ページ取得失敗")

            # =========================
            # 集約
            # =========================
            final = list(dict.fromkeys(res1))
            log(f"📦 FINAL件数: {len(final)}")

            if final:
                msg = "🏸 空きあり\n\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            page.screenshot(path="error.png", full_page=True)

        finally:
            browser.close()


if __name__ == "__main__":
    run()
