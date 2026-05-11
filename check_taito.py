import requests
import os
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import jpholiday

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

VERSION = "v10.4-no-link-wait"

WEEKS = ["月", "火", "水", "木", "金", "土", "日"]

DEBUG = False


# =========================================
# util
# =========================================

def log(msg):

    if DEBUG:
        print(msg, flush=True)


def info(msg):

    print(msg, flush=True)


def send(msg):

    if DEBUG:
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

        info(f"⚠️ Discord送信失敗: {e}")


# =========================================
# block heavy resources
# =========================================

def block_resources(page):

    def handler(route):

        rtype = route.request.resource_type

        if rtype in [
            "image",
            "media",
            "font",
            "stylesheet"
        ]:
            route.abort()

        else:
            route.continue_()

    page.route("**/*", handler)


# =========================================
# parse
# =========================================

def parse(page, label):

    results = []

    # 体育館テーブル固定
    table = page.locator("table").nth(21)

    cells = table.locator("a[id*='lnkKoma'], span").all()

    log(f"[{label}] cell数: {len(cells)}")

    for c in cells:

        try:

            txt = (
                c.inner_text()
                .replace("\xa0", "")
                .replace(" ", "")
                .strip()
            )

            m = re.search(
                r"(\d+)\s*(○|△|×|抽選|－)",
                txt
            )

            if m:

                results.append({
                    "day": int(m.group(1)),
                    "status": m.group(2)
                })

        except:
            pass

    unique = {}

    for r in results:

        key = f"{r['day']}_{r['status']}"

        unique[key] = r

    results = sorted(
        unique.values(),
        key=lambda x: x["day"]
    )

    log(f"[{label}] 件数: {len(results)}")

    return results


# =========================================
# click helper
# =========================================

def click(page, selector, wait_selector=None):

    page.locator(selector).first.click(
        timeout=5000
    )

    if wait_selector:

        page.wait_for_selector(
            wait_selector,
            timeout=5000
        )


# =========================================
# open calendar
# =========================================

def open_calendar(page):

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded",
        timeout=15000
    )

    click(
        page,
        "input[value='公共施設予約メニュー']"
    )

    click(
        page,
        "input[value*='空き照会']"
    )

    click(
        page,
        "input[value='次頁']"
    )

    click(
        page,
        "input[value*='柳北']"
    )

    click(
        page,
        "input[name='ucPCFooter$btnForward']"
    )

    click(
        page,
        "input[value='カレンダー']"
    )

    # 今月1日スタート
    now = datetime.now()

    page.locator("#txtYear").fill(
        str(now.year)
    )

    page.locator("#txtMonth").fill(
        str(now.month)
    )

    page.locator("#txtDay").fill("1")

    log(f"開始日: {now.year}/{now.month}/1")

    click(
        page,
        "input[value='1ヶ月']"
    )

    click(
        page,
        "input[name='ucPCFooter$btnForward']"
    )

    page.wait_for_timeout(1500)


# =========================================
# next month
# =========================================

def go_next(page):

    before_html = page.locator(
        "body"
    ).inner_html()

    page.locator(
        "#btnNextPeriod"
    ).click(
        force=True,
        timeout=5000
    )

    page.wait_for_function(
        """
        (before) => {
            return document.body.innerHTML !== before
        }
        """,
        arg=before_html,
        timeout=7000
    )

    page.wait_for_timeout(1500)

    body = page.inner_text("body")

    if "お探しのページを表示できません" in body:

        log("❌ 不正遷移")

        return []

    return parse(page, "NEXT")


# =========================================
# format
# =========================================

def format_month(data, year, month):

    rows = []

    for item in data:

        dt = datetime(
            year,
            month,
            item["day"]
        ).date()

        w = WEEKS[dt.weekday()]

        holiday_name = jpholiday.is_holiday_name(dt)

        line = f"{month}/{item['day']}({w}) {item['status']}"

        if holiday_name:
            line += f" ★({holiday_name})"

        rows.append(
            (item["day"], line)
        )

    rows = sorted(
        rows,
        key=lambda x: x[0]
    )

    seen = set()

    final = []

    for _, line in rows:

        if line not in seen:

            seen.add(line)

            final.append(line)

    return final


# =========================================
# mention
# =========================================

def has_weekend_or_holiday(data, year, month):

    for item in data:

        # ○△だけ通知対象
        if item["status"] not in ["○", "△"]:
            continue

        dt = datetime(
            year,
            month,
            item["day"]
        ).date()

        if (
            dt.weekday() >= 5
            or jpholiday.is_holiday(dt)
        ):
            return True

    return False


# =========================================
# main
# =========================================

def run():

    should_mention = False

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--disable-translate"
            ]
        )

        context = browser.new_context()

        page = context.new_page()

        block_resources(page)

        try:

            open_calendar(page)

            current = parse(
                page,
                "CURRENT"
            )

            next_data = go_next(page)

            now = datetime.now()

            current_month = now.month

            next_month = (
                1 if now.month == 12
                else now.month + 1
            )

            next_year = (
                now.year + 1
                if now.month == 12
                else now.year
            )

            current_lines = format_month(
                current,
                now.year,
                current_month
            )

            next_lines = format_month(
                next_data,
                next_year,
                next_month
            )

            should_mention = (
                has_weekend_or_holiday(
                    current,
                    now.year,
                    current_month
                )
                or
                has_weekend_or_holiday(
                    next_data,
                    next_year,
                    next_month
                )
            )

            mention = (
                "@everyone\n"
                if should_mention
                else ""
            )

            msg = (
                mention
                + f"🏸 柳北スポーツプラザ [{VERSION}]\n\n"

                f"【{current_month}月】\n"
                + (
                    "\n".join(current_lines)
                    if current_lines else "空きなし"
                )

                + "\n\n"

                f"【{next_month}月】\n"
                + (
                    "\n".join(next_lines)
                    if next_lines else "空きなし"
                )
            )

            send(msg)

            info(
                f"✅ 台東区完了 "
                f"(mention: {should_mention})"
            )

        except Exception as e:

            info(f"⚠️ 台東区 ERROR: {e}")

            send(f"⚠️ ERROR\n{e}")

        finally:

            context.close()
            browser.close()


if __name__ == "__main__":
    run()
