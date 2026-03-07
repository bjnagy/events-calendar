import asyncio
from playwright.async_api import async_playwright
import extruct
from bs4 import BeautifulSoup, NavigableString
import re
import json
import sys
import time

WINDOWS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def run_report(url):
    response = asyncio.run(capture_traffic(url))
    results = analyze_results(response)
    return results

async def capture_traffic(url, timeout=10):
    async with async_playwright() as p:
        # Launch browser and create a new page
        #browser = await p.chromium.launch(headless=True)
        #browser = await p.chromium.launch(headless=True, args=["--headless=new"])
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--disable-software-rasterizer"]
        )
        context = await browser.new_context(
            offline=False,
            ignore_https_errors=True,
            user_agent=WINDOWS_UA,
            extra_http_headers={
                "Sec-CH-UA-Platform": '"Windows"',
                "Sec-CH-UA-Platform-Version": '"13.0.0"' #Win11
            },
            service_workers="block" #attempt to block service workers from intercepting requests for fulfillment
        )

        page = await context.new_page()

        # Storage for captured data
        captured_responses = []

        # Define the listener
        async def handle_response(response):
            try:
                # Retrieve details
                url = response.url
                status = response.status
                method = response.request.method
                resource_type = response.request.resource_type
                #request_headers = await response.request.all_headers() # Note: Use request.all_headers() for Request object
                #content_type = request_headers.get('content-type', 'N/A')
                response_content_type = await response.header_value(name='content-type')
            
                # Retrieve body (wrapped in try/except for responses like redirects or binary files)
                if resource_type in ["document", "xhr", "fetch"] and ('text/html' in response_content_type or 'application/json' in response_content_type):
                    try:
                        body = await response.text()
                        if 'application/json' in response_content_type:
                            body = await response.json()
                        else:
                            body = await response.text()
                    except Exception:
                        if 'application/json' in response_content_type:
                            body = await response.text()
                        else:
                            body = "[Could not decode body (binary or redirected)]"

                    captured_responses.append({
                        "url": url,
                        "status": status,
                        "method": method,
                        "resource_type": resource_type,
                        "body": body,
                        "content_type": response_content_type
                    })
            except Exception as e:
                pass # Ignore requests that disappear or fail before capture
        
        #network trace for debugging
        #page.on("request", lambda r: print(f"{r.resource_type}: {r.url}"))
        #page.on("requestfailed", lambda request: print(f"FAILED: {request.url} - Error: {request.failure}"))
        
        # Track pending requests
        pending_requests = set()

        def on_request(request):
            pending_requests.add(request.url)

        def on_request_finished(request):
            pending_requests.discard(request.url)

        def on_request_failed(request):
            pending_requests.discard(request.url)

        page.on("request", on_request)
        page.on("requestfinished", on_request_finished)
        page.on("requestfailed", on_request_failed)
        page.on("response", handle_response)

        # Navigate and wait for the 'load' event (Complete)
        try:
            #print(f"Navigating to {url}...")
            await page.goto(url, wait_until="networkidle", timeout=timeout*1000)
            start_time = time.time()
            while pending_requests and (time.time() - start_time) < timeout:
                print(f"Waiting for {len(pending_requests)} requests...")
                time.sleep(0.5)
            #await page.wait_for_timeout(manual_timeout)
        except:
            print("Timeout exceeded while waiting for networkidle.")
        finally:
            #print(await page.evaluate("navigator.userAgent"))
            await context.close()
            await browser.close()
        return captured_responses
    
        #options for handling networkidle timeouts e.g. with meetup.com
        #1. wait for page element to load
        #await expect(page.locator("h1")).toHaveText("Welcome", timeout=10000)
        #2. wait for specific events
        #await page.goto("https://example.com", wait_until="domcontentloaded")
    

def analyze_results(results):
    for result in results:
        result['metadata'] = []
        result['json'] = []
        result['parsed'] = {}
        if 'text/html' in result['content_type'] and result['body'].strip():

            #search for metadata
            metadata = extruct.extract(result['body'])
            #print(data)
            result['metadata'] = metadata
            #print(metadata)

            soup = BeautifulSoup(result['body'], 'html.parser')

            #search for json
            json_scripts = []
            search_results = soup.find_all('script', {'type': 'application/json'})
            for search_result in search_results:
                try:
                    script_content = search_result.string or search_result.contents[0]
                    json_script = json.loads(script_content)
                except:
                    json_script = {}
                json_scripts.append(json_script)
            result['json'] = json_scripts

            #search for events with design pattern "Event-card"
            events = []
            search_results = soup.find_all(class_=re.compile(r"Event-card", re.I))
            for search_result in search_results:
                #print(search_result)
                event = {}
                for element in search_result.find_all(True):
                    if element.name == 'a':
                        if element.has_attr('class') and element['class']:
                            #print(element['class'], element.get('href', None), element.get_text(strip=True))
                            event[" ".join(element['class'])] = {"href": element.get('href', None), "text": element.get_text(strip=True)}
                        else:
                            print(element['class'], element.get('href', None), element.get_text(strip=True))
                            if element.get_text(strip=True):
                                event[element.get_text(strip=True)] = {"href": element.get('href', None), "text": element.get_text(strip=True)}
                            else:
                                event['link'] = {"href": element.get('href', None), "text": element.get_text(strip=True)}
                    elif element.has_attr('class') and element['class']:
                        #print(element['class'], element.get_text(strip=True))
                        event[" ".join(element['class'])] = element.get_text(strip=True)
                events.append(event)
            result['parsed']['Event-card'] = events
            #print(events)
        #else:
            #document empty

    return results

def print_results(results):
    for idx, item in enumerate(results):
        print(f"\n--- Request {idx+1} ---")
        print(f"URL: {item['url']}")
        print(f"Method: {item['method']}")
        print(f"Status: {item['status']}")
        print(f"Resource Type: {item['resource_type']}")
        print(f"Content Type: {item['content_type']}")
        if "application/json" in item['content_type']:
            body = json.dumps(item['body'])
        else:
            body = item['body']
        print(f"Body (first 100 chars): {body[:100]}...")
        print(f"Metadata (first 100 chars): {json.dumps(item['metadata'])[:100]}...")
        print(f"JSON (first 100 chars): {json.dumps(item['json'])[:100]}...")
        print(f"Parsed (first 100 chars): {json.dumps(item['parsed'])[:100]}...")
    return

# Run the script
if __name__ == "__main__":
    if len(sys.argv) > 1:
        results = run_report(sys.argv[1])
        print_results(results)