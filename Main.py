from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright
import re, asyncio

app = FastAPI()

PRICE_RE = re.compile(r'(?:£|€|\$)\s?(\d{1,4}(?:[.,]\d{1,2})?)')

def parse_price(text):
    if not text:
        return None
    m = PRICE_RE.search(text.replace(',', ''))
    return float(m.group(1)) if m else None

async def scrape_event(event_url: str, zones_expected=None):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await browser.new_context(locale="en-GB", timezone_id="Europe/London")
        page = await ctx.new_page()
        await page.goto(event_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        # zone kartlarını bul
        zone_cards = page.locator("[data-testid*='zone'], [class*='Zone']")
        count = await zone_cards.count()
        results = []

        for i in range(count):
            el = zone_cards.nth(i)
            try:
                name = (await el.inner_text()).strip()
            except:
                continue
            if not name:
                continue

            # ilgili zone’daki fiyatları oku
            texts = await el.all_inner_texts()
            prices = [parse_price(t) for t in texts if parse_price(t)]
            if not prices:
                continue

            # burada fiyat listelerini ayrıştıracağız
            min2 = min(prices)   # TODO: quantity=2 filtrelemesi yapılabilir
            min4 = min(prices)   # TODO: sadece 4’lü ilanlar için filtre

            results.append({
                "zone_name": name,
                "min2": min2,
                "min4": min4,
                "has2": min2 is not None,
                "has4": min4 is not None
            })

        await ctx.close()
        await browser.close()
        return results

@app.post("/")
async def root(req: Request):
    body = await req.json()
    event_url = body.get("event_url", "")
    zones = body.get("zones", None)
    if not event_url:
        return JSONResponse([], status_code=200)
    data = await scrape_event(event_url, zones)
    return JSONResponse(data, status_code=200)
