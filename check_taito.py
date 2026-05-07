import requests
import os
import re
import json
from datetime import datetime
from playwright.sync_api import sync_playwright
import jpholiday
import redis

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
REDIS_URL = os.getenv("REDIS_URL")

BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"

VERSION = "v10.2-log-clean"

WEEKS = ["月", "火", "水", "木", "金", "土", "日"]

# =========================================
# Redis
# =========================================

r = None

if REDIS_URL:

    try:

        connection_url = (
            REDIS_URL.replace("redis://", "rediss://", 1)
            if REDIS_URL.startswith("redis://")
            else REDIS_URL
        )

        r = redis.from_url(
            connection_url,
            decode_responses=True,
            ssl_cert_reqs=None
        )

        r.ping()

        print("✅ Redis connection successful (Taito)")

    except Exception as e:

        print(f"❌ Redis connection error: {e}")

        r = None


# =========================================
# util
# =========================================

def log(msg):

    now = datetime.now().strftime("%H:%M:%S")

    print(f"[{now}] {msg}", flush=True)


def send(msg):

    print("\n=== DISCORD SEND ===")
    print(msg)

    if not WEBHOOK_URL:
        return

    try:

        requests.post(
            WEBHOOK_URL,
            json={"content": msg[:2000]},
            timeout=20
        )

        log("✅ Discord通知成功")

    except Exception as e:

        log(f"❌ Discord送信失敗: {e}")


# =========================================
# block resources
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
# click helper
# =========================================

def click(page, selector, wait_selector=None, label=None):

    if label:
        log(f"➡️ {label}")

    page.locator(selector).first.click(
        timeout=5000
    )

    if wait_selector:

        page.wait_for_selector(
            wait_selector,
            timeout=5000
        )


# =========================================
# parse
# =========================================

def parse(page, label):

    results = []

    table = page.locator("table").nth(21)

    links = table.locator(
        "a[id*='lnkKoma']"
    ).all()

    log(f"📊 [{label}] link数: {len(links)}")

    for l in links:

        try:

            txt = (
                l.inner_text()
                .replace("\xa0", "")
                .replace(" ", "")
                .strip()
            )

            m = re.search(
                r"(\d+)\s*(○|△|×|抽選)",
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

    for rdata in results:

        key = f"{rdata['day']}_{rdata['status']}"

        unique[key] = rdata

    results = sorted(
        unique.values(),
        key=lambda x: x["day"]
    )

    log(f"✅ [{label}] 抽出件数: {len(results)}")

    return results


# =========================================
# open calendar
# =========================================

def open_calendar(page):

    log("🌐 TOPアクセス")

    page.goto(
        BASE_URL,
        wait_until="domcontentloaded",
        timeout=15000
    )

    click(
        page,
        "input[value='公共施設予約メニュー']",
        label="公共施設予約メニュー"
    )

    click(
        page,
        "input[value*='空き照会']",
        label="空き照会"
    )

    click(
        page,
        "input[value='次頁']",
        label="次頁"
    )

    click(
        page,
        "input[value*='柳北']",
        label="柳北選択"
    )

    click(
        page,
        "input[name='ucPCFooter$btnForward']",
        label="次へ"
    )

    click(
        page,
        "input[value='カレンダー']",
        label="カレンダー"
    )

    now = datetime.now()

    page.locator("#txtYear").fill(str(now.year))
    page.locator("#txtMonth").fill(str(now.month))
    page.locator("#txtDay").fill("1")

    log(f"📅 開始日: {now.year}/{now.month}/1")

    click(
        page,
        "input[value='1ヶ月']",
        label="1ヶ月表示"
    )

    click(
        page,
        "input[name='ucPCFooter$btnForward']",
        "a[id*='lnkKoma']",
        label="空き一覧表示"
    )


# =========================================
# next
# =========================================

def go_next(page):

    before = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"➡️ 次期間遷移 (before={before})")

    page.locator(
        "#btnNextPeriod"
    ).click(
        force=True,
        timeout=5000
    )

    page.wait_for_function(
        """
        (before) => {
            return document
                .querySelectorAll("a[id*='lnkKoma']")
                .length !== before
        }
        """,
        arg=before,
        timeout=7000
    )

    after = page.locator(
        "a[id*='lnkKoma']"
    ).count()

    log(f"✅ 次期間遷移成功 (after={after})")

    body = page.inner_text("body")

    if "お探しのページを表示できません" in body:

        log("❌ ASP.NET不正遷移検知")

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

        rows.append((item["day"], line))

    rows = sorted(rows, key=lambda x: x[0])

    return [x[1] for x in rows]


# =========================================
# mention
# =========================================

def has_mention_target(data, year, month):

    for item in data:

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

    log(f"🚀 柳北監視開始 [{VERSION}]")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )

        context = browser.new_context()

        page = context.new_page()

        block_resources(page)

        try:

            open_calendar(page)

            log("=== CURRENT MONTH ===")

            current = parse(page, "CURRENT")

            log("=== NEXT MONTH ===")

            next_data = go_next(page)

            now = datetime.now()

            current_lines = format_month(
                current,
                now.year,
                now.month
            )

            next_month = (
                1 if now.month == 12
                else now.month + 1
            )

            next_year = (
                now.year + 1
                if now.month == 12
                else now.year
            )

            next_lines = format_month(
                next_data,
                next_year,
                next_month
            )

            # Redis比較
            current_state = {
                "current": current_lines,
                "next": next_lines
            }

            is_changed = True

            if r:

                try:

                    last_raw = r.get("taito_ryuhoku_status")

                    if last_raw:

                        last_state = json.loads(last_raw)

                        if last_state == current_state:

                            is_changed = False

                    r.set(
                        "taito_ryuhoku_status",
                        json.dumps(current_state)
                    )

                except Exception as e:

                    log(f"❌ Redis Error: {e}")

            should_mention = (
                has_mention_target(
                    current,
                    now.year,
                    now.month
                )
                or
                has_mention_target(
                    next_data,
                    next_year,
                    next_month
                )
            )

            mention = (
                "@everyone\n"
                if should_mention and is_changed
                else ""
            )

            msg = (
                mention
                + f"🏸 柳北スポーツプラザ [{VERSION}]"
            )

            if not is_changed:
                msg += "（前回から変更なし）"

            msg += (

                f"\n\n【{now.month}月】\n"
                + (
                    "\n".join(current_lines)
                    if current_lines else "空きなし"
                )

                + f"\n\n【{next_month}月】\n"
                + (
                    "\n".join(next_lines)
                    if next_lines else "空きなし"
                )
            )

            send(msg)

            log(
                f"✅ 完了 "
                f"(changed={is_changed}, "
                f"mention={should_mention and is_changed})"
            )

        except Exception as e:

            log(f"❌ ERROR: {e}")

            send(f"⚠️ ERROR\n{e}")

        finally:

            context.close()
            browser.close()
            log("🛑 Browser closed")


if __name__ == "__main__":
    run()
