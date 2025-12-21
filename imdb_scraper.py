import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import os
def setup_driver():
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--window-size=1920,1080")
    options.set_capability("pageLoadStrategy", "eager")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(60)
    return driver

def safe_click(driver, element):
    """Safely click an element using JavaScript to avoid click interception errors."""
    try:
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(0.5)
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception as e:
        print(f"Click error: {e}")
        return False





def scrape_amazon_logo(query, driver):
    """Scrape series logo from Amazon Prime via DuckDuckGo search."""
    print(f"Attempting to scrape Amazon Prime logo for: {query}")
    logo_url = ""
    original_window = driver.current_window_handle
    
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Search via DuckDuckGo
        driver.get(f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}+amazon+prime+video")
        time.sleep(2)
        
        try:
            # Find Amazon link
            first_result = driver.find_element(By.CSS_SELECTOR, "a.result__a")
            amazon_url = first_result.get_attribute("href")
            print(f"Found Amazon URL: {amazon_url}")
            driver.get(amazon_url)
            time.sleep(3)
            # Try to find the LOGO (not poster)
            try:
                # Amazon Prime logo - look for images with specific classes or alt text containing show name
                # Example: <img alt="The Boys" class="ljcPsM" src="https://m.media-amazon.com/images/S/pv-target-images/...png">
                img = driver.find_element(By.CSS_SELECTOR, "img.ljcPsM, img[class*='title-logo'], img[data-testid='base-image'][alt]") 
                logo_url = img.get_attribute("src")
                print(f"Found Amazon logo with selector: {logo_url}")
            except:
                # Try to find logo by looking for PNG images (logos are usually PNG)
                try:
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    for i in imgs:
                        src = i.get_attribute("src") or ""
                        alt = i.get_attribute("alt") or ""
                        
                        # Look for PNG images from Amazon's media server with show name in alt
                        if src and "m.media-amazon.com" in src and ".png" in src.lower():
                            # Check if it's likely a logo (has show name in alt, not a poster)
                            if alt and query.lower() in alt.lower():
                                logo_url = src
                                print(f"Found Amazon logo (PNG with alt): {logo_url}")
                                break
                except:
                    pass
                    
        except Exception as e:
            print(f"Amazon search failed: {e}")

    except Exception as e:
        print(f"Error scraping Amazon logo: {e}")
    finally:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(original_window)
        except:
            pass
            
    return logo_url

def scrape_netflix_logo(query, driver):
    """Scrape series logo from Netflix via DuckDuckGo search."""
    print(f"Attempting to scrape Netflix logo for: {query}")
    logo_url = ""
    original_window = driver.current_window_handle
    
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Search via DuckDuckGo
        driver.get(f"https://duckduckgo.com/html/?q=site:netflix.com/in/title/+{query.replace(' ', '+')}")
        time.sleep(2)
        
        try:
            first_result = driver.find_element(By.CSS_SELECTOR, "a.result__a")
            netflix_url = first_result.get_attribute("href")
            print(f"Found Netflix URL: {netflix_url}")
            driver.get(netflix_url)
            time.sleep(3)
            
            # Try to find the LOGO (not poster)
            try:
                # Netflix logo - look for title logo images
                # Example: <img src="https://occ-0-7275-3662.1.nflxso.net/dnm/api/v6/.../logo.webp" alt="" class="default-ltr-iqcdef-cache-1wfyi7w e1e4hbe50">
                logo_img = driver.find_element(By.CSS_SELECTOR, "img.title-logo, img[class*='title-logo'], img.default-ltr-cache, img[class*='e1e4hbe']")
                logo_url = logo_img.get_attribute("src")
                print(f"Found Netflix logo with selector: {logo_url}")
            except:
                # Try to find logo by looking for WebP images from Netflix CDN
                try:
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    for i in imgs:
                        src = i.get_attribute("src") or ""
                        
                        # Look for WebP images from Netflix CDN (logos are usually WebP)
                        if src and "nflxso.net" in src and ".webp" in src.lower():
                            # Avoid poster images (they usually have different patterns)
                            if "title" in src.lower() or "logo" in src.lower():
                                logo_url = src
                                print(f"Found Netflix logo (WebP): {logo_url}")
                                break
                except:
                    pass

        except Exception as e:
             print(f"Netflix search failed: {e}")

    except Exception as e:
        print(f"Error scraping Netflix logo: {e}")
    finally:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(original_window)
        except:
            pass
            
    return logo_url

