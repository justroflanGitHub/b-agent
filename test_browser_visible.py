#!/usr/bin/env python3
"""
Simple Browser Visibility Test

Tests if browser can launch visibly on the host system.
"""

import asyncio
import sys
import os

async def test_visible_browser():
    """Test launching a visible browser."""
    try:
        print("Testing visible browser launch...")

        # Import playwright (should be available from container testing)
        from playwright.async_api import async_playwright

        print("Launching browser in visible mode...")

        async with async_playwright() as p:
            # Launch browser visibly (not headless)
            browser = await p.chromium.launch(
                headless=False,  # This should make browser visible
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--start-maximized",  # Start maximized
                    "--always-on-top",    # Keep on top
                ]
            )

            print("✅ Browser launched successfully!")
            print("You should see a browser window open and stay on top of other applications.")

            # Create a page and navigate
            page = await browser.new_page()
            await page.goto("https://www.google.com")

            print("✅ Navigated to Google!")
            print("Browser window should be visible and focused.")

            # Wait for user to see it
            await asyncio.sleep(10)

            print("Closing browser...")
            await browser.close()

            print("✅ Test completed successfully!")

    except Exception as e:
        print(f"❌ Browser test failed: {e}")
        print("This is likely due to missing dependencies or system configuration.")
        return False

    return True

if __name__ == "__main__":
    print("Browser Visibility Test")
    print("=" * 30)
    print("This will test if a browser can launch visibly on your system.")
    print("Make sure you have Playwright installed: pip install playwright")
    print("Then run: playwright install chromium")
    print()

    success = asyncio.run(test_visible_browser())

    if success:
        print("\n🎉 SUCCESS: Browser launched visibly!")
        print("The multi-agent browser automation system can run with visible browsers.")
    else:
        print("\n❌ FAILED: Could not launch visible browser.")
        print("You may need to install dependencies or configure your system differently.")
