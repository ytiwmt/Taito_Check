import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v6.5-dual-parse-final"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# 完全パース（hidden + fallback）
# =========================
def parse_all(page):
    results = []

    # --- ① hidden ---
    elems = page.locator("input[name^='h_dlRepeat2']").all()

    for e in elems:
        txt = e.get_attribute("value") or ""
        txt = txt.replace("&nbsp;", "").strip()

        m = re.search(r"(\d+).*(○|△|×)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    if results:
        return results

    # --- ② fallback（×ページ対応） ---
    log("⚠️ hidden空 → DOM解析fallback")

    text = page.inner_text("body")
    matches = re.findall(r"(\d+)\s*(○|△|×)", text)

    return [f"{d}{s}" for d, s in matches]


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
# 次ページ遷移
# =========================
def go_next(page):
    log("⏭️ 次ページ")

    target = page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll("input[name^='h_dlRepeat2']"));
            for (const el of inputs) {
                if (el.name.includes("Migrated_lnkNextSpan")) {
                    return el.name.replace("h_", "");
                }
            }
            return null;
        }
    """)

    if not target:
        raise Exception("NextSpan target not found")

    log(f"➡ POSTBACK TARGET: {target}")

    page.evaluate(f"__doPostBack('{target}','')")

    # --- 更新待ち（柔軟）
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except:
        pass

    page.wait_for_timeout(1000)


# =========================
# メイン
# =========================
def run():
    with sync_playwright() as p:
        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # --- 初期遷移 ---
            page.goto(BASE_URL)

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

            res1 = parse_all(page)
            log(f"1P: {res1}")
            analyze(res1, "1P")

            # =========================
            # 2ページ
            # =========================
            try:
                go_next(page)

                log("📑 2ページ目")

                res2 = parse_all(page)
                log(f"2P: {res2}")
                analyze(res2, "2P")

            except Exception as e:
                log(f"⚠️ 2ページ取得失敗: {e}")
                res2 = []

            # =========================
            # 集約
            # =========================
            final = sorted(set(res1 + res2))
            log(f"📦 FINAL: {final}")

            # =========================
            # 通知（Ver付き）
            # =========================
            if any("○" in x or "△" in x for x in final):
                msg = f"@everyone\n🏸 空きあり ({VERSION})\n" + "\n".join(final)
            else:
                msg = f"🏸 空きなし ({VERSION})"

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            import traceback
            traceback.print_exc()

            # --- 最低限通知（落ちても送る） ---
            send(f"⚠️ ERROR ({VERSION})\n{e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
