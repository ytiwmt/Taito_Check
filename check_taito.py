import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v6.0-postback-fix"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# hidden input解析（最重要）
# =========================
def parse_hidden(page):
    vals = page.locator("input[id*='lnkKoma']").all()

    results = []
    for v in vals:
        txt = v.get_attribute("value") or ""
        txt = txt.replace("&nbsp;", "").strip()

        m = re.search(r"(\d+).*(○|△|×)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    return results


# =========================
# 状態判定
# =========================
def analyze(results, label):
    maru = [r for r in results if "○" in r or "△" in r]
    batsu = [r for r in results if "×" in r]

    if maru:
        log(f"{label}: AVAILABLE / ○△={len(maru)} / ×={len(batsu)}")
        return "AVAILABLE"

    if batsu:
        log(f"{label}: FULL / ×={len(batsu)}")
        return "FULL"

    log(f"{label}: PARSE_FAILED")
    return "PARSE_FAILED"


# =========================
# 次ページ遷移（核心）
# =========================
def go_next(page):
    log("⏭️ 次ページ")

    with page.expect_response(
        lambda r: "Wg_ShisetsubetsuAkiJoukyou" in r.url,
        timeout=10000
    ):
        page.evaluate("""
            __doPostBack('dlRepeat2$ctl01$tpItem2$lnkNextSpan','')
        """)

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)


# =========================
# メイン
# =========================
def run():
    with sync_playwright() as p:
        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(BASE_URL)

            # --- 遷移 ---
            page.locator("input[value='公共施設予約メニュー']").click()
            page.locator("input[value^='1. 空き照会']").click()
            page.locator("input[value='次頁']").click()
            page.locator("input[value='柳北スポーツプラザ']").click()
            page.locator("input[name='ucPCFooter$btnForward']").click()

            page.locator("input[value='カレンダー']").click()
            page.locator("input[value='1ヶ月']").click()
            page.locator("input[name='ucPCFooter$btnForward']").click()

            page.wait_for_load_state("networkidle")

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")

            res1 = parse_hidden(page)
            log(f"1P: {res1}")
            analyze(res1, "1P")

            # =========================
            # 2ページ
            # =========================
            go_next(page)

            log("📑 2ページ目")

            res2 = parse_hidden(page)
            log(f"2P: {res2}")
            analyze(res2, "2P")

            # =========================
            # 集約
            # =========================
            final = sorted(set(res1 + res2))
            log(f"📦 FINAL: {final}")

            if any("○" in x or "△" in x for x in final):
                msg = "@everyone\n🏸 空きあり\n" + "\n".join(final)
            else:
                msg = "🏸 空きなし"

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
