"""
Amazon Price Scraper Utility
Fetches current product price from Amazon.de
"""

from playwright.sync_api import sync_playwright
import time
import random
import re


def fetch_amazon_price(asin):
    """
    Fetch the current price and image URL for a product from Amazon.de

    Args:
        asin (str): Amazon Standard Identification Number

    Returns:
        tuple: (price, image_url) where price is float in euros or None,
               and image_url is string or None
    """
    try:
        with sync_playwright() as p:
            # Launch browser with anti-bot detection settings
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            # Create context with realistic user agent
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='de-DE',
                timezone_id='Europe/Berlin',
                extra_http_headers={
                    'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                }
            )

            # Mask automation
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = context.new_page()

            # Navigate to product page
            url = f'https://www.amazon.de/dp/{asin}'
            print(f"Fetching price from: {url}")
            page.goto(url, wait_until='domcontentloaded', timeout=30000)

            # Minimal delay to let dynamic content load
            time.sleep(0.5)

            # Try to find price and image using various selectors
            price = None
            image_url = None

            # Extract product image first
            try:
                # Try main product image
                img_elem = page.locator('#landingImage').first
                if img_elem.count() == 0:
                    # Try alternative selectors
                    img_elem = page.locator('.a-dynamic-image').first

                if img_elem.count() > 0:
                    image_url = img_elem.get_attribute('src')
                    print(f"Found image URL: {image_url}")
            except Exception as e:
                print(f"Image extraction failed: {e}")

            # Method 1: Try .a-price .a-offscreen (most common)
            try:
                price_elem = page.locator('.a-price .a-offscreen').first
                if price_elem.count() > 0:
                    price_text = price_elem.inner_text()
                    price = parse_price_text(price_text)
                    print(f"Found price (method 1): {price_text} -> {price}")
            except Exception as e:
                print(f"Method 1 failed: {e}")

            # Method 2: Try #priceblock_ourprice
            if price is None:
                try:
                    price_elem = page.locator('#priceblock_ourprice').first
                    if price_elem.count() > 0:
                        price_text = price_elem.inner_text()
                        price = parse_price_text(price_text)
                        print(f"Found price (method 2): {price_text} -> {price}")
                except Exception as e:
                    print(f"Method 2 failed: {e}")

            # Method 3: Try #priceblock_dealprice
            if price is None:
                try:
                    price_elem = page.locator('#priceblock_dealprice').first
                    if price_elem.count() > 0:
                        price_text = price_elem.inner_text()
                        price = parse_price_text(price_text)
                        print(f"Found price (method 3): {price_text} -> {price}")
                except Exception as e:
                    print(f"Method 3 failed: {e}")

            # Method 4: Try .a-price-whole
            if price is None:
                try:
                    price_elem = page.locator('.a-price-whole').first
                    if price_elem.count() > 0:
                        price_text = price_elem.inner_text()
                        price = parse_price_text(price_text)
                        print(f"Found price (method 4): {price_text} -> {price}")
                except Exception as e:
                    print(f"Method 4 failed: {e}")

            # Method 5: Search page content for price patterns
            if price is None:
                try:
                    content = page.content()
                    # Look for patterns like "19,99 €" or "19.99€"
                    price_patterns = [
                        r'(\d+[,\.]\d{2})\s*€',
                        r'€\s*(\d+[,\.]\d{2})',
                    ]
                    for pattern in price_patterns:
                        matches = re.findall(pattern, content)
                        if matches:
                            price_text = matches[0]
                            price = parse_price_text(price_text)
                            if price:
                                print(f"Found price (method 5): {price_text} -> {price}")
                                break
                except Exception as e:
                    print(f"Method 5 failed: {e}")

            context.close()
            browser.close()

            if price is not None:
                print(f"Successfully fetched price: {price}€")
            else:
                print(f"Could not find price for ASIN: {asin}")

            return (price, image_url)

    except Exception as e:
        print(f"Error fetching data for ASIN {asin}: {e}")
        return (None, None)


def parse_price_text(price_text):
    """
    Parse price text into float

    Args:
        price_text (str): Price string like "19,99 €" or "€19.99"

    Returns:
        float: Price value or None if parsing fails
    """
    try:
        # Remove currency symbols and extra whitespace
        cleaned = price_text.replace('€', '').replace('EUR', '').strip()

        # Replace comma with dot for German prices
        cleaned = cleaned.replace(',', '.')

        # Remove any remaining non-numeric characters except dot
        cleaned = re.sub(r'[^\d\.]', '', cleaned)

        # Convert to float
        price = float(cleaned)

        return price
    except Exception as e:
        print(f"Error parsing price text '{price_text}': {e}")
        return None


# Test function
if __name__ == "__main__":
    # Test with a sample ASIN
    test_asin = "B0CQVMZBBG"  # Replace with actual ASIN
    price, image_url = fetch_amazon_price(test_asin)
    print(f"\nFinal result: Price: {price}€, Image: {image_url}")
