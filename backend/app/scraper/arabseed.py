"""ArabSeed scraper using Playwright."""
import re
import asyncio
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urljoin

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from app.models import ContentType
from app.schemas import SearchResult


# Ad domains to block/close
AD_DOMAINS = [
    "obqj2.com",
    "68s8.com", 
    "cm65.com",
    "abstractdemonicsilence.com",
]


class ArabSeedScraper:
    """ArabSeed content scraper."""
    
    def __init__(self):
        """Initialize scraper."""
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
        
    async def start(self):
        """Start browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        
    async def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
            
    async def search(self, query: str, content_type: str = None) -> List[SearchResult]:
        """Search ArabSeed for content.
        
        Args:
            query: Search query string
            content_type: Filter by content type ('series' or 'movies')
            
        Returns:
            List of search results
        """
        if not self.context:
            await self.start()
            
        page = await self.context.new_page()
        
        try:
            # Navigate to search page with content type filter
            if content_type == "series":
                search_url = f"https://a.asd.homes/find/?word={query}&type=series"
            elif content_type == "movies":
                search_url = f"https://a.asd.homes/find/?word={query}&type=movies"
            else:
                search_url = f"https://a.asd.homes/find/?word={query}&type="
            
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for results with more generic selectors
            try:
                await page.wait_for_selector(".item, .search-item, [class*='item'], .box, [class*='box']", timeout=10000)
            except:
                # Fallback: wait for any content
                await page.wait_for_timeout(3000)
            
            # Extract results with more generic selectors
            results = await page.evaluate('''() => {
                const items = [];
                const selectors = [
                    'a.movie__block',
                    '.item a',
                    '.search-item a', 
                    '[class*="item"] a',
                    '.box a',
                    '[class*="box"] a',
                    'a[href*="/مسلسل-"]',
                    'a[href*="/movie-"]'
                ];
                
                const processedUrls = new Set();
                
                selectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(card => {
                        const href = card.href || '';
                        if (!href || processedUrls.has(href)) return;
                        processedUrls.add(href);
                        
                        // Try multiple selectors for title
                        const title = card.querySelector('h3')?.textContent?.trim() 
                                   || card.querySelector('.movie__title')?.textContent?.trim()
                                   || card.querySelector('img')?.alt?.trim()
                                   || card.textContent?.trim() || '';
                        
                        const badge = card.querySelector('.mv__pro__type')?.textContent?.trim() 
                                   || card.querySelector('.mv__type')?.textContent?.trim()
                                   || card.querySelector('.__genre')?.textContent?.trim() || '';
                        
                        const img = card.querySelector('img');
                        const posterUrl = img?.src || img?.dataset?.src || '';
                        
                        // Determine content type from URL
                        let contentType = 'movie';
                        if (href.includes('/مسلسل-') || href.includes('/selary/')) {
                            contentType = 'series';
                        }
                        
                        if (title && href && title.length > 2) {
                            items.push({
                                title: title,
                                badge: badge,
                                arabseed_url: href,
                                poster_url: posterUrl,
                                type: contentType
                            });
                        }
                    });
                });
                
                return items;
            }''')
            
            # Filter and classify results
            import logging
            logger = logging.getLogger(__name__)

            search_results = []
            query_lower = query.lower().strip()

            logger.info(f"Raw search results count: {len(results)}")
            for i, result in enumerate(results):
                logger.info(f"Result {i+1}: {result['title']} (type: {result.get('type', 'unknown')})")
                title_lower = result['title'].lower()

                # Validate that the title contains the search query
                # This filters out unrelated results
                if query_lower not in title_lower:
                    logger.info(f"  -> Filtered out (query not in title)")
                    continue

                # Use the type from JavaScript extraction, fallback to classification
                if 'type' in result and result['type'] in ['series', 'movie']:
                    content_type = ContentType.SERIES if result['type'] == 'series' else ContentType.MOVIE
                else:
                    content_type = self._classify_content(result['badge'], result['arabseed_url'], result['title'])
                
                search_results.append(SearchResult(
                    title=result['title'],
                    type=content_type,
                    arabseed_url=result['arabseed_url'],
                    poster_url=result['poster_url'] if result['poster_url'] else None,
                    badge=result['badge'] if result['badge'] else None,
                ))

            logger.info(f"After filtering: {len(search_results)} results")

            # Deduplicate series results by grouping seasons
            search_results = self._deduplicate_series(search_results)

            logger.info(f"After deduplication: {len(search_results)} results")

            return search_results
            
        finally:
            await page.close()
            
    def _deduplicate_series(self, search_results: List[SearchResult]) -> List[SearchResult]:
        """Deduplicate series by removing season-specific duplicates.

        When ArabSeed returns multiple results for the same series (e.g., Season 1, Season 2),
        we keep only one entry - preferring the one without season number in the title.

        Args:
            search_results: List of search results

        Returns:
            Deduplicated list of search results
        """
        # Group results by base title (removing season indicators)
        series_map = {}
        movies = []

        for result in search_results:
            if result.type == ContentType.MOVIE:
                movies.append(result)
                continue

            # Extract base title by removing season patterns
            base_title = re.sub(
                r'\s*(الموسم|الحلقة|season|episode)\s*(الأول|الاول|الثاني|الثالث|الرابع|الخامس|السادس|السابع|الثامن|التاسع|العاشر|\d+)',
                '',
                result.title,
                flags=re.IGNORECASE
            ).strip()

            # Normalize the base title for grouping
            normalized_title = base_title.lower()

            if normalized_title not in series_map:
                series_map[normalized_title] = result
            else:
                # Prefer the result without season number in title
                # (it's usually the main series page)
                current_has_season = bool(re.search(
                    r'(الموسم|season)\s*(الأول|الاول|الثاني|الثالث|\d+)',
                    result.title,
                    re.IGNORECASE
                ))
                existing_has_season = bool(re.search(
                    r'(الموسم|season)\s*(الأول|الاول|الثاني|الثالث|\d+)',
                    series_map[normalized_title].title,
                    re.IGNORECASE
                ))

                # Replace if current doesn't have season and existing does
                if existing_has_season and not current_has_season:
                    series_map[normalized_title] = result

        # Combine deduplicated series with movies
        return movies + list(series_map.values())

    def _classify_content(self, badge: Optional[str], url: str, title: str = "") -> ContentType:
        """Classify content as movie or series.
        
        Args:
            badge: Content type badge text
            url: Content URL
            title: Content title for additional context
            
        Returns:
            ContentType enum
        """
        # Check title for episode patterns first (most reliable)
        if title:
            # Look for episode patterns in title
            if re.search(r'الحلقة\s*\d+|الموسم\s*(?:الأول|الثاني|الثالث|الرابع|الخامس|\d+)', title, re.IGNORECASE):
                return ContentType.SERIES
            # Look for season patterns
            if re.search(r'season\s*\d+|episode\s*\d+', title, re.IGNORECASE):
                return ContentType.SERIES
                
        # Check badge first
        if badge:
            if re.search(r'مسلسل|Series|TV', badge, re.IGNORECASE):
                return ContentType.SERIES
            if re.search(r'فيلم|Movie', badge, re.IGNORECASE):
                return ContentType.MOVIE
                
        # Check URL patterns
        if re.search(r'/مسلسل-|%D9%85%D8%B3%D9%84%D8%B3%D9%84-', url):
            return ContentType.SERIES
        if re.search(r'/فيلم-|%D9%81%D9%8A%D9%84%D9%85-', url):
            return ContentType.MOVIE
            
        # Default to movie
        return ContentType.MOVIE
        

    async def get_seasons(self, url: str) -> List[Dict[str, Any]]:
        """Discover available seasons for a series or episode URL.

        Uses the exact flow we discovered through browser testing:
        1. Navigate to the page
        2. Click anywhere to trigger ad overlays first
        3. Click on season dropdown to open it
        4. Extract seasons from dropdown options

        Returns a list of { number: int, url: str | None } sorted by number.
        """
        if not self.context:
            await self.start()

        page = await self.context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Step 1: Click anywhere on the page to trigger ad overlays first
            try:
                await page.click('body', timeout=5000)
                await page.wait_for_timeout(1000)  # Wait for ad overlay to appear
            except Exception:
                pass  # Continue even if this fails
            
            # Step 2: Click on the season dropdown button to open it
            try:
                # Look for the season dropdown button with class 'filter__bttn'
                await page.click('.filter__bttn', timeout=5000)
                await page.wait_for_timeout(1000)  # Wait for dropdown to open
            except Exception:
                # If dropdown click fails, try alternative selectors
                try:
                    # Try clicking on any element that contains season text
                    season_buttons = await page.query_selector_all('*')
                    for button in season_buttons:
                        text = await button.text_content()
                        if text and ('الموسم' in text or 'season' in text.lower()):
                            try:
                                await button.click()
                                await page.wait_for_timeout(1000)
                                break
                            except Exception:
                                continue
                except Exception:
                    pass  # Continue with static extraction if all clicks fail

            # Step 3: Extract seasons from the dropdown structure
            seasons = await page.evaluate('''() => {
                const results = [];
                const seasonWordToNum = {
                  'الأول': 1, 'الاول': 1,
                  'الثاني': 2,
                  'الثالث': 3,
                  'الرابع': 4,
                  'الخامس': 5,
                  'السادس': 6,
                  'السابع': 7,
                  'الثامن': 8,
                  'التاسع': 9,
                  'العاشر': 10,
                };

                const textToNumber = (txt) => {
                  if (!txt) return null;
                  txt = txt.trim();
                  
                  // Arabic word mapping
                  for (const [w,n] of Object.entries(seasonWordToNum)) {
                    if (txt.includes(w)) return n;
                  }
                  
                  // Extract digits that appear after 'الموسم'
                  const seasonMatch = txt.match(/الموسم\s+(\d+)/i);
                  if (seasonMatch) {
                    const num = parseInt(seasonMatch[1], 10);
                    if (num >= 1 && num <= 20) return num;
                  }
                  
                  return null;
                };

                // Look for the seasons list container
                const seasonsList = document.querySelector('#seasons__list, .list__sub__cats');
                if (seasonsList) {
                  // Extract from dropdown options (li elements in the seasons dropdown)
                  seasonsList.querySelectorAll('li').forEach(li => {
                    const span = li.querySelector('span');
                    if (span) {
                      const text = span.textContent.trim();
                      if (/الموسم/.test(text)) {
                        const num = textToNumber(text);
                        if (num && !results.some(r => r.number === num)) {
                          results.push({ number: num, url: null });
                        }
                      }
                    }
                  });

                  // Also extract from season dropdown button text
                  const seasonButton = seasonsList.querySelector('.filter__bttn b');
                  if (seasonButton) {
                    const buttonText = seasonButton.textContent.trim();
                    if (/الموسم/.test(buttonText)) {
                      const num = textToNumber(buttonText);
                      if (num && !results.some(r => r.number === num)) {
                        results.push({ number: num, url: null });
                      }
                    }
                  }
                }

                return results.sort((a,b) => a.number - b.number);
            }''')

            # Normalize to expected list of dicts
            normalized: List[Dict[str, Any]] = []
            if isinstance(seasons, list):
                for s in seasons:
                    try:
                        n = int(s.get('number'))
                        href = s.get('url') or None
                        normalized.append({ 'number': n, 'url': href })
                    except Exception:
                        continue

            return normalized
        finally:
            await page.close()

    def _extract_series_name_from_url(self, url: str) -> str:
        """Extract series name from ArabSeed URL.
        
        Args:
            url: ArabSeed series or episode URL
            
        Returns:
            Extracted series name for searching
        """
        import urllib.parse
        import re
        
        # Decode URL if it's encoded
        try:
            decoded_url = urllib.parse.unquote(url)
        except:
            decoded_url = url
        
        # Extract series name from URL patterns
        # Pattern 1: /مسلسل-series-name-الموسم-...
        series_match = re.search(r'/مسلسل-([^-]+(?:-[^-]+)*?)-الموسم', decoded_url)
        if series_match:
            series_name = series_match.group(1).replace('-', ' ')
            return series_name
        
        # Pattern 2: /series-name-الموسم-... (but not domain parts)
        series_match = re.search(r'/([^/.-]+(?:-[^/.-]+)*?)-الموسم', decoded_url)
        if series_match:
            series_name = series_match.group(1).replace('-', ' ')
            return series_name
        
        # Pattern 3: /مسلسل-series-name/
        series_match = re.search(r'/مسلسل-([^/]+)', decoded_url)
        if series_match:
            series_name = series_match.group(1).replace('-', ' ')
            return series_name
        
        # Fallback: extract from path segments
        path_parts = decoded_url.split('/')
        for part in path_parts:
            if (part and not part.startswith('http') and 
                'الموسم' not in part and 'الحلقة' not in part and
                '.' not in part and ':' not in part):
                # Clean up the part
                clean_part = part.replace('-', ' ').strip()
                if clean_part and len(clean_part) > 2:
                    return clean_part
        
        # Ultimate fallback
        return "series"

    async def get_episodes(self, series_url: str) -> List[Dict[str, Any]]:
        """Get all episodes for a series using the corrected approach.
        
        Corrected approach based on successful browser automation:
        1. Search for the series with type filter
        2. Open the series item (parent series page)
        3. Extract available seasons from dropdown
        4. Re-search with season-specific queries for each season
        5. Open the first episode of each season
        6. Extract episode list from ul.episodes__list.boxs__wrapper.d__flex.flex__wrap structure
        
        Args:
            series_url: URL of the series (used to extract series name)
            
        Returns:
            List of episode dictionaries with season, episode, title, and url
        """
        # Ensure context is available
        if not self.context:
            await self.start()
            
        page = await self.context.new_page()
        
        try:
            import urllib.parse
            
            # Extract series name from series URL for searching
            series_name = self._extract_series_name_from_url(series_url)
            
            # Step 1: Search for the series with type filter
            print(f"🔍 Step 1: Searching for '{series_name}' with series type filter...")
            
            # Navigate to series search URL
            encoded_query = urllib.parse.quote(series_name)
            series_search_url = f"https://a.asd.homes/find/?word={encoded_query}&type=series"
            
            print(f"   Search URL: {series_search_url}")
            await page.goto(series_search_url, wait_until="domcontentloaded", timeout=30000)
            
            # Handle ad overlays
            try:
                await page.click('body', timeout=5000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            
            # Extract search results
            search_results = await page.evaluate(f'''() => {{
                const results = [];
                const resultItems = document.querySelectorAll('.item, .search-item, [class*="item"], .box, [class*="box"]');
                
                resultItems.forEach((item, index) => {{
                    const link = item.querySelector('a');
                    if (!link || !link.href) return;
                    
                    const href = link.href;
                    const title = (link.textContent || '').trim();
                    
                    // Filter for the target series (not episodes)
                    const targetSeries = '{series_name}'.toLowerCase();
                    const isTargetSeries = title.toLowerCase().includes(targetSeries) || 
                                          href.toLowerCase().includes(targetSeries.replace(' ', '-')) ||
                                          href.toLowerCase().includes(targetSeries.replace(' ', '_'));
                    
                    // Make sure it's a series, not an episode (no الحلقة in title)
                    const isSeries = !title.includes('الحلقة') && !href.includes('الحلقة');
                    
                    if (isTargetSeries && isSeries) {{
                        results.push({{
                            title: title,
                            url: href
                        }});
                    }}
                }});
                
                return results;
            }}''')
            
            if not search_results:
                print("   ❌ No series results found")
                return []
            
            print(f"   ✅ Found {len(search_results)} series results")
            
            # Step 2: Open the series item
            print(f"\n🔍 Step 2: Opening the series item...")
            series_url = search_results[0]['url']
            print(f"   Series URL: {series_url}")
            
            await page.goto(series_url, wait_until="domcontentloaded", timeout=30000)
            
            # Handle ad overlays
            try:
                await page.click('body', timeout=5000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass
            
            # Step 3: Extract available seasons
            print(f"\n🔍 Step 3: Extracting available seasons...")
            seasons = await page.evaluate('''() => {
                const seasons = [];
                const seasonWordToNum = {
                  'الأول': 1, 'الاول': 1,
                  'الثاني': 2,
                  'الثالث': 3,
                  'الرابع': 4,
                  'الخامس': 5,
                  'السادس': 6,
                  'السابع': 7,
                  'الثامن': 8,
                  'التاسع': 9,
                  'العاشر': 10,
                };

                const textToNumber = (txt) => {
                  if (!txt) return null;
                  txt = txt.trim();
                  
                  // Arabic word mapping
                  for (const [w,n] of Object.entries(seasonWordToNum)) {
                    if (txt.includes(w)) return n;
                  }
                  
                  // Extract digits that appear after 'الموسم'
                  const seasonMatch = txt.match(/الموسم\\s+(\\d+)/i);
                  if (seasonMatch) {
                    const num = parseInt(seasonMatch[1], 10);
                    if (num >= 1 && num <= 20) return num;
                  }
                  
                  return null;
                };

                // Look for the seasons list container
                const seasonsList = document.querySelector('#seasons__list, .list__sub__cats');
                if (seasonsList) {
                  // Extract from dropdown options (li elements in the seasons dropdown)
                  seasonsList.querySelectorAll('li').forEach(li => {
                    const span = li.querySelector('span');
                    if (span) {
                      const text = span.textContent.trim();
                      if (/الموسم/.test(text)) {
                        const num = textToNumber(text);
                        if (num && !seasons.some(s => s.number === num)) {
                          seasons.push({ number: num, text: text });
                        }
                      }
                    }
                  });
                }

                return seasons.sort((a,b) => a.number - b.number);
            }''')
            
            print(f"   ✅ Found {len(seasons)} seasons:")
            for season in seasons:
                print(f"      - Season {season['number']}: {season['text']}")
            
            # Step 4: Extract episodes based on number of seasons
            print(f"\n🔍 Step 4: Extracting episodes...")
            all_episodes = []
            
            if len(seasons) == 1:
                # Single season - try to extract episodes directly from the series page
                print(f"   📺 Single season detected, extracting episodes directly from series page...")
                try:
                    # Try to extract episodes from the current series page
                    episodes = await page.evaluate('''() => {
                        const episodes = [];
                        const episodesList = document.querySelector('.episodes__list.boxs__wrapper.d__flex.flex__wrap');
                        
                        if (episodesList) {
                            const episodeItems = episodesList.querySelectorAll('li');
                            episodeItems.forEach((item, index) => {
                                const link = item.querySelector('a');
                                if (link && link.href) {
                                    const title = (link.textContent || '').trim();
                                    const href = link.href;
                                    
                                    // Extract episode number from title or URL
                                    let episodeNumber = index + 1;
                                    const episodeMatch = title.match(/الحلقة\\s*(\\d+)/i) || href.match(/الحلقة[^\\d]*(\\d+)/i);
                                    if (episodeMatch) {
                                        episodeNumber = parseInt(episodeMatch[1], 10);
                                    }
                                    
                                    episodes.push({
                                        season: 1,
                                        episode_number: episodeNumber,
                                        title: title,
                                        url: href
                                    });
                                }
                            });
                        }
                        
                        return episodes;
                    }''')
                    
                    if episodes:
                        all_episodes.extend(episodes)
                        print(f"   ✅ Found {len(episodes)} episodes directly from series page")
                    else:
                        print(f"   ❌ No episodes found on series page, falling back to search method")
                        # Fall back to search method for single season
                        season_info = seasons[0]
                        season_num = season_info['number']
                        season_text = season_info['text']
                        
                        print(f"   📺 Fallback: Processing Season {season_num}: {season_text}")
                        
                        # Create season-specific search query
                        season_query = f"{series_name} {season_text}"
                        encoded_query = urllib.parse.quote(season_query)
                        season_search_url = f"https://a.asd.homes/find/?word={encoded_query}&type="
                        
                        print(f"      Season search URL: {season_search_url}")
                        
                        # Navigate to season-specific search
                        await page.goto(season_search_url, wait_until="domcontentloaded", timeout=30000)
                        
                        # Handle ad overlays
                        try:
                            await page.click('body', timeout=5000)
                            await page.wait_for_timeout(1000)
                        except Exception:
                            pass
                        
                        # Find and open the first episode
                        print(f"      🔍 Finding first episode for Season {season_num}...")
                        
                        first_episode_url = await page.evaluate(f'''() => {{
                            // Look for episode links in search results
                            const resultItems = document.querySelectorAll('.item, .search-item, [class*="item"], .box, [class*="box"]');
                            
                            for (let item of resultItems) {{
                                const link = item.querySelector('a');
                                if (!link || !link.href) continue;
                                
                                const href = link.href;
                                const title = (link.textContent || '').trim();
                                
                                // Check if this is an episode (contains الحلقة)
                                if (title.includes('الحلقة') || href.includes('الحلقة')) {{
                                    // Filter for target series episodes only
                                    const targetSeries = '{series_name}'.toLowerCase();
                                    const isTargetSeries = title.toLowerCase().includes(targetSeries) || 
                                                          href.toLowerCase().includes(targetSeries.replace(' ', '-')) ||
                                                          href.toLowerCase().includes(targetSeries.replace(' ', '_'));
                                    
                                    if (isTargetSeries) {{
                                        return href;
                                    }}
                                }}
                            }}
                            return null;
                        }}''')
                        
                        if first_episode_url:
                            print(f"      ✅ Found first episode: {first_episode_url}")
                            
                            # Open the first episode to get the episode list
                            await page.goto(first_episode_url, wait_until="domcontentloaded", timeout=30000)
                            
                            # Handle ad overlays
                            try:
                                await page.click('body', timeout=5000)
                                await page.wait_for_timeout(1000)
                            except Exception:
                                pass
                            
                            # Extract episodes from the episode page
                            episodes = await page.evaluate('''() => {
                                const episodes = [];
                                const episodesList = document.querySelector('.episodes__list.boxs__wrapper.d__flex.flex__wrap');
                                
                                if (episodesList) {
                                    const episodeItems = episodesList.querySelectorAll('li');
                                    episodeItems.forEach((item, index) => {
                                        const link = item.querySelector('a');
                                        if (link && link.href) {
                                            const title = (link.textContent || '').trim();
                                            const href = link.href;
                                            
                                            // Extract episode number from title or URL
                                            let episodeNumber = index + 1;
                                            const episodeMatch = title.match(/الحلقة\\s*(\\d+)/i) || href.match(/الحلقة[^\\d]*(\\d+)/i);
                                            if (episodeMatch) {
                                                episodeNumber = parseInt(episodeMatch[1], 10);
                                            }
                                            
                                            episodes.push({
                                                season: 1,
                                                episode_number: episodeNumber,
                                                title: title,
                                                url: href
                                            });
                                        }
                                    });
                                }
                                
                                return episodes;
                            }''')
                            
                            if episodes:
                                all_episodes.extend(episodes)
                                print(f"      ✅ Found {len(episodes)} episodes from episode page")
                            else:
                                print(f"      ❌ No episodes found on episode page")
                        else:
                            print(f"      ❌ No first episode found for Season {season_num}")
                        
                except Exception as e:
                    print(f"   ❌ Error extracting episodes from series page: {e}")
                    # Continue with the original search method
                    pass
            
            # Multiple seasons - use the original season-specific search method
            if len(seasons) > 1 or len(all_episodes) == 0:
                print(f"   📺 Multiple seasons detected or fallback needed, using season-specific search...")
                for season_info in seasons:
                    season_num = season_info['number']
                    season_text = season_info['text']
                    
                    print(f"\n   📺 Processing Season {season_num}: {season_text}")
                    
                    # Create season-specific search query
                    season_query = f"{series_name} {season_text}"
                    encoded_query = urllib.parse.quote(season_query)
                    season_search_url = f"https://a.asd.homes/find/?word={encoded_query}&type="
                    
                    print(f"      Season search URL: {season_search_url}")
                    
                    # Navigate to season-specific search
                    await page.goto(season_search_url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Handle ad overlays
                    try:
                        await page.click('body', timeout=5000)
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    
                    # Step 5: Find and open the first episode
                    print(f"      🔍 Finding first episode for Season {season_num}...")
                    
                    first_episode_url = await page.evaluate(f'''() => {{
                    // Look for episode links in search results
                    const resultItems = document.querySelectorAll('.item, .search-item, [class*="item"], .box, [class*="box"]');
                    
                    for (let item of resultItems) {{
                        const link = item.querySelector('a');
                        if (!link || !link.href) continue;
                        
                        const href = link.href;
                        const title = (link.textContent || '').trim();
                        
                        // Check if this is an episode (contains الحلقة)
                        if (title.includes('الحلقة') || href.includes('الحلقة')) {{
                            // Filter for target series episodes only
                            const targetSeries = '{series_name}'.toLowerCase();
                            const isTargetSeries = title.toLowerCase().includes(targetSeries) || 
                                                  href.toLowerCase().includes(targetSeries.replace(' ', '-')) ||
                                                  href.toLowerCase().includes(targetSeries.replace(' ', '_'));
                            
                            if (isTargetSeries) {{
                                return href;
                            }}
                        }}
                    }}
                    return null;
                }}''')
                
                    if not first_episode_url:
                        print(f"      ❌ No episode found for Season {season_num}")
                        continue
                    
                    print(f"      ✅ First episode URL: {first_episode_url}")
                    
                    # Step 6: Open the first episode and extract episode list
                    print(f"      🔍 Opening first episode and extracting episode list...")
                    
                    await page.goto(first_episode_url, wait_until="domcontentloaded", timeout=30000)
                    
                    # Handle ad overlays
                    try:
                        await page.click('body', timeout=5000)
                        await page.wait_for_timeout(1000)
                    except Exception:
                        pass
                    
                    # Extract episodes from the episodes list structure
                    episodes = await page.evaluate('''() => {
                        const episodes = [];
                        
                        // Look for the episodes list container - this is the structure we found in browser testing
                        const episodesList = document.querySelector('.episodes__list.boxs__wrapper.d__flex.flex__wrap');
                        if (!episodesList) {
                            console.log('No episodes list found with exact class structure');
                            return episodes;
                        }
                        
                        // Get all LI items from the episodes list
                        const episodeItems = episodesList.querySelectorAll('li');
                        console.log(`Found ${episodeItems.length} episode items in episodes list`);
                        
                        episodeItems.forEach((item, index) => {
                            const link = item.querySelector('a');
                            if (!link) return;
                            
                            const href = link.href;
                            const text = (link.textContent || '').trim();
                            
                            // Extract episode number from link text (الحلقة13, الحلقة12, etc.)
                            let episodeNumber = null;
                            const episodeMatch = text.match(/الحلقة\\s*(\\d+)/i);
                            if (episodeMatch) {
                                episodeNumber = parseInt(episodeMatch[1]);
                            }
                            
                            // Fallback: extract from URL
                            if (!episodeNumber) {
                                const urlMatch = href.match(/الحلقة-(\\d+)/);
                                if (urlMatch) {
                                    episodeNumber = parseInt(urlMatch[1]);
                                }
                            }
                        
                        if (episodeNumber && href) {
                            // Create a title for the episode
                            const title = `الحلقة ${episodeNumber}`;
                            
                            episodes.push({
                                episode_number: episodeNumber,
                                title: title,
                                url: href
                            });
                            
                            console.log(`Episode ${episodeNumber}: ${title} -> ${href}`);
                        }
                    });
                    
                    console.log(`Valid episodes found: ${episodes.length}`);
                    return episodes;
                }''')
                
                print(f"      ✅ Found {len(episodes)} episodes for Season {season_num}")
                
                # Add season number to episodes
                for episode in episodes:
                    episode['season'] = season_num
                    all_episodes.append(episode)
                    print(f"         - Episode {episode['episode_number']}: {episode['title']}")
            
            print(f"\n📊 Final Summary:")
            print(f"   - Total episodes found: {len(all_episodes)}")
            
            episodes_by_season = {}
            for episode in all_episodes:
                season = episode['season']
                if season not in episodes_by_season:
                    episodes_by_season[season] = []
                episodes_by_season[season].append(episode)
            
            for season_num in sorted(episodes_by_season.keys()):
                season_episodes = episodes_by_season[season_num]
                print(f"   - Season {season_num}: {len(season_episodes)} episodes")
            
            return all_episodes
            
        finally:
            await page.close()
            
    async def _extract_episodes_from_links(self, page: Page, series_url: str) -> List[Dict[str, Any]]:
        """Extract episodes from page links as fallback.
        
        Args:
            page: Playwright page
            series_url: Series URL
            
        Returns:
            List of episode dictionaries
        """
        links = await page.evaluate('''() => {
            return Array.from(document.querySelectorAll('a')).map(a => ({
                href: a.href,
                text: (a.textContent || '').trim()
            }));
        }''')
        
        episodes = []
        series_base = urlparse(series_url).path.split('/')[1] if '/' in series_url else ''
        
        for link in links:
            url = link['href']
            text = link['text']
            
            # Match URLs with season/episode patterns
            season_match = re.search(r'الموسم-(?:الاول|الثاني|الثالث|(\d+))', url)
            episode_match = re.search(r'الحلقة-(\d+)', url)
            
            if episode_match and series_base in url:
                season = 1
                if season_match:
                    arabic_to_num = {'الاول': 1, 'الثاني': 2, 'الثالث': 3, 'الرابع': 4}
                    for ar, num in arabic_to_num.items():
                        if ar in url:
                            season = num
                            break
                    if season_match.group(1):
                        season = int(season_match.group(1))
                        
                episodes.append({
                    'season': season,
                    'episode_number': int(episode_match.group(1)),
                    'title': text,
                    'url': url
                })
                
        return episodes
        
    async def get_available_qualities(self, episode_url: str) -> List[str]:
        """Get available quality options for an episode/movie.
        
        Args:
            episode_url: URL of the episode/movie page
            
        Returns:
            List of available qualities (e.g., ['1080', '720', '480'])
        """
        if not self.context:
            await self.start()
            
        page = await self.context.new_page()
        
        try:
            # Navigate to content page
            await page.goto(episode_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            # Find download button and navigate to download page
            download_page_url = await page.evaluate('''() => {
                const downloadBtn = document.querySelector('a.download__btn, a[href*="/download/"]');
                return downloadBtn ? downloadBtn.href : null;
            }''')
            
            if not download_page_url:
                return []
                
            # Navigate to download page
            await page.goto(download_page_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            
            # Extract available qualities and deduplicate
            qualities = await page.evaluate('''() => {
                const qualityElements = document.querySelectorAll('[data-quality]');
                const qualitiesSet = new Set();
                qualityElements.forEach(el => {
                    const quality = el.getAttribute('data-quality');
                    if (quality) qualitiesSet.add(quality);
                });
                return Array.from(qualitiesSet);
            }''')
            
            return sorted([q for q in qualities if q], key=lambda x: int(x), reverse=True)
            
        finally:
            await page.close()
    
    async def get_download_url(self, episode_url: str, quality: str = "1080", max_retries: int = 3, log_callback=None) -> Optional[str]:
        """Get direct download URL for an episode/movie.
        
        Args:
            episode_url: URL of the episode/movie page
            quality: Preferred quality (e.g., '1080', '720', '480')
            max_retries: Maximum retry attempts
            log_callback: Optional callback function for logging progress
            
        Returns:
            Direct download URL or None
        """
        if not self.context:
            await self.start()
            
        def log(message: str):
            if log_callback:
                log_callback(message)
            
        import logging
        logger = logging.getLogger(__name__)
        logger.info(message := f"Starting download URL extraction for: {episode_url}")
        log(message)
            
        for attempt in range(max_retries):
            page = await self.context.new_page()
            download_url = None
            
            try:
                # Step 1: Navigate to movie/episode page
                logger.info(message := f"[Attempt {attempt + 1}/{max_retries}] Step 1: Navigating to content page...")
                log(message)
                log(f"  Target URL: {episode_url}")
                await page.goto(episode_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                current_url = page.url
                log(f"✓ Content page loaded")
                log(f"  Current URL: {current_url}")
                
                # Step 2: Click download button using JavaScript
                logger.info(message := "Step 2: Finding download button...")
                log(message)
                log("  Searching for: a.download__btn or a[href*='/download/']")
                download_page_url = await page.evaluate('''() => {
                    const downloadBtn = document.querySelector('a.download__btn, a[href*="/download/"]');
                    if (downloadBtn) {
                        const url = downloadBtn.href;
                        return url;
                    }
                    return null;
                }''')
                
                if not download_page_url:
                    logger.error(message := "✗ Could not find download button")
                    log(message)
                    continue
                    
                # Navigate to download page
                logger.info(message := f"✓ Found download page, navigating...")
                log(message)
                log(f"  Download page URL: {download_page_url}")
                await page.goto(download_page_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)
                current_url = page.url
                log("✓ Download page loaded")
                log(f"  Current URL: {current_url}")
                
                # Step 3: Select requested quality
                logger.info(message := f"Step 3: Selecting {quality}p quality...")
                log(message)
                log(f"  Searching for: [data-quality='{quality}']")
                
                # Log all available qualities
                available_qualities = await page.evaluate('''() => {
                    const qualities = [];
                    document.querySelectorAll('[data-quality]').forEach(el => {
                        qualities.push(el.getAttribute('data-quality'));
                    });
                    return qualities;
                }''')
                log(f"  Available qualities: {', '.join(available_qualities) if available_qualities else 'None found'}")
                
                quality_clicked = await page.evaluate(f'''() => {{
                    const qualityBox = document.querySelector('[data-quality="{quality}"]');
                    if (qualityBox) {{
                        qualityBox.click();
                        return "{quality}";
                    }}
                    return null;
                }}''')
                
                if not quality_clicked:
                    logger.error(message := f"✗ {quality}p quality not available")
                    log(message)
                    continue
                    
                logger.info(message := f"✓ Selected {quality_clicked}p quality")
                log(message)
                await asyncio.sleep(1)
                
                # Step 4: Click ArabSeed direct server link
                logger.info(message := "Step 4: Finding ArabSeed direct server...")
                log(message)
                log("  Searching for: a.arabseed")
                
                # Log all available server links
                server_links = await page.evaluate('''() => {
                    const links = [];
                    document.querySelectorAll('a').forEach(a => {
                        const text = (a.textContent || '').trim();
                        const classes = a.className || '';
                        if (text.includes('ArabSeed') || text.includes('عرب سيد') || classes.includes('arabseed')) {
                            links.push({
                                text: text.substring(0, 50),
                                class: classes,
                                href: a.href
                            });
                        }
                    });
                    return links;
                }''')
                log(f"  Found {len(server_links)} ArabSeed server links:")
                for link in server_links[:3]:  # Show first 3
                    log(f"    - [{link.get('class', 'no-class')}] {link.get('text', '')} -> {link.get('href', '')[:60]}")
                
                server_clicked = await page.evaluate('''() => {
                    const serverLink = document.querySelector('a.arabseed');
                    if (serverLink) {
                        const url = serverLink.href;
                        window.location.href = url;
                        return url;
                    }
                    return null;
                }''')
                
                if not server_clicked:
                    logger.error(message := "✗ Could not find ArabSeed server link")
                    log(message)
                    continue
                    
                logger.info(message := "✓ Navigating to ArabSeed server...")
                log(message)
                log(f"  Server URL: {server_clicked[:80]}")
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
                current_url = page.url
                log("✓ Server page loaded")
                log(f"  Current URL: {current_url}")
                
                # Step 5: Click "اضغط للتحميل" button using JavaScript to bypass ad overlays
                logger.info(message := "Step 5: Clicking first download button...")
                log(message)
                log("  Searching for: button#start (اضغط للتحميل)")
                
                # Check what buttons are available
                buttons_found = await page.evaluate('''() => {
                    const buttons = [];
                    document.querySelectorAll('button').forEach(btn => {
                        buttons.push({
                            id: btn.id || 'no-id',
                            class: btn.className || 'no-class',
                            text: (btn.textContent || '').trim().substring(0, 30)
                        });
                    });
                    return buttons;
                }''')
                log(f"  Found {len(buttons_found)} buttons on page:")
                for btn in buttons_found[:5]:  # Show first 5
                    log(f"    - [{btn.get('id', 'no-id')}] {btn.get('text', '')}")
                
                first_button_clicked = await page.evaluate('''() => {
                    const button = document.getElementById('start');
                    if (button) {
                        button.click();
                        return true;
                    }
                    return false;
                }''')
                
                if not first_button_clicked:
                    logger.error(message := "✗ Could not find 'اضغط للتحميل' button")
                    log(message)
                    continue
                    
                logger.info(message := "✓ First button clicked, waiting 15 seconds for download link...")
                log(message)
                await asyncio.sleep(15)  # Wait 15 seconds for the final download link to appear
                current_url = page.url
                log("✓ Wait complete, extracting download link")
                log(f"  Current URL: {current_url}")
                
                # Step 6: Extract download link from the updated page
                logger.info(message := "Step 6: Extracting final download link...")
                log(message)
                
                # Debug: Log all download-related links on the page
                all_links = await page.evaluate('''() => {
                    const links = [];
                    document.querySelectorAll('a').forEach(a => {
                        const href = a.href || '';
                        const text = (a.textContent || '').trim();
                        if (href.includes('.mp4') || href.includes('.mkv') || 
                            href.includes('download') || text.includes('تحميل') ||
                            a.id === 'btn' || a.className.includes('download')) {
                            links.push({
                                text: text.substring(0, 50),
                                href: href,
                                id: a.id,
                                className: a.className
                            });
                        }
                    });
                    return links;
                }''')
                
                logger.info(f"Found {len(all_links)} download-related links on page")
                log(f"Found {len(all_links)} download-related links:")
                for link in all_links:
                    log(f"  - [{link.get('id', 'no-id')}] {link.get('text', '')} -> {link.get('href', '')[:80]}")
                
                # Extract the actual download URL (should be .mp4 or .mkv file)
                async def find_direct_link() -> Optional[str]:
                    return await page.evaluate('''() => {
                        // First, try to find direct file download link (highest priority)
                        const directLink = Array.from(document.querySelectorAll('a')).find(a =>
                            a.href && (a.href.includes('.mp4') || a.href.includes('.mkv'))
                        );
                        if (directLink) return directLink.href;

                        // Fallback to #btn.downloadbtn
                        const downloadBtn = document.querySelector('a#btn.downloadbtn, a.downloadbtn');
                        if (downloadBtn) return downloadBtn.href;

                        return null;
                    }''')

                download_url = await find_direct_link()

                if download_url and ('.mp4' in download_url or '.mkv' in download_url):
                    logger.info(message := f"✓ Successfully extracted download URL!")
                    log(message)
                    log(f"Download URL: {download_url[:80]}...")
                    return download_url

                # If we only found an intermediate asd7b page, navigate to it then wait/poll
                if download_url and 'asd7b=1' in download_url and not ('.mp4' in download_url or '.mkv' in download_url):
                    log("Intermediate asd7b link found. Navigating to it and polling for direct link...")
                    try:
                        await page.goto(download_url, wait_until="domcontentloaded", timeout=30000)
                    except Exception as _:
                        pass
                    await asyncio.sleep(2)
                    # Poll up to 30s, every 2s
                    for sec in range(0, 31, 2):
                        direct = await find_direct_link()
                        if direct and ('.mp4' in direct or '.mkv' in direct):
                            logger.info(message := f"✓ Direct link appeared after {sec}s")
                            log(message)
                            log(f"Download URL: {direct[:80]}...")
                            return direct
                        await asyncio.sleep(2)
                    logger.warning(message := "✗ Timed out waiting for direct link after visiting asd7b page")
                    log(message)

                if not download_url:
                    logger.error(message := "✗ Download link not found on final page")
                    log(message)
                    # Take screenshot for debugging
                    try:
                        await page.screenshot(path="/app/data/debug_final_page.png")
                        logger.info("Screenshot saved to /app/data/debug_final_page.png")
                        log("Debug screenshot saved")
                    except:
                        pass
                    
            except Exception as e:
                logger.error(message := f"✗ Attempt {attempt + 1} failed: {str(e)}")
                log(message)
                
            finally:
                await page.close()
                await asyncio.sleep(2)  # Wait before retry
                
        return None
        
    async def _handle_download_flow(self, page: Page):
        """Handle the download flow with timers and ads.
        
        Args:
            page: Playwright page
        """
        # Wait for and handle first timer/button
        for _ in range(2):  # Two possible timer stages
            try:
                # Wait for button to appear (up to 30 seconds for timer)
                button = page.get_by_role('button', name='اضغط للتحميل').or_(
                    page.get_by_role('link', name='اضغط للتحميل')
                ).or_(
                    page.get_by_role('button', name='التحميل الان')
                ).or_(
                    page.get_by_role('link', name='التحميل الان')
                )
                
                await button.first.wait_for(state='visible', timeout=35000)
                
                # Click button and handle popup
                async with page.expect_popup(timeout=3000) as popup_info:
                    try:
                        await button.first.click(timeout=2000)
                        popup = await popup_info.value
                        
                        # Check if it's an ad
                        popup_url = popup.url
                        if any(domain in popup_url for domain in AD_DOMAINS):
                            await popup.close()
                            await asyncio.sleep(1)
                            # Click again after closing ad
                            await button.first.click(timeout=2000)
                    except:
                        pass
                        
                await asyncio.sleep(2)
                
            except Exception as e:
                # No more buttons, download link should be available
                break

