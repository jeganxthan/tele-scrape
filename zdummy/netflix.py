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
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import Select

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

def scrape_netflix(query):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {}

    try:
        print(f"Navigating to Netflix to search for: {query}")
        print(f"Navigating to Netflix to search for: {query}")
        # Search via DuckDuckGo HTML to avoid JS blocking
        driver.get(f"https://duckduckgo.com/html/?q=site:netflix.com/in/title/+{query.replace(' ', '+')}")
        time.sleep(3)
        
        # Click the first relevant result
        try:
            # DuckDuckGo HTML selectors
            first_result = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.result__a")))
            netflix_url = first_result.get_attribute("href")
            print(f"Found Netflix URL: {netflix_url}")
            driver.get(netflix_url)
        except Exception as e:
            print(f"Could not find Netflix URL via DuckDuckGo: {e}")
            return None

        time.sleep(5)

        # Scrape details
        print("Scraping show details...")
        
        # Title
        try:
            data["show_title"] = driver.find_element(By.CSS_SELECTOR, "h1.title-title").text
        except:
            try:
                data["show_title"] = driver.find_element(By.CSS_SELECTOR, "div.default-ltr-iqcdef-cache-kiz1b3 h2").text
            except:
                data["show_title"] = query

        # Metadata (Year, Rating, Seasons, etc.)
        # Netflix layout varies. Trying common selectors.
        try:
            meta_list = driver.find_elements(By.CSS_SELECTOR, "ul.default-ltr-iqcdef-cache-1xty6x8 li, .title-info-metadata-item")
            texts = [m.text for m in meta_list]
            
            data["year"] = next((t for t in texts if re.match(r'\d{4}', t)), "Unknown")
            data["rating"] = next((t for t in texts if t in ["U/A 16+", "A", "U", "18+", "TV-MA", "R"]), "TV-MA")
            data["seasons"] = next((t for t in texts if "Season" in t or "Limited Series" in t), "Unknown")
        except:
            data["year"] = ""
            data["rating"] = ""
            data["seasons"] = ""

        # Description
        try:
            data["description"] = driver.find_element(By.CSS_SELECTOR, "div.title-info-synopsis, div.default-ltr-iqcdef-cache-1akt4ld").text
        except:
            data["description"] = ""

        # Poster/Logo
        try:
            # Try to find the logo
            logo_img = driver.find_element(By.CSS_SELECTOR, "img.title-logo, img.logo")
            data["series_logo"] = logo_img.get_attribute("src")
        except:
            data["series_logo"] = ""

        try:
            # Try to find a background image as poster
            hero_img = driver.find_element(By.CSS_SELECTOR, "div.hero-image-desktop img, img.hero-image, .hero-image-container img")
            data["poster"] = hero_img.get_attribute("src")
        except:
            # Fallback: Try Open Graph image
            try:
                og_img = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
                data["poster"] = og_img.get_attribute("content")
            except:
                data["poster"] = ""
        
        # If still empty, try to find any large image
        if not data["poster"]:
            try:
                images = driver.find_elements(By.TAG_NAME, "img")
                best_img = ""
                max_size = 0
                for img in images:
                    try:
                        src = img.get_attribute("src")
                        if not src or "svg" in src or "icon" in src:
                            continue
                        # We can't easily check size without downloading or JS, but we can check if it looks like a content image
                        if "boxart" in src or "poster" in src or "hero" in src:
                            data["poster"] = src
                            break
                    except:
                        continue
            except:
                pass

        # Genres, Cast, etc.
        # These are often in a "More Details" section or just listed
        data["genre"] = ""
        data["genres"] = ""
        data["creators"] = ""
        data["cast"] = ""
        data["starring"] = ""
        
        try:
            tags = driver.find_elements(By.CSS_SELECTOR, "div.more-details-cell")
            for tag in tags:
                label = tag.find_element(By.CSS_SELECTOR, "span.more-details-label").text
                value = tag.text.replace(label, "").strip()
                
                if "Genres" in label:
                    data["genres"] = value
                    data["genre"] = value.split(",")[0] if value else ""
                elif "Cast" in label:
                    data["cast"] = value
                    data["starring"] = ", ".join(value.split(",")[:3])
                elif "Creator" in label:
                    data["creators"] = value
        except:
            pass

        # Fill missing fields with defaults
        data["show_characteristics"] = "Netflix Original"
        data["audio"] = "English"
        data["subtitles"] = "English"
        data["trailer_url"] = "" # Hard to get without playing

        # Episodes
        print("Scraping episodes...")
        data["seasons_data"] = []
        
        try:
            # Check if there is a season dropdown
            try:
                season_dropdown = driver.find_element(By.CSS_SELECTOR, "div.season-selector select, button.season-selector-button")
                # If it's a select
                if season_dropdown.tag_name == "select":
                    select = Select(season_dropdown)
                    season_options = [opt.text for opt in select.options]
                else:
                    # If it's a button (newer UI), might need to click to see list. 
                    # For now assume select or single season.
                    season_options = ["Season 1"] # Placeholder
            except:
                season_options = ["Season 1"] # Default if no selector (miniseries or 1 season)

            # Iterate seasons (simplified for now, might need more complex interaction for multiple seasons)
            # Note: Netflix often loads episodes dynamically.
            
            # For this task, we mainly want the IMAGES. 
            # Let's just scrape the currently visible episodes.
            
            season_episodes = []
            episode_elems = driver.find_elements(By.CSS_SELECTOR, "div.episode-item, li.episode")
            
            for ep in episode_elems:
                try:
                    # Title & Number
                    title_text = ep.find_element(By.CSS_SELECTOR, "h3.episode-title, span.episode-title").text
                except:
                    continue
        except:
            pass

    except Exception as e:
        print(f"Error in scrape_netflix: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()
        
    return data

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "Stranger Things"
    print(json.dumps(scrape_netflix(q), indent=4))

