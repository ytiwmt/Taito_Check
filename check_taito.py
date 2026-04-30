import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v6.8-page-detect-final"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    if WEBHOOK_URL:
        requests.post(WEBHOOK_URL, json={"content": msg})


# =========================
# KOMAパース（存在するものだけ取る）
# =========================
def parse_koma(page):
    elems = page.locator("input[name*='lnkKoma']").all()

    results = []
    for e in elems:
        txt = e.get_attribute("value") or ""
        txt = txt.replace("&nbsp;", "").strip()

        m = re.search(r"(\d+)\s*(○|△|×)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    return results


# =========================
# 状態判定（空配列も正常扱い）
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

    # ★ここが重要（2ページ目対策）
    log(f"{label}: FULL (データなし)")
    return "FULL"


# =========================
# 次ページ遷移（ページ変化検知）
# =========================
def go_next(page):
    log("⏭️ 次ページ")

    before = page.content()

    target = page.evaluate("""
        () => {
            const inputs = Array.from(document.querySelectorAll("input[name*='lnkNextSpan']"));
            for (const el of inputs) {
                return el.name.replace("h_", "");
            }
            return null;
        }
    """)

    if not target:
        log("⚠️ 次ページなし")
        return False

    log(f"➡ POSTBACK TARGET: {target}")

    try:
        page.evaluate(f"__doPostBack('{target}','')")

        # ★DOM変化ベースで待つ（KOMA依存しない）
        page.wait_for_function(
            """(prev) => document.body.innerHTML !== prev""",
            before,
            timeout=10000
        )

        log("✅ ページ変化検知")
        return True

    except:
        log("⚠️ ページ変化検知失敗")
        return False


# =========================
# メイン
# =========================
def run():
    with sync_playwright() as p:
        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        final = []

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
            # 1ページ目
            # =========================
            log("📑 1ページ目")

            res1 = parse_koma(page)
            log(f"1P: {res1}")
            analyze(res1, "1P")

            final += res1

            # =========================
            # 2ページ目
            # =========================
            if go_next(page):
                log("📑 2ページ目")

                res2 = parse_koma(page)
                log(f"2P: {res2}")
                analyze(res2, "2P")

                final += res2
            else:
                log("⚠️ 2ページ目スキップ")

            # =========================
            # 集約
            # =========================
            final = sorted(set(final))
            log(f"📦 FINAL: {final}")

            # =========================
            # 通知（必ず送る）
            # =========================
            if any("○" in x or "△" in x for x in final):
                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり\n"
                    f"Ver: {VERSION}\n"
                    + "\n".join(final)
                )
            else:
                msg = f"🏸 空きなし\nVer: {VERSION}"

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            import traceback
            traceback.print_exc()

            send(f"⚠️ ERROR\nVer: {VERSION}\n{e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
