from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.anyvisionmedia.com", wait_until="networkidle", timeout=30000)

    # Scroll to form
    page.locator('#contact').scroll_into_view_if_needed()
    page.wait_for_timeout(1000)

    # Fill form
    page.locator('#firstName').fill('Test')
    page.locator('#lastName').fill('Verified')
    page.locator('#email').fill('ian@anyvisionmedia.com')
    page.locator('#company').fill('AnyVision Media')
    page.locator('#interest').select_option('strategy')
    page.locator('#message').fill('Final verification test - form should work now')

    # Submit and capture response
    with page.expect_response(lambda r: r.request.method == "POST", timeout=15000) as resp_info:
        page.locator('#contactForm button[type="submit"]').click()

    resp = resp_info.value
    print(f"POST status: {resp.status}")
    print(f"POST URL: {resp.url}")

    page.wait_for_timeout(2000)
    btn_text = page.locator('#contactForm button[type="submit"]').inner_text().strip()
    print(f"Button text after submit: {btn_text}")
    page.screenshot(path="/tmp/form_verified.png")

    if resp.status == 200 and "Sent" in btn_text:
        print("\nFORM IS WORKING!")
    else:
        print("\nFORM STILL HAS ISSUES")

    browser.close()
