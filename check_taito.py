import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v7.4-wait-fix-final"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def send(msg):
    log(f"送信内容:\n{msg}")
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg})
        except Exception as e:
            log(f"❌ Webhook送信失敗: {e}")

# =========================
# 解析（aタグ主体）
# =========================
def parse(page):
    results = []

    # --- aタグ優先 ---
    links = page.locator("a[id*='lnkKoma']").all()

    for l in links:
        try:
            txt = l.inner_text()
            txt = txt.replace("\xa0", "").replace(" ", "").strip()
        except:
            continue

        m = re.search(r"(\d+)(○|△|×)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    # --- fallback ---
    if not results:
        log("⚠️ aタグ取得失敗 → hidden fallback")

        elems = page.locator("input[name*='lnkKoma']").all()
        for e in elems:
            txt = e.get_attribute("value") or ""
            txt = txt.replace("&nbsp;", "").strip()

            m = re.search(r"(\d+)\s*(○|△|×)", txt)
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

    log(f"{label}: EMPTY")
    return "EMPTY"

# =========================
# 次ページ遷移（修正版）
# =========================
def go_next(page):
    log("⏭️ 次ページ")

    before = page.locator("a[id*='lnkKoma']").count()

    target = page.evaluate("""
        () => {
            const el = document.querySelector("input[name*='lnkNextSpan']");
            return el ? el.name.replace("h_", "") : null;
        }
    """)

    if not target:
        log("⚠️ NextSpanなし")
        return False

    log(f"➡ POSTBACK: {target}")

    try:
        page.evaluate(f"__doPostBack('{target}','')")

        # ★ ここが修正ポイント（arg=）
        page.wait_for_function(
            """(args) => {
                const count = document.querySelectorAll("a[id*='lnkKoma']").length;
                return count > 0 && count !== args.before;
            }""",
            arg={"before": before},
            timeout=10000
        )

        page.wait_for_timeout(500)

        log("✅ 2ページ描画完了")
        return True

    except Exception as e:
        log(f"❌ 遷移検知失敗: {e}")
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
            # --- ナビ ---
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

            # ===== 1P =====
            log("📑 1ページ目")
            res1 = parse(page)
            log(f"1P: {res1}")
            analyze(res1, "1P")
            final.extend(res1)

            # ===== 2P =====
            moved = go_next(page)

            if moved:
                log("📑 2ページ目")
                res2 = parse(page)
                log(f"2P: {res2}")
                analyze(res2, "2P")

                if set(res1) != set(res2):
                    final.extend(res2)
                else:
                    log("⚠️ 同一データ → 遷移失敗")
            else:
                log("⚠️ 2ページ取得失敗")

            # ===== 集約 =====
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            # ===== 通知 =====
            if any("○" in x or "△" in x for x in final_unique):
                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(final_unique)}件\n"
                    f"```\n" + "\n".join(final_unique) + "\n```"
                )
            else:
                msg = (
                    f"🏸 空きなし [{VERSION}]\n"
                    f"{datetime.datetime.now().strftime('%m/%d %H:%M')}"
                )

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            import traceback
            traceback.print_exc()
            send(f"⚠️ エラー [{VERSION}]\n{e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