def scrape_hotstar_logo(query, driver):
    """Scrape series logo from Hotstar via DuckDuckGo search."""
    print(f"Attempting to scrape Hotstar logo for: {query}")
    logo_url = ""
    original_window = driver.current_window_handle
    
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        
        # Search via DuckDuckGo
        driver.get(f"https://duckduckgo.com/html/?q=site:hotstar.com+{query.replace(' ', '+')}")
        time.sleep(2)
        
        try:
            first_result = driver.find_element(By.CSS_SELECTOR, "a.result__a")
            hotstar_url = first_result.get_attribute("href")
            print(f"Found Hotstar URL: {hotstar_url}")
            driver.get(hotstar_url)
            time.sleep(3)
            
            # Try to find the LOGO (not poster)
            try:
                # Hotstar logo - look for title logo images
                logo_img = driver.find_element(By.CSS_SELECTOR, "img[class*='_2-A9IuHSssOiRkxHvku94z'], img[class*='title-logo'], img[alt][src*='hotstar.com'][class*='h-auto']")
                logo_url = logo_img.get_attribute("src")
                print(f"Found Hotstar logo with selector: {logo_url}")
            except:
                # Try to find logo by looking for images from Hotstar CDN with show name in alt
                try:
                    imgs = driver.find_elements(By.TAG_NAME, "img")
                    for i in imgs:
                        src = i.get_attribute("src") or ""
                        alt = i.get_attribute("alt") or ""
                        
                        # Look for images from Hotstar CDN with show name in alt
                        if src and "hotstar.com" in src and alt and query.lower() in alt.lower():
                            # Check if it's likely a logo (smaller height parameter suggests logo not poster)
                            if "h_124" in src or "h_100" in src or "h_150" in src:
                                logo_url = src
                                print(f"Found Hotstar logo (with alt): {logo_url}")
                                break
                except:
                    pass

        except Exception as e:
            print(f"Hotstar search failed: {e}")

    except Exception as e:
        print(f"Error scraping Hotstar logo: {e}")
    finally:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(original_window)
        except:
            pass
            
    return logo_url


