import requests
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

VERSION = "v9.2-fast-route-fixed"


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

    # 体育館テーブル固定
    table = page.locator("table").nth(21)

    links = table.locator(
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

    results = sorted(
        list(set(results)),
        key=lambda x: int(
            re.sub(r"\D", "", x)
        )
    )

    log(f"[{label}] 件数: {len(results)}")

    return results


# =========================================
# helper
# =========================================

def click(page, selector, wait_selector=None):

    page.locator(selector).first.click()

    if wait_selector:

        page.wait_for_selector(
            wait_selector,
            timeout=15000
        )


# =========================================
# open
# =========================================

def open_calendar(page):

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded"
    )

    # 公共施設予約メニュー
    click(
        page,
        "input[value='公共施設予約メニュー']"
    )

    # 空き照会
    click(
        page,
        "input[value*='空き照会']"
    )

    # 次頁
    click(
        page,
        "input[value='次頁']"
    )

    # 柳北
    page.locator(
        "input[value*='柳北']"
    ).first.wait_for(timeout=15000)

    click(
        page,
        "input[value*='柳北']"
    )

    # 次へ
    click(
        page,
        "input[name='ucPCFooter$btnForward']"
    )

    # カレンダー
    click(
        page,
        "input[value='カレンダー']"
    )

    # ==========================
    # 開始日 = 今月1日
    # ==========================

    now = datetime.now()

    page.locator("#txtYear").fill(
        str(now.year)
    )

    page.locator("#txtMonth").fill(
        str(now.month)
    )

    page.locator("#txtDay").fill("1")

    log(f"開始日: {now.year}/{now.month}/1")

    # 1ヶ月
    click(
        page,
        "input[value='1ヶ月']"
    )

    # 次へ
    click(
        page,
        "input[name='ucPCFooter$btnForward']",
        "a[id*='lnkKoma']"
    )


# =========================================
# next
# =========================================

def go_next(page):

    before = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"before links: {before}")

    page.locator(
        "#btnNextPeriod"
    ).click(force=True)

    # 44 -> 58 みたいな増加待ち
    page.wait_for_function(
        """
        (before) => {
            return (
                document
                    .querySelectorAll("a[id*='lnkKoma']")
                    .length > before
            )
        }
        """,
        arg=before,
        timeout=15000
    )

    after = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"after links: {after}")

    body = page.inner_text("body")

    if "お探しのページを表示できません" in body:

        log("❌ 不正遷移")

        return []

    return parse(page, "NEXT")


# =========================================
# main
# =========================================

def run():

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        page = browser.new_page()

        try:

            open_calendar(page)

            # CURRENT
            log("=== CURRENT ===")

            current = parse(
                page,
                "CURRENT"
            )

            # NEXT
            log("=== NEXT ===")

            next_data = go_next(page)

            now = datetime.now()

            current_month = now.month

            next_month = (
                1 if now.month == 12
                else now.month + 1
            )

            msg = (
                "@everyone\n"
                f"🏸 柳北スポーツプラザ [{VERSION}]\n\n"

                f"【{current_month}月】\n"
                + (
                    "\n".join(current)
                    if current else "データなし"
                )

                + "\n\n"

                f"【{next_month}月】\n"
                + (
                    "\n".join(next_data)
                    if next_data else "データなし"
                )
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
