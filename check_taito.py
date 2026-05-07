import requests
import os
import re
import time
import datetime
from playwright.sync_api import sync_playwright

VERSION = "v7.37-native-click-only"

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
        requests.post(
            WEBHOOK_URL,
            json={"content": msg},
            timeout=15
        )

    except Exception as e:
        log(f"Webhook失敗: {e}")

# =========================
# PARSE
# =========================
def parse(page, label):
    results = []

    links = page.locator("a[id*='lnkKoma']").all()

    log(f"[{label}] link数: {len(links)}")

    for l in links:
        try:
            txt = l.inner_text()

            txt = (
                txt.replace("\xa0", "")
                .replace(" ", "")
                .replace("\n", "")
                .strip()
            )

            m = re.search(r"(\d+)(○|△|×|抽選)", txt)

            if m:
                results.append(
                    f"{m.group(1)}{m.group(2)}"
                )

        except:
            pass

    log(f"[{label}] 抽出件数: {len(results)}")

    return results

# =========================
# ANALYZE
# =========================
def analyze(results, label):
    ok = [x for x in results if "○" in x or "△" in x]
    lot = [x for x in results if "抽選" in x]
    ng = [x for x in results if "×" in x]

    log(
        f"{label}: ○△={len(ok)} / "
        f"抽選={len(lot)} / ×={len(ng)}"
    )

# =========================
# FLOW
# =========================
def open_calendar(page):

    # 公共施設予約メニュー
    page.locator(
        "input[type='submit']",
        has_text="公共施設予約メニュー"
    ).first.click()

    page.wait_for_timeout(1500)

    # 空き照会
    page.locator(
        "input[type='submit']",
        has_text="空き照会"
    ).first.click()

    page.wait_for_timeout(1500)

    # 次頁
    page.locator(
        "input[type='submit']",
        has_text="次頁"
    ).first.click()

    page.wait_for_timeout(2000)

    # 柳北
    page.locator(
        "input[type='submit']",
        has_text="柳北"
    ).first.wait_for(timeout=30000)

    page.locator(
        "input[type='submit']",
        has_text="柳北"
    ).first.click()

    page.wait_for_timeout(1500)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_timeout(1500)

    # カレンダー
    page.locator(
        "input[type='submit']",
        has_text="カレンダー"
    ).first.click()

    page.wait_for_timeout(1500)

    # 1ヶ月
    page.locator(
        "input[type='submit']",
        has_text="1ヶ月"
    ).first.click()

    page.wait_for_timeout(1500)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_timeout(4000)

# =========================
# NEXT PAGE
# =========================
def go_next(page):

    try:
        log("⏭️ 次ページ（native click only）")

        next_btn = page.locator("#btnNextPeriod")

        next_btn.wait_for(timeout=10000)

        before_links = page.locator(
            "a[id*='lnkKoma']"
        ).count()

        before_url = page.url

        log(f"遷移前URL: {before_url}")
        log(f"遷移前link数: {before_links}")

        # ★ evaluate禁止
        # ★ dispatch禁止
        # ★ submit禁止
        # ★ EVENTTARGET禁止

        next_btn.click(delay=200)

        # ★ networkidle禁止
        time.sleep(8)

        after_url = page.url

        after_links = page.locator(
            "a[id*='lnkKoma']"
        ).count()

        body_head = page.inner_text("body")[:400]

        log(f"遷移後URL: {after_url}")
        log(f"遷移後link数: {after_links}")

        log(f"BODY HEAD:\n{body_head}")

        if "お探しのページを表示できません" in body_head:
            log("❌ 不正遷移")
            return False

        if after_links == 0:
            log("❌ lnkKoma消失")
            return False

        log("✅ 2ページ取得成功")

        return True

    except Exception as e:
        log(f"❌ 次ページ失敗: {e}")
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

        context = browser.new_context(
            viewport={"width": 1400, "height": 1200}
        )

        page = context.new_page()

        final = []

        try:

            page.goto(
                BASE_URL,
                wait_until="domcontentloaded"
            )

            page.wait_for_timeout(3000)

            # =========================
            # 1ページ目
            # =========================
            open_calendar(page)

            log("📑 1ページ目")

            res1 = parse(page, "1P")

            log(f"1P: {res1}")

            analyze(res1, "1P")

            final.extend(res1)

            # =========================
            # 2ページ目
            # =========================
            if go_next(page):

                log("📑 2ページ目")

                res2 = parse(page, "2P")

                log(f"2P: {res2}")

                analyze(res2, "2P")

                final.extend(res2)

            else:
                log("⚠️ 2ページ取得失敗")

            # =========================
            # FINAL
            # =========================
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(
                    re.sub(r"\D", "", x)
                )
            )

            log(f"📦 FINAL: {final_unique}")

            ok_exists = any(
                ("○" in x or "△" in x)
                for x in final_unique
            )

            if ok_exists:

                msg = (
                    f"@everyone\n"
                    f"🏸 空きあり [{VERSION}]\n"
                    f"{len(final_unique)}件\n"
                    f"```\n"
                    + "\n".join(final_unique)
                    + "\n```"
                )

            else:
                msg = f"🏸 空きなし [{VERSION}]"

            send(msg)

        except Exception as e:

            log(f"🔥 ERROR: {e}")

            try:
                page.screenshot(
                    path="debug_error.png",
                    full_page=True
                )
            except:
                pass

            send(
                f"⚠️ エラー [{VERSION}]\n{e}"
            )

        finally:

            browser.close()

            log("🔒 END")

# =========================
# ENTRY
# =========================
if __name__ == "__main__":
    run()
