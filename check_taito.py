import requests
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

VERSION = "v8.4-month-start-fix"


# =========================================
# util
# =========================================

def log(msg):
    print(msg, flush=True)


def send(msg):

    print("\n=== SEND ===")
    print(msg)

    if not WEBHOOK_URL:
        return

    try:
        requests.post(
            WEBHOOK_URL,
            json={"content": msg},
            timeout=20
        )
    except Exception as e:
        print(e)


# =========================================
# parse
# =========================================

def parse(page, label):

    results = []

    links = page.locator(
        "a[id*='lnkKoma']"
    ).all()

    log(f"[{label}] link数: {len(links)}")

    for l in links:

        try:

            txt = (
                l.inner_text()
                .replace("\xa0", "")
                .replace(" ", "")
                .strip()
            )

            m = re.search(
                r"(\d+)(○|△|×|抽選)",
                txt
            )

            if m:

                results.append(
                    f"{m.group(1)}{m.group(2)}"
                )

        except:
            pass

    log(f"[{label}] 件数: {len(results)}")

    return results


# =========================================
# setup
# =========================================

def open_calendar(page):

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded"
    )

    page.wait_for_timeout(3000)

    # 公共施設予約メニュー
    page.locator(
        "input[value='公共施設予約メニュー']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 空き照会
    page.locator(
        "input[value*='空き照会']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次頁
    page.locator(
        "input[value='次頁']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2000)

    # 柳北
    page.locator(
        "input[value*='柳北']"
    ).first.wait_for(timeout=30000)

    page.locator(
        "input[value*='柳北']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)

    # カレンダー
    page.locator(
        "input[value='カレンダー']"
    ).first.click()

    page.wait_for_timeout(1000)

    # =====================================
    # 表示開始日 = 今月1日
    # =====================================

    now = datetime.now()

    # year
    txt_year = page.locator("#txtYear")
    txt_year.click()

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    txt_year.type(str(now.year))

    # month
    txt_month = page.locator("#txtMonth")
    txt_month.click()

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    txt_month.type(str(now.month))

    # day
    txt_day = page.locator("#txtDay")
    txt_day.click()

    page.keyboard.press("Control+A")
    page.keyboard.press("Backspace")

    txt_day.type("1")

    log(f"開始日: {now.year}/{now.month}/1")

    page.wait_for_timeout(1000)

    # 1ヶ月
    page.locator(
        "input[value='1ヶ月']"
    ).first.click()

    page.wait_for_timeout(1000)

    # 次へ
    page.locator(
        "input[name='ucPCFooter$btnForward']"
    ).first.click()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(5000)

    page.wait_for_selector(
        "a[id*='lnkKoma']",
        timeout=30000
    )


# =========================================
# next page
# =========================================

def go_next(page):

    try:

        log("⏭️ btnNextPeriod click")

        before = page.locator(
            "a[id*='lnkKoma']"
        ).count()

        log(f"before links: {before}")

        page.locator(
            "#btnNextPeriod"
        ).click(force=True)

        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(5000)

        body = page.inner_text("body")

        after = page.locator(
            "a[id*='lnkKoma']"
        ).count()

        log(f"after links: {after}")

        if "お探しのページを表示できません" in body:

            log("❌ 不正遷移")

            log(body[:500])

            return []

        return parse(page, "NEXT")

    except Exception as e:

        log(f"❌ NEXT ERROR: {e}")

        try:
            body = page.inner_text("body")
            log(body[:1000])
        except:
            pass

        return []


# =========================================
# main
# =========================================

def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = browser.new_context(
            viewport={
                "width": 1400,
                "height": 1200
            }
        )

        page = context.new_page()

        final = []

        try:

            open_calendar(page)

            # CURRENT
            log("=== CURRENT ===")

            current = parse(
                page,
                "CURRENT"
            )

            final.extend(current)

            # NEXT
            log("=== NEXT ===")

            next_data = go_next(page)

            final.extend(next_data)

            # FINAL
            final = sorted(
                list(set(final)),
                key=lambda x: int(
                    re.sub(r"\D", "", x)
                )
            )

            log(f"FINAL: {final}")

            msg = (
                "@everyone\n"
                f"🏸 柳北スポーツプラザ [{VERSION}]\n"
                + "\n".join(final)
            )

            send(msg)

        except Exception as e:

            log(f"ERROR: {e}")

            try:
                page.screenshot(
                    path="debug.png",
                    full_page=True
                )
            except:
                pass

            send(f"⚠️ ERROR\n{e}")

        finally:
            browser.close()


if __name__ == "__main__":
    run()
