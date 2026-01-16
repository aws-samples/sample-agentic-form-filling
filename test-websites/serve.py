#!/usr/bin/env python3
"""
Simple HTTP server for serving test websites locally.
Serves each website on a different port.
"""

import argparse
import http.server
import socketserver
import threading
from functools import partial
from pathlib import Path

SITES = {
    "website1-airlines": 8001,
    "website2-seatmap": 8002,
    "website3-spa": 8003,
    "website4-dialogs": 8004,
    "website5-iframes": 8005,
    "website6-popups": 8006,
}


class CORSHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler with CORS support."""

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()


def serve_site(site_dir: Path, port: int, site_name: str):
    """Serve a single site on the specified port."""
    # Use partial to pass directory to handler - thread-safe approach
    handler = partial(CORSHTTPRequestHandler, directory=str(site_dir))

    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"  {site_name}: http://localhost:{port}")
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Serve test websites locally")
    parser.add_argument(
        "--site",
        choices=list(SITES.keys()),
        help="Serve only this site (default: all sites)",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port to serve on (only used with --site)",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).parent

    if args.site:
        # Serve single site
        site_dir = base_dir / args.site
        port = args.port or SITES[args.site]
        print(f"Serving {args.site} at http://localhost:{port}")
        serve_site(site_dir, port, args.site)
    else:
        # Serve all sites
        print("Starting test website servers...")
        print()
        threads = []
        for site, port in SITES.items():
            site_dir = base_dir / site
            if site_dir.exists():
                thread = threading.Thread(
                    target=serve_site, args=(site_dir, port, site), daemon=True
                )
                thread.start()
                threads.append(thread)
            else:
                print(f"  {site}: Directory not found, skipping")

        print()
        print("Press Ctrl+C to stop all servers")
        try:
            # Keep main thread alive
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            print("\nShutting down servers...")


if __name__ == "__main__":
    main()
