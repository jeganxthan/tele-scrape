import json
import time
import re
import os
import sys
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Import project-specific utilities
import db_utils
import filemoon_converter

def setup_driver():
    """Setup a headless Chrome driver with optimized settings."""
    options = Options()
    options.add_argument("--headless=new") 
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--mute-audio")
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

def scrape_stremio_images(tt_id, media_type, driver):
    """Scrape high-quality series logo, fanart, and poster from Stremio staging."""
    print(f"Attempting to scrape Stremio images for {tt_id} ({media_type})")
    stremio_data = {"logo": "", "fanart": "", "poster": ""}
    
    url = f"https://staging.strem.io/#/detail/{media_type}/{tt_id}/"
    original_window = driver.current_window_handle
    
    try:
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(url)
        time.sleep(5) 
        
        # 1. Logo
        try:
            logo_img = driver.find_elements(By.CSS_SELECTOR, "img[src*='/logo/']")
            if logo_img:
                stremio_data["logo"] = logo_img[0].get_attribute("src")
        except: pass
            
        # 2. Fanart (Background)
        try:
            bg_el = driver.find_elements(By.CSS_SELECTOR, "div.image")
            if bg_el:
                bg_style = bg_el[0].get_attribute("style")
                if "background-image" in bg_style and 'url("' in bg_style:
                    stremio_data["fanart"] = bg_style.split('url("')[1].split('")')[0]
        except: pass
            
        # 3. Poster
        if tt_id:
            stremio_data["poster"] = f"https://images.metahub.space/poster/medium/{tt_id}/img"
            
    except Exception as e:
        print(f"Error scraping Stremio: {e}")
    finally:
        try:
            if len(driver.window_handles) > 1:
                driver.close()
            driver.switch_to.window(original_window)
        except: pass
            
    return stremio_data

def natural_sort_key(s):
    """
    Key for natural sorting of strings containing numbers.
    e.g. "Ep 1", "Ep 2", "Ep 10" -> 1, 2, 10
    """
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split('([0-9]+)', s)]

