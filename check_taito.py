import requests
import os
import re
import time
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v8-stable-dom-rebuild"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# =========================
# LOG
# =========================
def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


# =========================
# DISCORD
# =========================
def send(msg):
    log(f"送信内容:\n{msg}")

    if not WEBHOOK_URL:
        return

    try:
        requests.post(WEBHOOK_URL, json={"content": msg}, timeout=10)
    except Exception as e:
        log(f"Webhook失敗: {e}")


# =========================
# PARSE
# =========================
def parse(page, label):
    links = page.locator("a[id*='lnkKoma']").all()

    log(f"[{label}] link数: {len(links)}")

    results = []

    for l in links:
        try:
            txt = l.inner_text()
            txt = txt.replace("\xa0", "").replace(" ", "").strip()

            m = re.search(r"(\d+)(○|△|×|抽選)", txt)
            if m:
                results.append(f"{m.group(1)}{m.group(2)}")

        except:
            pass

    log(f"[{label}] 抽出件数: {len(results)}")

    return results


# =========================
# WAIT TABLE READY
# =========================
def wait_table(page):
    page.wait_for_selector("text=体育館", timeout=20000)

    page.wait_for_function("""
        () => {
            const links = document.querySelectorAll("a[id*='lnkKoma']");
            return links && links.length > 10;
        }
    """, timeout=20000)


# =========================
# PAGE FLOW
# =========================
def open_base(page):

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    page.get_by_role("button", name="公共施設予約メニュー").click()
    page.wait_for_timeout(1500)

    page.get_by_role("button", name="空き照会").click()
    page.wait_for_timeout(1500)

    page.get_by_role("button", name="次頁").click()
    page.wait_for_timeout(2000)

    page.get_by_text("柳北").first.click()
    page.wait_for_timeout(2000)

    page.locator("input[name='ucPCFooter$btnForward']").click()
    page.wait_for_timeout(2000)

    page.get_by_text("カレンダー").first.click()
    page.wait_for_timeout(2000)

    page.get_by_text("1ヶ月").first.click()
    page.wait_for_timeout(2000)

    page.locator("input[name='ucPCFooter$btnForward']").click()
    page.wait_for_timeout(3000)

    wait_table(page)


# =========================
# NEXT PERIOD SAFE
# =========================
def go_next(page):

    log("⏭️ 次期間")

    before = page.locator("a[id*='lnkKoma']").count()
    log(f"遷移前: {before}")

    page.locator("#btnNextPeriod").click()

    try:
        page.wait_for_function(
            """(prev) => {
                const links = document.querySelectorAll("a[id*='lnkKoma']");
                return links.length !== prev && links.length > 0;
            }""",
            arg=before,
            timeout=20000
        )

        after = page.locator("a[id*='lnkKoma']").count()
        log(f"遷移後: {after}")

        return True

    except:

        body = page.inner_text("body")[:400]
        log(f"❌ 遷移失敗BODY:\n{body}")

        return False


# =========================
# MAIN
# =========================
def run():

    with sync_playwright() as p:

        log(f"🚀 {VERSION}")

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        page = browser.new_page()
        final = []

        try:

            open_base(page)

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")
            res1 = parse(page, "1P")
            final.extend(res1)

            # =========================
            # 2ページ
            # =========================
            if go_next(page):

                wait_table(page)

                log("📑 2ページ目")
                res2 = parse(page, "2P")
                final.extend(res2)

            else:
                log("⚠️ 次期間なし")

            # =========================
            # FINAL
            # =========================
            final = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final}")

            if any(("○" in x or "△" in x) for x in final):

                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(final)}件\n"
                    f"```\n" + "\n".join(final) + "\n```"
                )

            else:
                msg = f"🏸 空きなし [{VERSION}]"

            send(msg)

        except Exception as e:
            log(f"🔥 ERROR: {e}")
            send(f"⚠️ エラー [{VERSION}]\n{e}")

        finally:
            browser.close()
            log("🔒 END")


if __name__ == "__main__":
    run()
