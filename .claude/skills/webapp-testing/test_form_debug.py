from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://www.anyvisionmedia.com", wait_until="networkidle", timeout=30000)

    # Test 1: POST to '/' (current approach)
    print("=== Test 1: POST to '/' ===")
    result1 = page.evaluate("""
        () => fetch('/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'form-name=contact&firstName=Test&lastName=One&email=t@t.com&company=Co&interest=strategy&message=test1'
        }).then(r => ({ status: r.status, url: r.url, redirected: r.redirected, statusText: r.statusText }))
    """)
    print(f"  Result: {result1}")

    # Test 2: POST to current page URL
    print("\n=== Test 2: POST to window.location.href ===")
    result2 = page.evaluate("""
        () => fetch(window.location.href, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'form-name=contact&firstName=Test&lastName=Two&email=t@t.com&company=Co&interest=strategy&message=test2'
        }).then(r => ({ status: r.status, url: r.url, redirected: r.redirected, statusText: r.statusText }))
    """)
    print(f"  Result: {result2}")

    # Test 3: POST to index.html
    print("\n=== Test 3: POST to '/index.html' ===")
    result3 = page.evaluate("""
        () => fetch('/index.html', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'form-name=contact&firstName=Test&lastName=Three&email=t@t.com&company=Co&interest=strategy&message=test3'
        }).then(r => ({ status: r.status, url: r.url, redirected: r.redirected, statusText: r.statusText }))
    """)
    print(f"  Result: {result3}")

    # Test 4: POST without redirect following
    print("\n=== Test 4: POST to '/' with redirect: 'manual' ===")
    result4 = page.evaluate("""
        () => fetch('/', {
            method: 'POST',
            redirect: 'manual',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'form-name=contact&firstName=Test&lastName=Four&email=t@t.com&company=Co&interest=strategy&message=test4'
        }).then(r => ({ status: r.status, type: r.type, url: r.url, redirected: r.redirected }))
    """)
    print(f"  Result: {result4}")

    # Test 5: POST to Netlify subdomain directly
    print("\n=== Test 5: POST to Netlify subdomain ===")
    result5 = page.evaluate("""
        () => fetch('https://animated-horse-c76645.netlify.app/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'form-name=contact&firstName=Test&lastName=Five&email=t@t.com&company=Co&interest=strategy&message=test5'
        }).then(r => ({ status: r.status, url: r.url, redirected: r.redirected }))
        .catch(e => ({ error: e.message }))
    """)
    print(f"  Result: {result5}")

    browser.close()