def fill_urls_sequentially(data, query):
    """
    Sequentially maps sorted FileMoon files to episodes for the given query.
    Assumes files in CSV are named like "Demon slayer 1", "Demon slayer 2" etc.
    """
    print(f"Aligning FileMoon URLs sequentially for query: '{query}'")
    csv_path = "filemoon_files.csv"
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV file not found: {csv_path}")
        return data

    candidate_files = []
    
    # Normalize query for fuzzy matching (remove special chars, lowercase)
    query_clean = re.sub(r'[^\w\s]', '', query).lower().split()
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                file_code = row.get('file_code', '').strip()
                
                # Check if file title contains significant words from query
                # e.g. "Demon" and "Slayer"
                title_lower = title.lower()
                match_count = 0
                for word in query_clean:
                    if word in title_lower:
                        match_count += 1
                
                # If matches at least half the words, consider it a candidate
                if match_count >= max(1, len(query_clean) // 2):
                    candidate_files.append({"title": title, "file_code": file_code})
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return data

    # Sort files naturally: "Show 1", "Show 2", "Show 10"
    candidate_files.sort(key=lambda x: natural_sort_key(x['title']))
    
    print(f"Found {len(candidate_files)} candidate files for '{query}'")
    
    # Flatten episodes list to assign sequentially
    episodes_flat = []
    for season in data.get("seasons_data", []):
         for s_key, ep_list in season.items():
            episodes_flat.extend(ep_list)
            
    # Assign URLs
    # We loop min(len(episodes), len(files))
    count = min(len(episodes_flat), len(candidate_files))
    
    for i in range(count):
        file_info = candidate_files[i]
        ep_info = episodes_flat[i]
        
        url = f"https://filemoon.in/e/{file_info['file_code']}"
        ep_info["url"] = url
        
        print(f"   Mapped: '{ep_info['title']}' <--> '{file_info['title']}' ({url})")
        
    return data

def scrape_anime_meta(query="Demon Slayer"):
    """Scrape anime metadata from IMDb and align it with FileMoon URLs."""
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {}

    try:
        # 1. Search IMDb for the Anime
        print(f"Searching IMDb for: {query}")
        driver.get("https://www.imdb.com/")
        try:
            search_input = wait.until(EC.element_to_be_clickable((By.ID, "suggestion-search")))
        except:
            search_input = wait.until(EC.element_to_be_clickable((By.NAME, "q")))
            
        search_input.clear()
        search_input.send_keys(query)
        search_input.send_keys(Keys.ENTER)
        
        time.sleep(3)
        
        # Select the best matching TV Series result
        clicked = False
        links = driver.find_elements(By.TAG_NAME, "a")
        candidates = []
        query_lower = query.lower()
        
        for link in links:
            try:
                text = link.text.strip()
                href = link.get_attribute("href")
                if not text or not href or "/title/" not in href or "/name/" in href:
                    continue
                
                if query_lower in text.lower():
                    try:
                        parent = link.find_element(By.XPATH, "./ancestor::li")
                        parent_text = parent.text
                    except:
                        parent_text = text
                    
                    candidates.append({"link": link, "text": text, "parent_text": parent_text, "href": href})
            except:
                continue

        # Filter for TV Series
        tv_candidates = [c for c in candidates if "tv series" in c["parent_text"].lower() or "mini series" in c["parent_text"].lower()]
        
        if tv_candidates:
            # Prefer exact match or first TV series
            best_match = next((c for c in tv_candidates if c["text"].lower() == query_lower), tv_candidates[0])
            print(f"Selecting result: {best_match['text']}")
            safe_click(driver, best_match["link"])
            clicked = True
        elif candidates:
            print(f"No TV series found, selecting first title result: {candidates[0]['text']}")
            safe_click(driver, candidates[0]["link"])
            clicked = True
            
        if not clicked:
            raise Exception(f"No results found for {query}")

        time.sleep(3)
        current_url = driver.current_url
        tt_id = re.search(r'tt\d+', current_url).group(0) if re.search(r'tt\d+', current_url) else None
        
        # 2. Extract Main Metadata
        print("Extracting metadata...")
        data["show_title"] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        data["category"] = "anime"
        
        try:
            header_items = driver.find_elements(By.CSS_SELECTOR, "ul.ipc-inline-list--show-dividers li")
            texts = [item.text for item in header_items]
            data["year"] = next((t for t in texts if any(y in t for y in ["19", "20"])), "2024")
            data["rating"] = next((t for t in texts if any(r in t for r in ["TV-", "PG", "R", "U", "A"])), "TV-14")
        except:
            data["year"] = "2024"
            data["rating"] = "TV-14"

        try:
            data["description"] = driver.find_element(By.CSS_SELECTOR, "span[data-testid='plot-xl']").text
        except:
            try: data["description"] = driver.find_element(By.CSS_SELECTOR, "p[data-testid='plot']").text
            except: data["description"] = ""

        # High-quality images
        stremio = scrape_stremio_images(tt_id, "series", driver) if tt_id else {"logo": "", "fanart": "", "poster": ""}
        data["series_logo"] = stremio["logo"] or stremio["poster"] or ""
        data["poster"] = stremio["poster"] or ""
        data["fanart"] = stremio["fanart"] or ""
        
        # Fallback for poster
        if not data["poster"]:
            try:
                poster_img = driver.find_element(By.CSS_SELECTOR, "div[data-testid='hero-media__poster'] img")
                data["poster"] = poster_img.get_attribute("src")
            except: pass

        # Other metadata
        data["creators"] = ""
        try:
            credits = driver.find_elements(By.CSS_SELECTOR, "li[data-testid='title-pc-principal-credit']")
            for credit in credits:
                if "Creator" in credit.text or "Created" in credit.text:
                    data["creators"] = ", ".join([l.text for l in credit.find_elements(By.TAG_NAME, "a") if l.text and "Creator" not in l.text])
                    break
        except: pass
        
        data["cast"] = ""
        try:
            actors = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='title-cast-item__actor']")
            data["cast"] = ", ".join([a.text for a in actors[:10]])
            data["starring"] = ", ".join([a.text for a in actors[:3]])
        except: 
            data["starring"] = ""

        # Default characteristics
        data["show_characteristics"] = "Animation, Action, Adventure, Fantasy"
        data["audio"] = "Japanese, English"
        data["subtitles"] = "English, Spanish"

        # 3. Scrape Episodes
        print("Scraping episodes...")
        data["seasons_data"] = []
        
        # Navigate to Episode List
        if "/episodes" not in driver.current_url:
            try:
                ep_link = wait.until(EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Episodes")))
                safe_click(driver, ep_link)
                time.sleep(3)
            except:
                driver.get(driver.current_url.split("?")[0].rstrip("/") + "/episodes")
                time.sleep(3)

        # Find Seasons
        season_nums = []
        try:
            tabs = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='tab-season-entry']")
            for tab in tabs:
                txt = tab.text.strip()
                if txt.isdigit(): season_nums.append(txt)
        except: 
            season_nums = ["1"]
            
        if not season_nums: season_nums = ["1"]
        data["seasons"] = f"{len(season_nums)} Seasons"

        title_for_filename = re.sub(r'\s*\(.*?\)', '', data["show_title"]).strip()
        show_clean = title_for_filename.title()

        global_episode_counter = 1

        for sn in season_nums:
            print(f"Scraping Season {sn}...")
            # Navigate to the season if needed
            if len(season_nums) > 1:
                try:
                    tabs = driver.find_elements(By.CSS_SELECTOR, "a[data-testid='tab-season-entry']")
                    for tab in tabs:
                        if tab.text.strip() == sn:
                            safe_click(driver, tab)
                            time.sleep(3)
                            break
                except: pass

            season_episodes = []
            seen_titles = set()
            
            # Scroll to load all
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            cards = driver.find_elements(By.CSS_SELECTOR, "article.episode-item-wrapper, div[data-testid='episodes-item']")
            if not cards: cards = driver.find_elements(By.TAG_NAME, "article")

            for card in cards:
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "h4, .ipc-title__text")
                    ep_title = title_el.text.strip()
                    if not ep_title or ep_title in seen_titles: continue
                    seen_titles.add(ep_title)
                    
                    try: ep_desc = card.find_element(By.CSS_SELECTOR, ".ipc-html-content-inner-div").text.strip()
                    except: ep_desc = ""
                    
                    ep_img = ""
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
                                ep_img = urls[-1]
                        
                        # Fallback to src attribute
                        if not ep_img:
                            ep_img = img_el.get_attribute("src") or ""
                            
                            # Fix incomplete URLs
                            if ep_img:
                                if ep_img.startswith("//"):
                                    ep_img = "https:" + ep_img
                                elif ep_img.startswith("/"):
                                    ep_img = "https://www.imdb.com" + ep_img
                                elif not ep_img.startswith("http"):
                                    # Likely a placeholder or data URL, skip it
                                    ep_img = ""
                    except: pass
                    
                    try: ep_duration = card.find_element(By.CSS_SELECTOR, ".ipc-inline-list").text.strip()
                    except: ep_duration = "24m"

                    # Parse Season/Episode numbers
                    match = re.search(r"S(\d+)\.E(\d+)", ep_title, re.IGNORECASE)
                    s_num = int(match.group(1)) if match else int(sn)
                    e_num = int(match.group(2)) if match else len(season_episodes) + 1

                    season_episodes.append({
                        "title": ep_title,
                        "description": ep_desc,
                        "duration": ep_duration,
                        "image_url": ep_img,
                        "filename": f"{show_clean} {global_episode_counter}.mp4",
                        "url": "https://filemoon.in/placeholder",
                        "subtitle_file": ""
                    })
                    global_episode_counter += 1
                except: continue
            
            data["seasons_data"].append({f"Season {int(sn):02d}": season_episodes})

    except Exception as e:
        print(f"Error during scraping: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

    # Post-processing: FileMoon URL alignment
    print("Aligning with FileMoon URLs...")
    try:
        # data = filemoon_converter.fill_filemoon_urls(data) # OLD METHOD
        data = fill_urls_sequentially(data, query) # NEW METHOD
    except Exception as e:
        print(f"Error aligning URLs: {e}")

    return data

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "Demon Slayer"
    print(f"🚀 Starting Anime Meta Scraper for: {query}")
    
    result = scrape_anime_meta(query)
    
    if not result.get("show_title"):
        print("❌ Failed to scrape data.")
        sys.exit(1)

    # Save to static
    static_dir = "static"
    os.makedirs(static_dir, exist_ok=True)
    query_slug = re.sub(r'[^\w\s-]', '', query).strip().replace(' ', '_').lower()
    output_path = os.path.join(static_dir, f"{query_slug}_meta.json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    print(f"✅ Metadata saved to {output_path}")

    # Save to MongoDB
    try:
        db_utils.save_show_data(result)
        print("✅ Data saved to MongoDB")
    except Exception as e:
        print(f"❌ Failed to save to MongoDB: {e}")
