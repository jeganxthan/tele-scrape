import sys
import time
import json
import datetime
import re
import csv
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from db_utils import save_show_data, save_movie_data

def find_file_code_in_csv(query):
    """Searches for a file_code in filemoon_files.csv based on the query."""
    csv_path = "filemoon_files.csv"
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV not found: {csv_path}")
        return None
    
    query_words = query.lower().split()
    try:
        with open(csv_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use 'title' column (or 'filename' as fallback)
                title = (row.get('title') or row.get('filename', '')).lower()
                # Check if all query words are in the title
                if all(word in title for word in query_words):
                    file_code = row.get('file_code', '')
                    if file_code:
                        print(f"✅ Found match in CSV: {row.get('title') or row.get('filename')} -> {file_code}")
                        return file_code
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
    
    return None

def setup_driver():
    print("Setting up Chrome driver...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Chrome driver setup successful.")
    return driver

def scrape_movie_metadata(movie_name, scrape_type="movie"):
    driver = setup_driver()
    metadata = {}
    try:
        url = "https://staging.strem.io/#/"
        print(f"Navigating to {url}...")
        driver.get(url)
        
        # Wait for search box to be interactive
        wait = WebDriverWait(driver, 15)
        print("Waiting for search field...")
        search_input = wait.until(EC.element_to_be_clickable((By.ID, "global-search-field")))
        
        from selenium.webdriver.common.keys import Keys

        def perform_search_and_select(query_name, force_type=None):
            print(f"Searching for '{query_name}'...")
            search_input.clear()
            search_input.send_keys(query_name)
            time.sleep(1)
            search_input.send_keys(Keys.ENTER)
            
            # Wait for results to appear
            print("Waiting for search results...")
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".board-item, .item, li[ng-repeat*='result.metas']")))
                results = driver.find_elements(By.CSS_SELECTOR, ".board-item, .item, li[ng-repeat*='result.metas']")
            except:
                results = []
        
            print(f"Found {len(results)} results.")
            
            target_item = None
            
            # Determine preference based on query or force_type
            prefer_type = force_type if force_type else "movie"
            if not force_type and "anime" in movie_name.lower():
                prefer_type = "series" # Anime is usually classified as series
            
            print(f"Preferring type: {prefer_type}")
            
            for i, res in enumerate(results):
                try:
                    # Extract item data using Angular scope
                    item_data = driver.execute_script("return angular.element(arguments[0]).scope().item", res)
                    item_name = item_data.get('name', '')
                    item_type = item_data.get('type', '')
                    item_year = item_data.get('year', '')
                    
                    print(f"Result {i}: Name='{item_name}', Type='{item_type}', Year='{item_year}'")
                    
                    # Strict filtering: If we want a specific type, IGNORE other types
                    if prefer_type and item_type != prefer_type:
                        print(f"Skipping result {i} (Type='{item_type}') because we want '{prefer_type}'")
                        continue

                    # Check for exact match + type preference
                    # Compare against the CURRENT query name for better matching on retry
                    if item_name.lower() == query_name.lower() and item_type == prefer_type:
                        target_item = res
                        print("✅ Found exact preferred match!")
                        break

                    
                    # Fallback: exact match, SAME type (limit fallback to same type)
                    if item_name.lower() == query_name.lower() and target_item is None and item_type == prefer_type:
                        target_item = res
                except Exception as e:
                    print(f"Error inspecting result {i}: {e}")
                    continue
            
            # If no specific target found, default to the first one THAT MATCHES TYPE
            if target_item is None and results:
                 print("No exact match found, looking for first result with correct type...")
                 for res in results:
                     try:
                        item_data = driver.execute_script("return angular.element(arguments[0]).scope().item", res)
                        if item_data.get('type') == prefer_type:
                            target_item = res
                            print(f"Selected first '{prefer_type}' result: {item_data.get('name')}")
                            break
                     except: pass

            if target_item:
                print(f"Clicking selected item...")
                try:
                    target_item.click()
                except Exception as e:
                    print(f"Standard click failed, attempting JS click: {e}")
                    driver.execute_script("arguments[0].click();", target_item)
                return True
            else:
                print("❌ No matching results found.")
                return False

        # Attempt 1: Original name
        if not perform_search_and_select(movie_name, force_type=scrape_type):
            # Attempt 2: Strip year if present
            # Regex to find (YYYY) or just YYYY at the end
            cleaned_name = re.sub(r'\s*\(?\d{4}\)?$', '', movie_name)
            
            if cleaned_name != movie_name and len(cleaned_name) > 2:
                print(f"⚠️ Initial search failed. Retrying with year stripped: '{cleaned_name}'")
                if not perform_search_and_select(cleaned_name, force_type=scrape_type):
                     print(f"❌ Retry failed for '{cleaned_name}'. Aborting.")
                     return None
            else:
                return None
        
        print(f"Current URL: {driver.current_url}")
        
        print("Waiting for details page...")
        time.sleep(2)  # Give page time to load
        
        # Determine if it's a movie or series
        is_anime = "anime" in movie_name.lower()
        
        # Enforce strict categorization: If it's not anime, it MUST be a movie (as per user request)
        # Even if the URL says /series/, we treat it as movie metadata or fail, 
        # but since we filtered search results, we should be on a movie page.
        
        metadata['category'] = "anime" if is_anime else "movie"
        is_series = False # Force false for movie_metadata.py unless logic changes in future
        
        # Extract title
        try:
            title_elem = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#detail h1, #detail .logo img, #detail .title")))
            if title_elem.tag_name == 'img':
                title = title_elem.get_attribute("alt")
            else:
                title = title_elem.text
            
            metadata['title'] = title
            print(f"Found title: {title}")
        except:
            metadata['title'] = ""
        
        # Extract description
        try:
            desc_elem = driver.find_element(By.CSS_SELECTOR, "#detail .description, #detail .text, [ng-bind-html*='description']")
            metadata['description'] = desc_elem.text
        except:
            metadata['description'] = ""

        # Extract year
        try:
            info_items = driver.find_elements(By.CSS_SELECTOR, "#detail .info li")
            metadata['year'] = ""
            for item in info_items:
                text = item.text
                # Match year or year range (e.g., "2020" or "2020–")
                if re.match(r'^\d{4}', text):
                    metadata['year'] = text
                    break
        except:
            metadata['year'] = ""
        
        # Extract rating (IMDb)
        try:
            rating_elem = driver.find_element(By.CSS_SELECTOR, ".info .external, #detail .imdb-rating, #detail .rating")
            rating_text = rating_elem.text.strip()
            if rating_text and "/" not in rating_text and rating_text.replace(".", "").isdigit():
                metadata['rating'] = f"{rating_text}/10"
            else:
                metadata['rating'] = rating_text if rating_text else "User reviews"
        except:
            metadata['rating'] = "User reviews"
        
        # Extract images
        # 1. Get IMDB ID for robust fallbacks
        imdb_id = ""
        imdb_id_match = re.search(r'tt\d+', driver.current_url)
        if imdb_id_match:
            imdb_id = imdb_id_match.group(0)

        # 2. Poster (Sidebar vertical image)
        try:
            poster_elem = driver.find_element(By.CSS_SELECTOR, ".sidebar img[stremio-image*='poster'], .sidebar img, #detail .poster img")
            metadata['poster'] = poster_elem.get_attribute("src")
        except:
            if imdb_id:
                metadata['poster'] = f"https://images.metahub.space/poster/medium/{imdb_id}/img"
            else:
                metadata['poster'] = ""

        # 3. Series Logo (Horizontal logo)
        try:
            # Look for images with 'logo' in their path/ng-src as requested
            logo_elem = driver.find_element(By.CSS_SELECTOR, "img[ng-src*='/logo/'], img[src*='/logo/'], #detail .logo img")
            metadata['series_logo'] = logo_elem.get_attribute("src")
        except:
            metadata['series_logo'] = metadata.get('poster', "")
        
        # 4. Background
        bg_url = ""
        # Method A: Check background element style
        try:
            background_elem = driver.find_element(By.CSS_SELECTOR, "#detail .background")
            bg_style = background_elem.get_attribute("style")
            if "url(" in bg_style:
                bg_url = bg_style.split("url(")[1].split(")")[0].replace('"', '').replace("'", "")
        except:
            pass
        
        # Method B: Check for background image element
        if not bg_url:
            try:
                bg_img = driver.find_element(By.CSS_SELECTOR, "#detail .background img, #detail .background .image img")
                bg_url = bg_img.get_attribute("src")
            except:
                pass
        
        # Method C: Construct from IMDB ID (most reliable fallback)
        if not bg_url and imdb_id:
            bg_url = f"https://images.metahub.space/background/medium/{imdb_id}/img"
            print(f"✅ Constructed background from IMDB ID: {imdb_id}")
        
        metadata['background'] = bg_url if bg_url else ""

        # Extract creators, cast, and genres using improved section logic
        def extract_section_links(label_text):
            try:
                sections = driver.find_elements(By.CSS_SELECTOR, ".details .section")
                for section in sections:
                    try:
                        title_el = section.find_element(By.CSS_SELECTOR, ".title")
                        if label_text.lower() in title_el.text.lower():
                            links = section.find_elements(By.CSS_SELECTOR, ".links .link")
                            return ", ".join([link.text for link in links if link.text])
                    except:
                        continue
            except:
                pass
            return ""

        metadata['creators'] = extract_section_links("DIRECTORS")
        if not metadata['creators']:
            metadata['creators'] = extract_section_links("CREATORS")
        
        metadata['cast'] = extract_section_links("CAST")
        metadata['show_characteristics'] = extract_section_links("GENRES")
        
        # Extract starring (top 3 cast members)
        if metadata['cast']:
            cast_parts = metadata['cast'].split(", ")
            metadata['starring'] = ", ".join(cast_parts[:3])
        else:
            metadata['starring'] = ""
        
        # Extract audio languages
        try:
            audio_elem = driver.find_element(By.CSS_SELECTOR, "#detail .audio, [ng-if*='audio'], .languages .audio")
            metadata['audio'] = audio_elem.text
        except:
            metadata['audio'] = "Japanese, English"  # Default for anime
        
        # Extract subtitle languages
        try:
            subtitle_elem = driver.find_element(By.CSS_SELECTOR, "#detail .subtitles, [ng-if*='subtitle'], .languages .subtitles")
            metadata['subtitles'] = subtitle_elem.text
        except:
            metadata['subtitles'] = "English, Spanish"  # Default
        
        # URL (fill from FileMoon CSV)
        file_code = find_file_code_in_csv(movie_name)
        if file_code:
            metadata['url'] = f"https://filemoon.in/e/{file_code}"
        else:
            metadata['url'] = ""

        # Save to database
        if is_anime:
             # Logic for anime might be different, but assuming save_show_data if it has seasons?
             # For now, if "anime" in name, we might be scraping series. 
             # But user said "no season_data" from movie_metadata.py.
             # Let's assume anime goes to save_show_data if structure fits, OR we just save as movie?
             # The previous code did: metadata['category'] = "anime".
             # If category is anime, DB utils might handle it.
             # However, simple safe bet:
             pass 
             
        # Save to database
        # Strictly save using save_movie_data as requested by user ("no season_data")
        # unless it is explicitly an anime which might need show handling.
        # But for "movie_metadata.py", let's prioritize movie saving.
        
        save_movie_data(metadata)

        # Convert datetime to string for printing
        print_metadata = metadata.copy()
        if "created_at" in print_metadata and isinstance(print_metadata["created_at"], datetime.datetime):
            print_metadata["created_at"] = print_metadata["created_at"].isoformat()
            
        print(json.dumps(print_metadata, indent=4))
        return metadata
        
    except Exception as e:
        print(f"Error scraping metadata: {e}")
        with open("debug_page.html", "w") as f:
            f.write(driver.page_source)
        print("Saved debug_page.html")
        driver.save_screenshot("debug_screenshot.png")
        print("Saved debug_screenshot.png")
        return None
    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 movie_metadata.py \"Movie Name\"")
        # Default testing
        # scrape_movie_metadata("Inception")
    else:
        scrape_movie_metadata(sys.argv[1])

