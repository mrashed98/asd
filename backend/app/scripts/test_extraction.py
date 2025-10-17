import asyncio
import sys
import argparse
from typing import List

from app.scraper.arabseed import ArabSeedScraper
from app.models import ContentType


async def run(query: str, quality: str) -> int:
    logs: List[str] = []

    def log_callback(message: str) -> None:
        # Keep logs in memory and also print for real-time visibility
        logs.append(message)
        print(message)

    async with ArabSeedScraper() as scraper:
        print(f"Searching for: {query}")
        results = await scraper.search(query)
        if not results:
            print("No search results found.")
            return 2

        # Prefer movies and exact/contains match
        movie_results = [r for r in results if r.type == ContentType.MOVIE]
        picked = None
        for r in movie_results or results:
            if query.strip() in r.title:
                picked = r
                break
        if not picked:
            picked = (movie_results or results)[0]

        print(f"Picked: {picked.title}")
        print(f"URL: {picked.arabseed_url}")
        print(f"Requested quality: {quality}p")

        url = await scraper.get_download_url(
            picked.arabseed_url,
            quality=quality,
            log_callback=log_callback,
        )

        if not url:
            print("FAILED: No download URL extracted.")
            return 1

        print("SUCCESS: Direct download URL:")
        print(url)
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Test ArabSeed download URL extraction")
    parser.add_argument("--query", required=False, default="روكي الغلابة")
    parser.add_argument("--quality", required=False, default="1080")
    args = parser.parse_args()

    exit_code = asyncio.run(run(args.query, args.quality))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


