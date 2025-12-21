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

def scrape_hotstar(query):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {}

    try:
        print(f"Navigating to JioHotstar to search for: {query}")
        print(f"Navigating to JioHotstar to search for: {query}")
        # Search via DuckDuckGo HTML
        driver.get(f"https://duckduckgo.com/html/?q=site:hotstar.com/in/shows+{query.replace(' ', '+')}")
        time.sleep(3)
        
        try:
            first_result = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.result__a")))
            hotstar_url = first_result.get_attribute("href")
            print(f"Found Hotstar URL: {hotstar_url}")
            driver.get(hotstar_url)
        except Exception as e:
            print(f"Could not find Hotstar URL via DuckDuckGo: {e}")
            return None

        time.sleep(5)

        # Scrape details
        print("Scraping show details...")
        
        # Title
        try:
            data["show_title"] = driver.find_element(By.CSS_SELECTOR, "h1.title").text
        except:
            try:
                data["show_title"] = driver.find_element(By.CSS_SELECTOR, "div.content-title").text
            except:
                data["show_title"] = query

        # Metadata
        try:
            meta_items = driver.find_elements(By.CSS_SELECTOR, "div.meta-data span")
            texts = [m.text for m in meta_items]
            data["year"] = next((t for t in texts if re.match(r'\d{4}', t)), "Unknown")
            data["rating"] = next((t for t in texts if t in ["U/A 16+", "A", "U", "18+", "15+"]), "U/A 16+")
            data["seasons"] = next((t for t in texts if "Season" in t), "Unknown")
        except:
            data["year"] = ""
            data["rating"] = ""
            data["seasons"] = ""

        try:
            data["description"] = driver.find_element(By.CSS_SELECTOR, "div.description").text
        except:
            data["description"] = ""

        # Images
        try:
            # Try to find the hero image
            img = driver.find_element(By.CSS_SELECTOR, "div.masthead-container img, img.shimmer-img")
            data["poster"] = img.get_attribute("src")
        except:
            # Fallback: Try Open Graph image
            try:
                og_img = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
                data["poster"] = og_img.get_attribute("content")
            except:
                data["poster"] = ""
        
        # If still empty, try to find any large image
        if not data["poster"] or "logo.png" in data["poster"]:
            data["poster"] = "" # Reset if it was the logo
            try:
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for img in imgs:
                    try:
                        src = img.get_attribute("src")
                        if not src: continue
                        # Hotstar images often have 'h_493' or similar dimensions in URL
                        if ("hotstar.com" in src or "akamaized.net" in src) and "logo" not in src:
                            data["poster"] = src
                            break
                    except:
                        continue
            except:
                pass
        
        data["series_logo"] = data.get("poster", "")

        # Genres, Cast
        data["genre"] = ""
        data["genres"] = ""
        data["creators"] = ""
        data["cast"] = ""
        data["starring"] = ""
        
        # Hotstar often puts genres in metadata
        try:
            genre_el = driver.find_element(By.CSS_SELECTOR, "div.genre-list")
            data["genres"] = genre_el.text
            data["genre"] = data["genres"].split(",")[0]
        except:
            pass

        # Episodes - SKIPPED (Using IMDb for episodes)
        data["seasons_data"] = []

    except Exception as e:
        print(f"Error in scrape_hotstar: {e}")
    finally:
        driver.quit()
        
    return data

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "The Last of Us"
    print(json.dumps(scrape_hotstar(q), indent=4))
