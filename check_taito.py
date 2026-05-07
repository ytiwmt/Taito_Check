def go_next(page):
    log("⏭️ 次ページ（完全POSTBACK）")

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

        # ★ここが核心
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

        return after_count > 0

    except Exception as e:
        log(f"❌ 遷移失敗: {e}")
        return False
