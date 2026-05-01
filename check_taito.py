import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v7.18-single-page-safe"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


# =========================
# log
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


def send(msg):
    log(f"送信内容:\n{msg}")
    if WEBHOOK_URL:
        try:
            requests.post(WEBHOOK_URL, json={"content": msg})
        except Exception as e:
            log(f"❌ Webhook失敗: {e}")


# =========================
# parse
# =========================
def parse(page):
    results = []

    for a in page.locator("a[id*='lnkKoma']").all():
        try:
            txt = a.inner_text().replace("\xa0", "").replace(" ", "").strip()
            m = re.search(r"(\d+)(○|△|×)", txt)
            if m:
                results.append(f"{m.group(1)}{m.group(2)}")
        except:
            pass

    return results


def analyze(results, label):
    ok = [r for r in results if "○" in r or "△" in r]
    ng = [r for r in results if "×" in r]
    log(f"{label}: ○△={len(ok)} / ×={len(ng)}")


# =========================
# 次ページ（存在チェック型）
# =========================
def go_next(page):
    log("⏭️ 次ページ判定")

    target = page.evaluate("""
        () => {
            const el = document.querySelector("input[name*='lnkNextSpan']");
            return el ? el.name.replace("h_", "") : null;
        }
    """)

    # ★ここがv7.18の核心
    if not target:
        log("➡ 2ページ目なし（月末状態）")
        return False

    log(f"➡ POSTBACK: {target}")

    try:
        page.evaluate(f"__doPostBack('{target}','')")

        # ★検知しない、固定待機のみ
        page.wait_for_timeout(2500)

        log("✅ 遷移試行完了")
        return True

    except Exception as e:
        log(f"❌ 遷移失敗: {e}")
        return False


# =========================
# main
# =========================
def run():
    with sync_playwright() as p:
        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        final = []

        try:
            page.goto(BASE_URL)

            # 初期操作
            page.locator("input[value='公共施設予約メニュー']").click()
            page.locator("input[value^='1. 空き照会']").click()
            page.locator("input[value='次頁']").click()
            page.locator("input[value='柳北スポーツプラザ']").click()
            page.locator("input[name='ucPCFooter$btnForward']").click()

            page.locator("input[value='カレンダー']").click()
            page.locator("input[value='1ヶ月']").click()
            page.locator("input[name='ucPCFooter$btnForward']").click()

            page.wait_for_load_state("networkidle")

            # =====================
            # 1P
            # =====================
            log("📑 1ページ目")
            res1 = parse(page)
            log(f"1P: {res1}")
            analyze(res1, "1P")
            final.extend(res1)

            # =====================
            # 2P（あれば）
            # =====================
            if go_next(page):
                log("📑 2ページ目（存在）")

                # 念のため再取得
                res2 = parse(page)
                log(f"2P: {res2}")
                analyze(res2, "2P")
                final.extend(res2)

            # =====================
            # 集約
            # =====================
            final_unique = sorted(
                set(final),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            # =====================
            # 通知
            # =====================
            if any("○" in x or "△" in x for x in final_unique):
                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(final_unique)}件\n"
                    f"```\n" + "\n".join(final_unique) + "\n```"
                )
            else:
                msg = f"🏸 空きなし [{VERSION}]"

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
