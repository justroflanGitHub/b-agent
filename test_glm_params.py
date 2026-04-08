"""Test GLM-4.6v-flash with different params to get content field populated."""
import asyncio, aiohttp, json, base64

async def test():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:8765/form_filling/index.html")
        await page.wait_for_load_state("networkidle")
        screenshot_bytes = await page.screenshot()
        await browser.close()
    
    img_b64 = base64.b64encode(screenshot_bytes).decode()
    
    prompt = """You are a GUI agent.

## Output Format
Thought: ...
Action: ...

## Action Space
click(point='<point>x y</point>')
type(content='xxx')
finished(content='summary')

## Task
Click on the First Name input field."""

    # Test with and without extra body params
    tests = [
        {"name": "default", "extra": {}},
        {"name": "enable_thinking=false", "extra": {"extra_body": {"enable_thinking": False}}},
        {"name": "do_sample=true", "extra": {"do_sample": True, "temperature": 0.7}},
    ]
    
    async with aiohttp.ClientSession() as session:
        for t in tests:
            payload = {
                "model": "glm-4.6v-flash",
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                ]}],
                "max_tokens": 500,
            }
            payload.update(t["extra"])
            
            try:
                resp = await session.post('http://192.168.1.5:1234/v1/chat/completions', 
                    json=payload, timeout=aiohttp.ClientTimeout(total=120))
                data = await resp.json()
                choice = data["choices"][0]["message"]
                content = choice.get("content", "")
                reasoning = choice.get("reasoning_content", "")[:200]
                print(f"\n=== {t['name']} ===")
                print(f"content: {repr(content[:300])}")
                print(f"reasoning: {repr(reasoning)}")
            except Exception as e:
                print(f"\n=== {t['name']} ERROR: {e} ===")

asyncio.run(test())
