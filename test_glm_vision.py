"""Test GLM-4.6v-flash with actual screenshot."""
import asyncio, aiohttp, json, base64

async def test():
    # Take a screenshot of a test page
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto("http://localhost:8765/form_filling/index.html")
        await page.wait_for_load_state("networkidle")
        screenshot_bytes = await page.screenshot()
        await browser.close()
    
    img_b64 = base64.b64encode(screenshot_bytes).decode()
    
    async with aiohttp.ClientSession() as session:
        prompt = """You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format
```
Thought: ...
Action: ...
```

## Action Space
click(point='<point>x y</point>')  # Click at pixel coordinates in the screenshot image.
fill_field(point='<point>x y</point>', field_label='label', field_value='value')
type(content='xxx')
press_enter()
scroll(direction='down')
finished(content='summary')

## Note
- Write a small plan in Thought, then summarize your next action in one sentence.
- For fill_field, field_value must be ONLY the short value to type (e.g. "John"), NEVER the full task text.
- Coordinates are absolute pixel positions in the screenshot image. (0,0) is top-left.

## Task
Fill in the First Name field with "John".

## Action History
None yet."""

        resp = await session.post('http://192.168.1.5:1234/v1/chat/completions', json={
            "model": "glm-4.6v-flash",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            ]}],
            "max_tokens": 500
        }, timeout=aiohttp.ClientTimeout(total=120))
        data = await resp.json()
        
        choice = data["choices"][0]["message"]
        print("=== content ===")
        print(repr(choice.get("content", "")))
        print("\n=== reasoning_content ===")
        print(repr(choice.get("reasoning_content", "")[:500]))

asyncio.run(test())
