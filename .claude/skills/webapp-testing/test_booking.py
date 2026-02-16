from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    print("=== Loading booking page ===")
    page.goto("https://calendar.app.google/79JABt2piDQ5X4gW8", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    print(f"Page title: {page.title()}")
    page.screenshot(path="/tmp/booking_page.png", full_page=True)
    print("Screenshot saved to /tmp/booking_page.png")

    # Try to get any visible text about availability
    body_text = page.locator("body").inner_text()
    # Print first 1000 chars to see what's on the page
    print(f"\nPage content preview:\n{body_text[:1500]}")

    browser.close()
