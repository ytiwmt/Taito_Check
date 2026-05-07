import requests
from playwright.sync_api import sync_playwright
import os
import re
import datetime

VERSION = "v7.32-final-stable"

WEBHOOK_URL = os.getenv("WEBHOOK_URL_Taito")
BASE_URL = "https://shisetsu.city.taito.lg.jp/Wg_ModeSelect.aspx"


# =========================
# ログ
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
# 解析
# =========================
def parse(page, label):
    results = []

    links = page.locator("a[id*='lnkKoma']").all()
    log(f"[{label}] link数: {len(links)}")

    for l in links:
        try:
            txt = l.inner_text()
            txt = txt.replace("\xa0", "").replace(" ", "").strip()
        except:
            continue

        m = re.search(r"(\d+)(○|△|×|抽選)", txt)
        if m:
            results.append(f"{m.group(1)}{m.group(2)}")

    log(f"[{label}] 抽出件数: {len(results)}")
    return results


def analyze(results, label):
    ok = [r for r in results if "○" in r or "△" in r]
    lot = [r for r in results if "抽選" in r]
    ng = [r for r in results if "×" in r]
    log(f"{label}: ○△={len(ok)} / 抽選={len(lot)} / ×={len(ng)}")


# =========================
# 次ページ（描画待ち修正版）
# =========================
def go_next(page):
    log("⏭️ 次ページ（POSTBACK + DOM変化待ち）")

    try:
        before_count = page.locator("a[id*='lnkKoma']").count()
        log(f"遷移前リンク数: {before_count}")

        page.evaluate("""
            () => {
                const form = document.forms[0];

                let et = document.querySelector("input[name='__EVENTTARGET']");
                if (!et) {
                    et = document.createElement("input");
                    et.type = "hidden";
                    et.name = "__EVENTTARGET";
                    form.appendChild(et);
                }
                et.value = "dlRepeat2$ctl00$tpItem2$Migrated_lnkNextSpan";

                let ea = document.querySelector("input[name='__EVENTARGUMENT']");
                if (!ea) {
                    ea = document.createElement("input");
                    ea.type = "hidden";
                    ea.name = "__EVENTARGUMENT";
                    form.appendChild(ea);
                }
                ea.value = "";

                form.submit();
            }
        """)

        # ★ここが最重要
        page.wait_for_function(
            """(prev) => {
                const now = document.querySelectorAll("a[id*='lnkKoma']").length;
                return now !== prev;
            }""",
            arg=before_count,
            timeout=15000
        )

        page.wait_for_selector("a[id*='lnkKoma']", timeout=15000)

        after_count = page.locator("a[id*='lnkKoma']").count()
        log(f"遷移後リンク数: {after_count}")

        if after_count == 0:
            log("❌ DOM更新されたがデータなし")
            return False

        log("✅ 2ページ目取得成功")
        return True

    except Exception as e:
        log(f"❌ 遷移失敗: {e}")
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
            page.goto(BASE_URL)

            page.locator("input[type='submit']", has_text="公共施設予約メニュー").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[type='submit']", has_text="空き照会").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[type='submit']", has_text="次頁").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[type='submit']", has_text="柳北").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[type='submit']", has_text="カレンダー").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[type='submit']", has_text="1ヶ月").first.click()
            page.wait_for_load_state("networkidle")

            page.locator("input[name='ucPCFooter$btnForward']").first.click()
            page.wait_for_load_state("networkidle")

            # =========================
            # 1ページ
            # =========================
            log("📑 1ページ目")
            res1 = parse(page, "1P")
            analyze(res1, "1P")
            final.extend(res1)

            # =========================
            # 2ページ
            # =========================
            if go_next(page):
                log("📑 2ページ目")
                res2 = parse(page, "2P")
                analyze(res2, "2P")
                final.extend(res2)
            else:
                log("⚠️ 2ページ取得失敗")

            # =========================
            # 集約
            # =========================
            final_unique = sorted(
                list(set(final)),
                key=lambda x: int(re.sub(r"\D", "", x))
            )

            log(f"📦 FINAL: {final_unique}")

            # 通知
            if any(("○" in x or "△" in x) for x in final_unique):
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
            send(f"⚠️ エラー [{VERSION}]\n{e}")

        finally:
            log("🔒 END")
            browser.close()


if __name__ == "__main__":
    run()
