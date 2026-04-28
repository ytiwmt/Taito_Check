from playwright.sync_api import sync_playwright
import time

URL = "https://shisetsu.city.taito.lg.jp/StartPage.aspx?Startpage=ModeSelect"


def click(page, selector):
    el = page.locator(selector).filter(has_not=page.locator("[type='hidden']")).first
    el.wait_for(state="attached", timeout=30000)
    el.click()
    time.sleep(1.5)


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="domcontentloaded")
        time.sleep(2)

        # ★重要：visible inputに限定
        page.wait_for_selector("input[value='公共施設予約メニュー']", timeout=30000)

        click(page, "input[value='公共施設予約メニュー']")
        click(page, "input[name='rbtnYoyaku']")
        click(page, "input[value='次頁']")
        click(page, "input[value='柳北スポーツプラザ']")

        click(page, "input[name='rbCalendar'][value='カレンダー']")
        click(page, "input[name='rbtnMonth'][value='1ヶ月']")
        click(page, "input[name='ucPCFooter$btnForward']")

        time.sleep(3)

        print(page.inner_text("body"))

        browser.close()


if __name__ == "__main__":
    run()
