import asyncio
import csv
import os
import re
import json
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# List of e-commerce domains to crawl
DOMAINS = [
    "https://www.amazon.com",
    "https://www.flipkart.com",
    "https://www.meesho.com",
    "https://www.ebay.com",
    "https://www.target.com",
    "https://www.alibaba.com",
    "https://www.snapdeal.com",
    "https://www.shopclues.com",
    "https://www.rakuten.com",
    "https://www.jd.com",
    "https://www.lazada.com",
    "https://www.otto.de",
    "https://www.zalando.com",
    "https://www.ajio.com",
    "https://www.snapdeal.com",
    "https://paytmmall.com",
    "https://www.nykaa.com",
    "https://www.lenskart.com",
    "https://www.firstcry.com",
    "https://storeily.com",
    "https://www.bewakoof.com"
]

# Patterns to identify product pages dynamically
PRODUCT_PATTERNS = [r"/product/",r"/products/", r"/item/", r"/p/", r"/dp/", r"/shop/",r"/babyhug",r"/hooper",r"/john-jacobs"]

# CSV & JSON file paths
CSV_FILE = os.path.join(os.getcwd(), "output.csv")
JSON_FILE = os.path.join(os.getcwd(), "output.json")

# User-Agent rotation to avoid blocking
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
]

visited_urls = set()


def is_product_url(url):
    """Check if the URL matches product patterns dynamically."""
    return any(re.search(pattern, url) for pattern in PRODUCT_PATTERNS)


async def fetch(session, url):
    """Fetch a static HTML page asynchronously."""
    headers = {"User-Agent": USER_AGENTS[len(visited_urls) % len(USER_AGENTS)]}
    try:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status == 200:
                return await response.text()
            else:
                print(f"⚠️ Failed {url} - Status {response.status}")
    except Exception as e:
        print(f"❌ Error fetching {url}: {e}")
    return None


async def crawl_static_site(domain):
    """Crawl static sites to find product URLs and handle pagination."""
    async with aiohttp.ClientSession() as session:
        html = await fetch(session, domain)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        product_links = []

        for link in soup.find_all("a", href=True):
            url = link["href"]
            full_url = urljoin(domain, url)

            if full_url not in visited_urls and is_product_url(full_url):
                visited_urls.add(full_url)
                product_links.append({"Website": domain, "Product URL": full_url})

        return product_links


async def crawl_dynamic_site(domain):
    """Use Playwright to crawl JavaScript-heavy sites with infinite scrolling."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(domain, timeout=30000)
            await asyncio.sleep(3)  # Wait for dynamic content to load

            # Handle infinite scrolling
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # Extract links dynamically
            links = await page.eval_on_selector_all("a", "elements => elements.map(e => e.href)")
            product_links = [{"Website": domain, "Product URL": link} for link in links if is_product_url(link) and link not in visited_urls]
            visited_urls.update([link["Product URL"] for link in product_links])

            await browser.close()
            return product_links
        except Exception as e:
            print(f"❌ Error with Playwright on {domain}: {e}")
            await browser.close()
            return []


async def main():
    """Main function to start crawling multiple domains."""
    print("🚀 Crawling started...")
    tasks = [crawl_dynamic_site(domain) if "meesho" in domain or "flipkart" in domain else crawl_static_site(domain) for domain in DOMAINS]
    results = await asyncio.gather(*tasks)
    flattened_results = [item for sublist in results for item in sublist]

    with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["Website", "Product URL"])
        writer.writeheader()
        writer.writerows(flattened_results)

    with open(JSON_FILE, "w", encoding="utf-8") as file:
        json.dump(flattened_results, file, indent=4)

    print(f"✅ Crawling complete! Results saved to {CSV_FILE} and {JSON_FILE}")


if __name__ == "__main__":
    asyncio.run(main())