"""Quick test to see what GLM-4.6v-flash outputs."""
import asyncio, aiohttp, json

async def test():
    async with aiohttp.ClientSession() as session:
        # Test 1: Simple text
        resp = await session.post('http://192.168.1.5:1234/v1/chat/completions', json={
            "model": "glm-4.6v-flash",
            "messages": [{"role": "user", "content": "Say hello in JSON format"}],
            "max_tokens": 100
        })
        data = await resp.json()
        print("=== Text test ===")
        print(json.dumps(data, indent=2)[:500])

        # Test 2: Vision-style prompt
        prompt = """You are a GUI agent.

## Output Format
Thought: ...
Action: ...

## Action Space
click(point='<point>x y</point>')
type(content='xxx')
finished(content='summary')

## Task
Click the Submit button at around x=500, y=300."""

        resp2 = await session.post('http://192.168.1.5:1234/v1/chat/completions', json={
            "model": "glm-4.6v-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300
        })
        data2 = await resp2.json()
        print("\n=== Vision prompt test ===")
        print(json.dumps(data2, indent=2)[:1000])

        # Test 3: List models
        resp3 = await session.get('http://192.168.1.5:1234/v1/models')
        data3 = await resp3.json()
        print("\n=== Models ===")
        print(json.dumps(data3, indent=2)[:500])

asyncio.run(test())
