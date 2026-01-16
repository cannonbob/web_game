from playwright.sync_api import sync_playwright
import time

def test_silhouette_timing():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        # Open test file
        page.goto('file:///C:/Users/Kai/Documents/Projekte/VS Code/web game v1/test_silhouette.html')

        # Set up console message listener
        console_messages = []
        page.on('console', lambda msg: console_messages.append(f"[{time.time():.1f}] {msg.text}"))

        # Wait for page to load
        page.wait_for_load_state('networkidle')

        print("Starting test...")
        start_time = time.time()

        # Click start button
        page.click('button:has-text("Start Animation")')

        # Monitor the animation for 50 seconds
        for i in range(50):
            elapsed = time.time() - start_time

            # Get current phase
            phase_text = page.locator('#phaseInfo').text_content()
            timer_text = page.locator('#timer').text_content()

            # Get computed styles
            img = page.locator('#silhouette-image')
            clip_path = img.evaluate('el => window.getComputedStyle(el).clipPath')
            filter_value = img.evaluate('el => window.getComputedStyle(el).filter')

            print(f"t={elapsed:.1f}s | {phase_text} | {timer_text} | clip-path: {clip_path[:30]}... | filter: {filter_value}")

            time.sleep(1)

        print("\n=== Console Messages ===")
        for msg in console_messages:
            print(msg)

        browser.close()

if __name__ == '__main__':
    test_silhouette_timing()
