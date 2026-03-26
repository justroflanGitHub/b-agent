#!/usr/bin/env python3
"""
Simple HTTP server for serving test pages locally.
Used for testing browser agent capabilities.

Usage:
    python server.py [--port PORT] [--host HOST]

Default: http://localhost:8080
"""

import http.server
import socketserver
import argparse
import sys
from pathlib import Path


class TestPageHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for test pages with CORS support."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(description='Start a local HTTP server for test pages')
    parser.add_argument('--port', type=int, default=8080, help='Port (default: 8080)')
    parser.add_argument('--host', type=str, default='localhost', help='Host (default: localhost)')
    args = parser.parse_args()
    
    try:
        with socketserver.TCPServer((args.host, args.port), TestPageHandler) as httpd:
            url = f"http://{args.host}:{args.port}"
            print("\n" + "=" * 60)
            print("  Browser Agent Test Pages Server")
            print("=" * 60)
            print(f"\n  Server: {url}")
            print("\n  Test Pages:")
            print(f"    - Form Filling:      {url}/form_filling/")
            print(f"    - Data Extraction:   {url}/data_extraction/")
            print(f"    - Web Scraping:      {url}/web_scraping/")
            print(f"    - Search & Research: {url}/search_research/")
            print(f"    - Workflow:          {url}/workflow_automation/")
            print(f"    - E-commerce:        {url}/ecommerce/")
            print(f"    - UI Testing:        {url}/ui_testing/")
            print("\n  Press Ctrl+C to stop")
            print("=" * 60 + "\n")
            httpd.serve_forever()
    except OSError as e:
        if e.errno == 98:
            print(f"Error: Port {args.port} already in use. Try --port {args.port + 1}")
        else:
            print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == '__main__':
    main()
