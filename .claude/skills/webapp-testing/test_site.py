from playwright.sync_api import sync_playwright
import json

console_messages = []
network_errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture console messages
    page.on("console", lambda msg: console_messages.append({
        "type": msg.type,
        "text": msg.text
    }))

    # Capture network failures
    page.on("requestfailed", lambda req: network_errors.append({
        "url": req.url,
        "failure": req.failure
    }))

    print("=== Navigating to site ===")
    page.goto("https://www.anyvisionmedia.com", wait_until="networkidle", timeout=30000)
    page.screenshot(path="/tmp/site_loaded.png", full_page=False)
    print(f"Page title: {page.title()}")

    # Check the hero CTA button
    print("\n=== Checking Hero CTA Button ===")
    hero_btn = page.locator('.hero .btn-primary').first
    if hero_btn.count() > 0:
        href = hero_btn.get_attribute('href')
        text = hero_btn.inner_text()
        print(f"Hero button text: {text.strip()}")
        print(f"Hero button href: {href}")
    else:
        print("Hero CTA button not found")

    # Scroll to contact section
    print("\n=== Scrolling to Contact Form ===")
    page.locator('#contact').scroll_into_view_if_needed()
    page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/contact_section.png", full_page=False)

    # Check form exists
    form = page.locator('#contactForm')
    print(f"Form found: {form.count() > 0}")

    # Check hidden form-name input
    hidden_input = page.locator('input[name="form-name"]')
    print(f"Hidden form-name input found: {hidden_input.count() > 0}")
    if hidden_input.count() > 0:
        print(f"Hidden form-name value: {hidden_input.get_attribute('value')}")

    # Fill out the form
    print("\n=== Filling Form ===")
    page.locator('#firstName').fill('Test')
    page.locator('#lastName').fill('Browser')
    page.locator('#email').fill('test@browser.com')
    page.locator('#company').fill('Test Co')
    page.locator('#interest').select_option('strategy')
    page.locator('#message').fill('Browser test submission')

    page.screenshot(path="/tmp/form_filled.png", full_page=False)
    print("Form filled successfully")

    # Submit form and capture response
    print("\n=== Submitting Form ===")

    # Listen for the fetch response
    with page.expect_response(lambda r: r.request.method == "POST", timeout=15000) as response_info:
        page.locator('#contactForm button[type="submit"]').click()

    response = response_info.value
    print(f"POST response status: {response.status}")
    print(f"POST response URL: {response.url}")

    # Wait for UI to update
    page.wait_for_timeout(2000)
    page.screenshot(path="/tmp/after_submit.png", full_page=False)

    # Check button text after submit
    submit_btn = page.locator('#contactForm button[type="submit"]')
    if submit_btn.count() > 0:
        btn_text = submit_btn.inner_text()
        print(f"Submit button text after submit: {btn_text.strip()}")

    # Check the booking button in the contact section
    print("\n=== Checking Booking Button ===")
    booking_btns = page.locator('a[href*="calendar.app.google"]')
    print(f"Booking buttons found: {booking_btns.count()}")
    for i in range(booking_btns.count()):
        btn = booking_btns.nth(i)
        print(f"  Button {i+1}: text='{btn.inner_text().strip()[:50]}', href='{btn.get_attribute('href')}'")

    # Print console messages
    print(f"\n=== Console Messages ({len(console_messages)}) ===")
    for msg in console_messages:
        if msg["type"] in ("error", "warning"):
            print(f"  [{msg['type']}] {msg['text'][:200]}")

    # Print network errors
    print(f"\n=== Network Errors ({len(network_errors)}) ===")
    for err in network_errors:
        print(f"  {err['url']}: {err['failure']}")

    browser.close()
    print("\n=== Done ===")
