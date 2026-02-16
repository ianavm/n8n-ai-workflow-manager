from playwright.sync_api import sync_playwright

console_errors = []
network_log = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    # Capture ALL console messages
    page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}"))

    # Capture ALL network requests/responses
    page.on("response", lambda resp: network_log.append(f"{resp.request.method} {resp.url} -> {resp.status}"))
    page.on("requestfailed", lambda req: network_log.append(f"FAILED: {req.method} {req.url} {req.failure}"))

    print("=== Loading site ===")
    page.goto("https://www.anyvisionmedia.com", wait_until="networkidle", timeout=30000)
    print(f"Page loaded: {page.title()}")

    # Check what URL the fetch actually goes to
    print("\n=== Checking deployed JS fetch URL ===")
    fetch_url = page.evaluate("""
        () => {
            const scripts = document.querySelectorAll('script');
            for (const s of scripts) {
                if (s.textContent.includes('fetch(')) {
                    const match = s.textContent.match(/fetch\\(['"]([^'"]+)['"]/);
                    if (match) return match[1];
                }
            }
            return 'not found';
        }
    """)
    print(f"Fetch URL in deployed JS: {fetch_url}")

    # Scroll to form and fill it out
    print("\n=== Filling form ===")
    page.locator('#contact').scroll_into_view_if_needed()
    page.wait_for_timeout(1000)

    page.locator('#firstName').fill('EndToEnd')
    page.locator('#lastName').fill('Test')
    page.locator('#email').fill('ian@anyvisionmedia.com')
    page.locator('#company').fill('AnyVision Media')
    page.locator('#interest').select_option('strategy')
    page.locator('#message').fill('E2E test - checking if form actually submits')

    # Clear network log before submit to isolate POST
    network_log.clear()
    console_errors.clear()

    print("\n=== Submitting form ===")
    # Click and wait for response
    try:
        with page.expect_response(lambda r: r.request.method == "POST", timeout=15000) as resp_info:
            page.locator('#contactForm button[type="submit"]').click()

        resp = resp_info.value
        print(f"POST URL: {resp.url}")
        print(f"POST Status: {resp.status}")
        print(f"POST Status Text: {resp.status_text}")

        # Get response body
        try:
            body = resp.text()[:300]
            print(f"Response body (first 300 chars): {body}")
        except:
            print("Could not read response body")

        # Check request details
        req = resp.request
        print(f"\nRequest URL: {req.url}")
        print(f"Request method: {req.method}")
        print(f"Request headers: {dict(req.headers)}")
        print(f"Request post data: {req.post_data[:300] if req.post_data else 'None'}")

    except Exception as e:
        print(f"Error waiting for response: {e}")

    page.wait_for_timeout(2000)

    # Check button state
    btn = page.locator('#contactForm button[type="submit"]')
    print(f"\nButton text after submit: {btn.inner_text().strip()}")
    print(f"Button disabled: {btn.is_disabled()}")

    page.screenshot(path="/tmp/e2e_result.png")

    # Print all console messages
    print(f"\n=== Console ({len(console_errors)}) ===")
    for msg in console_errors:
        print(f"  {msg}")

    # Print network log
    print(f"\n=== Network after submit ({len(network_log)}) ===")
    for entry in network_log:
        print(f"  {entry}")

    browser.close()
