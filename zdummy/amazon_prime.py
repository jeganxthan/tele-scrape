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

def scrape_amazon(query):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {}

    try:
        print(f"Navigating to Amazon Prime to search for: {query}")
        print(f"Navigating to Amazon Prime to search for: {query}")
        # Search via DuckDuckGo HTML
        driver.get(f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}+amazon+prime+video")
        time.sleep(3)
        
        try:
            first_result = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "a.result__a")))
            amazon_url = first_result.get_attribute("href")
            print(f"Found Amazon URL: {amazon_url}")
            driver.get(amazon_url)
        except Exception as e:
            print(f"Could not find Amazon URL via DuckDuckGo: {e}")
            return None

        time.sleep(5)

        # Scrape details
        print("Scraping show details...")
        
        # Title
        try:
            data["show_title"] = driver.find_element(By.CSS_SELECTOR, "h1[data-automation-id='title']").text
        except:
            data["show_title"] = query

        # Metadata
        try:
            data["year"] = driver.find_element(By.CSS_SELECTOR, "span[data-automation-id='release-year-badge']").text
        except:
            data["year"] = ""
            
        try:
            data["rating"] = driver.find_element(By.CSS_SELECTOR, "span[data-automation-id='rating-badge']").text
        except:
            data["rating"] = "18+"

        try:
            data["description"] = driver.find_element(By.CSS_SELECTOR, "div[data-automation-id='synopsis']").text
        except:
            data["description"] = ""

        # Images
        try:
            # Hero image or cover
            img = driver.find_element(By.CSS_SELECTOR, "img._1G5d, img.V5X5, img[alt*='Poster'], img[alt*='Cover']") 
            data["poster"] = img.get_attribute("src")
        except:
            # Fallback: Try Open Graph image
            try:
                og_img = driver.find_element(By.CSS_SELECTOR, "meta[property='og:image']")
                data["poster"] = og_img.get_attribute("content")
            except:
                data["poster"] = ""
        
        # If still empty, try to find any large image
        if not data["poster"] or "seo-logo" in data["poster"]:
            data["poster"] = "" # Reset if it was the logo
            try:
                imgs = driver.find_elements(By.TAG_NAME, "img")
                for i in imgs:
                    src = i.get_attribute("src")
                    if src and "m.media-amazon.com" in src and ("_V1_" in src or "SX" in src):
                        # Check if it's not a tiny icon or logo
                        if "icon" not in src and "logo" not in src:
                            data["poster"] = src
                            break
            except:
                pass
        
        data["series_logo"] = data.get("poster", "")

        # Genres, Cast
        data["genre"] = ""
        data["genres"] = ""
        data["creators"] = ""
        data["cast"] = ""
        data["starring"] = ""
        
        try:
            meta_rows = driver.find_elements(By.CSS_SELECTOR, "div[data-automation-id='meta-info']")
            for row in meta_rows:
                text = row.text
                if "Genres" in text:
                    data["genres"] = text.replace("Genres", "").strip()
                    data["genre"] = data["genres"].split(",")[0]
                elif "Starring" in text:
                    data["starring"] = text.replace("Starring", "").strip()
                    data["cast"] = data["starring"]
        except:
            pass

        # Episodes
        print("Scraping episodes...")
        data["seasons_data"] = []
        
    except Exception as e:
        print(f"Error in scrape_amazon: {e}")
    finally:
        driver.quit()
        
    return data

if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "The Boys"
    print(json.dumps(scrape_amazon(q), indent=4))
