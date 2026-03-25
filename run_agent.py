#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Browser Agent CLI - Command-line interface for the browser agent.

Usage:
    python run_agent.py "Search for AI news"
    python run_agent.py --url https://example.com "Fill out the form"
    python run_agent.py --config config.yaml "Extract data from page"
"""

import asyncio
import argparse
import logging
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from browser_agent import BrowserAgent, Config, get_config


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


async def run_task(
    goal: str,
    url: str = None,
    config_path: str = None,
    headless: bool = False,
    verbose: bool = False
):
    """Run a browser automation task."""
    # Load configuration
    config = get_config(config_path)
    
    # Override settings from CLI
    if headless:
        config.browser.headless = True
    if verbose:
        config.logging.level = "DEBUG"
    
    # Ensure directories exist
    config.ensure_directories()
    
    print(f"\n🎯 Browser Agent Starting")
    print(f"   Goal: {goal}")
    if url:
        print(f"   Start URL: {url}")
    print(f"   Headless: {config.browser.headless}")
    print()
    
    async with BrowserAgent(config) as agent:
        # Execute the task
        result = await agent.execute_task(goal, start_url=url)
        
        # Print results
        print("\n" + "=" * 60)
        print("📊 Task Result")
        print("=" * 60)
        print(f"Success: {'✅ Yes' if result.success else '❌ No'}")
        print(f"Execution Time: {result.execution_time:.2f}s")
        print(f"Steps Completed: {len(result.steps)}")
        
        if result.error:
            print(f"Error: {result.error}")
        
        if result.data:
            print(f"Data: {result.data}")
        
        print("\n📋 Execution Steps:")
        for i, step in enumerate(result.steps, 1):
            status = "✅" if step.get("success") else "❌"
            action = step.get("action", "unknown")
            print(f"   {i}. {status} {action}")
            if step.get("error"):
                print(f"      Error: {step['error']}")
        
        print("\n" + "=" * 60)
        
        # Keep browser open for inspection if not headless
        if not config.browser.headless:
            print("\n👀 Browser window remains open for inspection.")
            print("   Press Ctrl+C to close and exit.")
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\n\n👋 Closing browser and exiting...")
        
        return result


async def interactive_mode(config: Config):
    """Run in interactive mode for multiple tasks."""
    print("\n🤖 Browser Agent - Interactive Mode")
    print("=" * 40)
    print("Enter tasks to execute. Type 'quit' to exit.")
    print()
    
    async with BrowserAgent(config) as agent:
        while True:
            try:
                # Get task from user
                goal = input("🎯 Enter task: ").strip()
                
                if goal.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not goal:
                    continue
                
                # Get optional URL
                url = input("🌐 Start URL (optional): ").strip()
                if not url:
                    url = None
                
                # Execute task
                result = await agent.execute_task(goal, start_url=url)
                
                print(f"\n{'✅' if result.success else '❌'} Task {'completed' if result.success else 'failed'}")
                print(f"   Time: {result.execution_time:.2f}s")
                print()
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Browser Agent - AI-powered browser automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_agent.py "Search for AI news"
    python run_agent.py --url https://example.com "Fill out the form"
    python run_agent.py --headless "Extract data from page"
    python run_agent.py --interactive
        """
    )
    
    parser.add_argument(
        "goal",
        nargs="?",
        help="Task goal to execute"
    )
    parser.add_argument(
        "--url", "-u",
        default="https://google.com",
        help="Starting URL (default: https://google.com)"
    )
    parser.add_argument(
        "--config", "-c",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level)
    
    # Load config
    config = get_config(args.config)
    if args.headless:
        config.browser.headless = True
    
    # Run
    if args.interactive:
        asyncio.run(interactive_mode(config))
    elif args.goal:
        asyncio.run(run_task(
            args.goal,
            url=args.url,
            config_path=args.config,
            headless=args.headless,
            verbose=args.verbose
        ))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