def scrape_imdb(query="The Witcher"):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {}

    try:
        # 1. Go to IMDb
        print("Navigating to IMDb...")
        driver.get("https://www.imdb.com/")
        
        # 2. Search for the query
        print(f"Searching for '{query}'...")
        try:
            search_input = wait.until(EC.element_to_be_clickable((By.ID, "suggestion-search")))
        except:
            search_input = wait.until(EC.element_to_be_clickable((By.NAME, "q")))
            
        search_input.clear()
        search_input.send_keys(query)
        time.sleep(1)
        search_input.send_keys(Keys.ENTER)
        
        # 3. Click the correct result (TV Series) - IMPROVED with better selectors
        print("Clicking result...")
        time.sleep(3)  # Wait for search results to load
        
        clicked = False
        
        # Strategy 1: Global Link Search (Most Robust)
        try:
            print("Strategy 1: Global search for title links...")
            # Find all links that contain the query text
            links = driver.find_elements(By.TAG_NAME, "a")
            print(f"Found {len(links)} total links on page.")
            
            candidates = []
            query_lower = query.lower()
            
            for link in links:
                try:
                    text = link.text.strip()
                    href = link.get_attribute("href")
                    
                    if not text or not href:
                        continue
                    
                    # STRICT: Must be /title/ URL, NOT /name/ URL
                    if "/title/" not in href or "/name/" in href:
                        continue
                        
                    # Check if text matches query
                    if query_lower in text.lower():
                        # Get parent text to check for year/type
                        try:
                            parent = link.find_element(By.XPATH, "./ancestor::li")
                            parent_text = parent.text
                        except:
                            parent_text = text
                        
                        candidates.append({
                            "link": link,
                            "text": text,
                            "parent_text": parent_text,
                            "href": href
                        })
                except:
                    continue
            
            print(f"Found {len(candidates)} candidate links.")
            
            # Filter candidates - EXCLUDE shorts and movies, PRIORITIZE TV series
            tv_series_candidates = []
            other_candidates = []
            
            for cand in candidates:
                p_text = cand["parent_text"].lower()
                title = cand["text"]
                
                print(f"Candidate: '{title}' | Context: {p_text[:80]}...")
                
                # Skip short films and movies with duration indicators
                if "short" in p_text or re.search(r'\d+h\s*\d+m', p_text):
                    print(f"  ⏭️ Skipping (short/movie): {title}")
                    continue
                
                # Separate TV series from others
                if "tv series" in p_text or "tv mini series" in p_text:
                    tv_series_candidates.append(cand)
                else:
                    other_candidates.append(cand)
            
            # Priority 1: Exact match in TV series
            for cand in tv_series_candidates:
                if cand["text"].lower() == query_lower:
                    print(f"Found Priority 1 match (exact TV series): {cand['text']}")
                    safe_click(driver, cand["link"])
                    clicked = True
                    break
            
            # Priority 2: Starts with query in TV series (for "Demon Slayer: Kimetsu no Yaiba")
            if not clicked:
                for cand in tv_series_candidates:
                    if cand["text"].lower().startswith(query_lower):
                        print(f"Found Priority 2 match (starts with, TV series): {cand['text']}")
                        safe_click(driver, cand["link"])
                        clicked = True
                        break
            
            # Priority 3: Any TV series match
            if not clicked and tv_series_candidates:
                print(f"Found Priority 3 match (first TV series): {tv_series_candidates[0]['text']}")
                safe_click(driver, tv_series_candidates[0]["link"])
                clicked = True
            
            # Priority 4: Exact match in other candidates (fallback)
            if not clicked:
                for cand in other_candidates:
                    if cand["text"].lower() == query_lower:
                        print(f"Found Priority 4 match (exact, non-TV): {cand['text']}")
                        safe_click(driver, cand["link"])
                        clicked = True
                        break
                        
        except Exception as e:
            print(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Exact Title Match (Any Type)
        if not clicked:
            try:
                results = driver.find_elements(By.CSS_SELECTOR, "a.ipc-metadata-list-summary-item__t")
                for result in results:
                    if result.text.strip().lower() == query.lower():
                        print(f"Clicking exact match: {result.text}")
                        safe_click(driver, result)
                        clicked = True
                        break
            except Exception as e:
                print(f"Strategy 2 failed: {e}")
        
        # Strategy 3: First Title Result
        if not clicked:
            try:
                results = driver.find_elements(By.CSS_SELECTOR, "a.ipc-metadata-list-summary-item__t")
                if results:
                    print(f"Clicking first title result: {results[0].text}")
                    safe_click(driver, results[0])
                    clicked = True
            except Exception as e:
                print(f"Strategy 3 failed: {e}")
        
        if not clicked:
            raise Exception("Could not find and click any search result")

        time.sleep(3)
        
        # 4. Scrape Main Metadata
        print("Scraping metadata...")
        
        # Title
        try:
            data["show_title"] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except:
            data["show_title"] = query
            
        # Year & Rating & Seasons count (from header list)
        try:
            header_items = driver.find_elements(By.CSS_SELECTOR, "ul.ipc-inline-list--show-dividers li")
            texts = [item.text for item in header_items]
            data["year"] = next((t for t in texts if "20" in t), "2019")
            data["rating"] = next((t for t in texts if "TV-" in t or t in ["A", "U", "PG", "R"]), "TV-MA")
        except:
            data["year"] = "2019"
            data["rating"] = "TV-MA"

        # Seasons count (will update later from episodes tab)
        data["seasons"] = "Unknown" 

        # Description
        try:
            data["description"] = driver.find_element(By.CSS_SELECTOR, "span[data-testid='plot-xl']").text
        except:
            try:
                data["description"] = driver.find_element(By.CSS_SELECTOR, "p[data-testid='plot']").text
            except:
                data["description"] = ""

        # Streaming Service Logo Logic
        print("Checking for streaming service...")
        service_logo = ""
        
        # Detect Service
        is_amazon = False
        is_netflix = False
        is_hotstar = False
        
        try:
            # Check page text for indicators
            page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            if "watch on prime video" in page_text or "amazon original" in page_text:
                is_amazon = True
            elif "watch on netflix" in page_text or "netflix original" in page_text:
                is_netflix = True
            elif "watch on hotstar" in page_text or "disney+ hotstar" in page_text or "hotstar" in page_text:
                is_hotstar = True
                
            # Check specific elements if text check is ambiguous
            if not (is_amazon or is_netflix or is_hotstar):
                try:
                    watch_btns = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='tm-box-wl-button']")
                    for btn in watch_btns:
                        href = btn.get_attribute("href")
                        if "amazon" in href:
                            is_amazon = True
                            break
                        elif "netflix" in href:
                            is_netflix = True
                            break
                        elif "hotstar" in href:
                            is_hotstar = True
                            break
                except:
                    pass
        except:
            pass
            
        # Manual overrides for known shows if detection fails (optional, but good for testing)
        if "the boys" in query.lower():
            is_amazon = True
        if "squid game" in query.lower() or "stranger things" in query.lower():
            is_netflix = True
        if "demon slayer" in query.lower():
            is_hotstar = True
            
        if is_amazon:
            print("Detected Amazon Prime association.")
            service_logo = scrape_amazon_logo(query, driver)
        elif is_netflix:
            print("Detected Netflix association.")
            service_logo = scrape_netflix_logo(query, driver)
        elif is_hotstar:
            print("Detected Hotstar association.")
            service_logo = scrape_hotstar_logo(query, driver)
            
        if service_logo:
            data["series_logo"] = service_logo
            print(f"Using streaming service logo: {service_logo}")
        else:
            # IMDb Poster/Logo Fallback
            print("Using IMDb poster as logo...")
            try:
                # Try to get the main poster
                poster_el = driver.find_element(By.CSS_SELECTOR, "div[data-testid='hero-media__poster'] img, div.ipc-poster img")
                
                # Try srcset first for higher quality
                srcset = poster_el.get_attribute("srcset")
                if srcset:
                    urls = []
                    for part in srcset.split(','):
                        url = part.strip().split()[0]
                        if url and url.startswith('http'):
                            urls.append(url)
                    if urls:
                        data["series_logo"] = urls[-1]
                    else:
                        data["series_logo"] = poster_el.get_attribute("src")
                else:
                    data["series_logo"] = poster_el.get_attribute("src")
                    
            except Exception as e:
                print(f"Error scraping poster: {e}")
                data["series_logo"] = ""


        # Creators
        try:
            creators_li = driver.find_elements(By.CSS_SELECTOR, "li[data-testid='title-pc-principal-credit']")
            creators = []
            for li in creators_li:
                if "Creator" in li.text or "Created" in li.text:
                    links = li.find_elements(By.TAG_NAME, "a")
                    creators = [l.text for l in links if l.text and "Creator" not in l.text]
                    break
            data["creators"] = ", ".join(creators)
        except:
            data["creators"] = ""

        # Cast (Starring)
        try:
            cast_items = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='title-cast-item__actor']")
            cast_names = [c.text for c in cast_items[:10]]
            data["cast"] = ", ".join(cast_names)
            data["starring"] = ", ".join(cast_names[:3])
        except:
            data["cast"] = ""
            data["starring"] = ""

        # Placeholders for user requested fields
        data["show_characteristics"] = "Fantasy, Action, Drama, Magic, Monsters"
        data["audio"] = "English, Polish, French, German, Spanish"
        data["subtitles"] = "English, Spanish, French"

        # 5. Scrape Episodes - IMPROVED
        print("Scraping episodes...")
        data["seasons_data"] = []
        
        # Navigate to Episodes
        if "episodes" not in driver.current_url:
            try:
                episodes_link = wait.until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Episodes")))
                safe_click(driver, episodes_link)
                time.sleep(3)
            except:
                print("Could not find Episodes link, trying URL manipulation")
        
        # Force URL manipulation if still not on episodes page
        if "episodes" not in driver.current_url:
            print("Forcing navigation to episodes URL...")
            current_url = driver.current_url.split("?")[0]
            if current_url.endswith("/"):
                ep_url = current_url + "episodes"
            else:
                ep_url = current_url + "/episodes"
            driver.get(ep_url)
            time.sleep(3)
            
        print(f"Current URL for episodes: {driver.current_url}")

        # Get total seasons - USE CLICKABLE TABS
        try:
            season_tabs = []
            season_nums = []
            
            # Wait for page to fully load
            time.sleep(3)
            
            print("Looking for season tabs...")
            
            # Find season tabs - these are <a> tags with data-testid="tab-season-entry"
            try:
                tabs = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='tab-season-entry']")
                print(f"Found {len(tabs)} season tabs")
                
                for tab in tabs:
                    text = tab.text.strip()
                    href = tab.get_attribute("href")
                    print(f"  Season tab: text='{text}', href='{href}'")
                    
                    # Extract season number from text
                    if text and text.isdigit():
                        season_nums.append(text)
                        season_tabs.append(tab)
                    else:
                        # Try to extract from href like "/episodes/?season=2"
                        match = re.search(r'season=(\d+)', href)
                        if match:
                            season_num = match.group(1)
                            season_nums.append(season_num)
                            season_tabs.append(tab)
                
                print(f"✓ Found {len(season_nums)} seasons: {season_nums}")
            except Exception as e:
                print(f"Error finding season tabs: {e}")
            
            # Fallback if no tabs found
            if not season_nums:
                print("⚠️ No season tabs found, defaulting to Season 1")
                season_nums = ["1"]
            
            data["seasons"] = f"{len(season_nums)} Season{'s' if len(season_nums) > 1 else ''}"
            print(f"📊 Total seasons to scrape: {len(season_nums)}")
            
            # Clean show title for filename (remove year/roman numerals in parens)
            # e.g. "The Boys (VIII)" -> "The Boys"
            title_for_filename = re.sub(r'\s*\(.*?\)', '', data["show_title"]).strip()
            show_clean = re.sub(r'[^\w\s-]', '', title_for_filename).strip().replace(' ', '_')
            
            # Scrape each season - CLICK ON TABS
            for idx, sn in enumerate(season_nums):
                print(f"Scraping Season {sn}...")
                
                # Click on the season tab if we have tabs and it's not the first season (already loaded)
                if season_tabs and idx > 0:
                    try:
                        # Re-find the tab to avoid stale element
                        tabs = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='tab-season-entry']")
                        for tab in tabs:
                            text = tab.text.strip()
                            href = tab.get_attribute("href")
                            
                            # Check if this is the season we want
                            if text == sn or f"season={sn}" in href:
                                print(f"Clicking on Season {sn} tab...")
                                safe_click(driver, tab)
                                time.sleep(3)  # Wait for episodes to load
                                break
                    except Exception as e:
                        print(f"Error clicking season tab: {e}")


                # Scrape episodes in this season
                season_episodes = []
                seen_titles = set()  # Track seen episode titles to avoid duplicates
                
                # Wait for episode list to load
                time.sleep(3)
                
                # Scroll down to load all episodes
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
                # Find episode container - try multiple strategies
                try:
                    # Strategy 1: Look for the episodes section
                    list_container = driver.find_element(By.CSS_SELECTOR, "section[data-testid='episodes-content']")
                except:
                    try:
                        # Strategy 2: Look for article parent
                        list_container = driver.find_element(By.CSS_SELECTOR, ".ipc-page-grid__item--span-2")
                    except:
                        try:
                            list_container = driver.find_element(By.CSS_SELECTOR, "div.ipc-page-content")
                        except:
                            list_container = driver.find_element(By.TAG_NAME, "body")

                # Find episode items - improved selectors
                # Look for article elements or list items
                potential_cards = list_container.find_elements(By.CSS_SELECTOR, "article.episode-item-wrapper, .ipc-list-card, div[data-testid='episodes-item']")
                
                if not potential_cards:
                    # Fallback: look for any article
                    potential_cards = list_container.find_elements(By.TAG_NAME, "article")
                
                if not potential_cards:
                    # Last resort: find by title elements
                    potential_cards = list_container.find_elements(By.CSS_SELECTOR, "div.ipc-title")
                
                print(f"Found {len(potential_cards)} potential episode cards")

                print(f"Found {len(potential_cards)} potential episode cards")

                for idx, card in enumerate(potential_cards):
                    ep_data = {}
                    try:
                        # Extract title
                        try:
                            title_el = card.find_element(By.CSS_SELECTOR, "h4, .ipc-title__text, a.ipc-title-link-wrapper")
                            full_title = title_el.text.strip()
                            if not full_title:
                                continue
                        except:
                            continue
                        
                        # Extract description
                        try:
                            desc_el = card.find_element(By.CSS_SELECTOR, ".ipc-html-content-inner-div, div[class*='plot']")
                            desc = desc_el.text.strip()
                        except:
                            desc = ""
                        
                        # Extract image - IMPROVED to get valid URLs
                        img_src = ""
                        try:
                            img_el = card.find_element(By.CSS_SELECTOR, "img.ipc-image")
                            
                            # Try srcset first (usually has better quality)
                            srcset = img_el.get_attribute("srcset")
                            if srcset:
                                # Parse srcset - format: "url 1x, url 2x"
                                urls = []
                                for part in srcset.split(','):
                                    url = part.strip().split()[0]
                                    if url and url.startswith('http'):
                                        urls.append(url)
                                
                                # Use the highest quality (last one)
                                if urls:
                                    img_src = urls[-1]
                            
                            # Fallback to src attribute
                            if not img_src:
                                img_src = img_el.get_attribute("src") or ""
                                
                                # Fix incomplete URLs
                                if img_src:
                                    if img_src.startswith("//"):
                                        img_src = "https:" + img_src
                                    elif img_src.startswith("/"):
                                        img_src = "https://www.imdb.com" + img_src
                                    elif not img_src.startswith("http"):
                                        # Likely a placeholder or data URL, skip it
                                        img_src = ""
                        except:
                            img_src = ""
                        
                        # Extract duration/date
                        try:
                            metadata_el = card.find_element(By.CSS_SELECTOR, ".ipc-inline-list, ul.ipc-metadata-list")
                            duration = metadata_el.text.strip()
                        except:
                            duration = "1h"

                        ep_data["title"] = full_title
                        ep_data["description"] = desc
                        ep_data["duration"] = duration
                        ep_data["image_url"] = img_src
                            
                        # Filename & URL - extract S##E## from title
                        match = re.search(r"S(\d+)\.E(\d+)", full_title, re.IGNORECASE)
                        if match:
                            s_num = int(match.group(1))
                            e_num = int(match.group(2))
                        else:
                            s_num = int(sn)
                            e_num = len(season_episodes) + 1
                            
                        ep_data["filename"] = f"{show_clean}_S{s_num:02d}E{e_num:02d}.mkv"
                        ep_data["url"] = "https://filemoon.in/placeholder"
                        
                        # Only add if we haven't seen this title before (avoid duplicates)
                        if full_title not in seen_titles:
                            season_episodes.append(ep_data)
                            seen_titles.add(full_title)
                    except Exception as e:
                        continue
                
                data["seasons_data"].append({f"Season {sn}": season_episodes})

        except Exception as e:
            print(f"Error scraping seasons: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        driver.save_screenshot("imdb_error.png")

    finally:
        driver.quit()
        
    return data

if __name__ == "__main__":
    import sys
    
    # Get query from command line argument or default to The Witcher
    query = sys.argv[1] if len(sys.argv) > 1 else "The Witcher"
    
    print(f"Scraping IMDb for: {query}")
    result = scrape_imdb(query)

    STATIC_DIR = "static"
    os.makedirs(STATIC_DIR, exist_ok=True)
    
    query_clean = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_').lower()
    output_file = os.path.join(STATIC_DIR, f"{query_clean}.json")
    
    # Save to /static folder
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"✅ Data saved to {output_file}")

