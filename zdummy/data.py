import json
import time
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

def scrape_episode_images(driver, wait):
    """Scrapes episode images from the current view."""
    images = []
    try:
        # Wait for at least one episode image to be present
        # User provided class: _21vZ2G_wEIYD0ldl4ro03R
        # We'll use that and a fallback
        print("Finding episode images...")
        # Scroll down to ensure lazy loaded images are loaded
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        img_elements = driver.find_elements(By.CSS_SELECTOR, "img._21vZ2G_wEIYD0ldl4ro03R, article img")
        for img in img_elements:
            src = img.get_attribute("src")
            if src:
                images.append(src)
    except Exception as e:
        print(f"Error scraping episode images: {e}")
    return images

def scrape_hotstar(query="the lost of us"):
    driver = setup_driver()
    wait = WebDriverWait(driver, 20)
    data = {"main_image": None, "episodes": {}}

    try:
        # 1. Go to Explore
        print("Navigating to Hotstar Explore...")
        driver.get("https://www.hotstar.com/in/explore")
        
        # 2. Click Search Bar
        print(f"Searching for '{query}'...")
        search_bar = wait.until(EC.element_to_be_clickable((By.ID, "searchBar")))
        search_bar.click()
        search_bar.send_keys(query)
        
        # 3. Click the specific result
        print("Waiting for results...")
        # Case-insensitive search using the query
        lower_query = query.lower()
        xpath_query = f"//p[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{lower_query}')]"
        
        try:
            result = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_query)))
            result.click()
        except Exception:
            print("Exact/Fuzzy text match not found, trying first result...")
            # Fallback: Click the first result card/title
            # Selector for result title: p._1zc788KtPN0EmaoSx7RUA_ (from user snippet)
            # or just generic p with class ON_SURFACE_DEFAULT
            first_result = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "p.ON_SURFACE_DEFAULT, a.ON_SURFACE_DEFAULT")))
            first_result.click()
        
        # Wait for show page to load
        time.sleep(3) 

        # 4. Scrape URL of the main image
        print("Scraping show image...")
        try:
            img_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[data-testid='image-element']")))
            data['main_image'] = img_element.get_attribute("src")
        except Exception as e:
            print(f"Error scraping main image: {e}")

        # 5. Scrape Season 1 Episodes
        print("Scraping Season 1 episodes...")
        data['episodes']['Season 1'] = scrape_episode_images(driver, wait)

        # 6. Switch to Season 2 (if exists) and Scrape
        try:
            print("Checking for Season 2...")
            # Try to find Season 2 button/tab
            season2_btn = driver.find_element(By.XPATH, "//span[contains(text(), 'Season 2')] | //button[contains(text(), 'Season 2')]")
            
            # Scroll to it just in case
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", season2_btn)
            time.sleep(0.5)
            
            driver.execute_script("arguments[0].click();", season2_btn)
            time.sleep(3) # Wait for content load
            
            print("Scraping Season 2 episodes...")
            data['episodes']['Season 2'] = scrape_episode_images(driver, wait)
            
        except Exception as e:
            print(f"Season 2 not found or could not be clicked: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")
        # driver.save_screenshot("error_screenshot.png") # Optional

    finally:
        driver.quit()
        
        # 7. Save to JSON (optional, but good for debugging)
        with open("hotstar_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print("Data saved to hotstar_data.json")
        
    return data

if __name__ == "__main__":
    scrape_hotstar()
