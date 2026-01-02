import os
import time
import zipfile
import re
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def get_clean_movie_name(folder_name):
    # Remove content in brackets [] and parentheses ()
    clean_name = re.sub(r'\[.*?\]', '', folder_name)
    clean_name = re.sub(r'\(.*?\)', '', clean_name)
    # Remove extra spaces
    clean_name = " ".join(clean_name.split())
    # Add year if found in original folder to be more specific?
    # For now, let's keep it simple. The user example "Avengers Infinity War (2018)..." 
    # cleans to "Avengers Infinity War".
    # It might be useful to keep the year if possible.
    match = re.search(r'\((\d{4})\)', folder_name)
    if match:
        clean_name += f" {match.group(1)}"
    return clean_name

def download_subtitle(movie_name, download_dir):
    print(f"Searching subtitles for: {movie_name}")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.set_capability("pageLoadStrategy", "eager") # Don't wait for full resources/ads
    
    # Set download directory
    prefs = {"download.default_directory": str(download_dir)}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    
def download_from_opensubtitles(driver, movie_name, download_dir):
    try:
        # Construct specific English search URL to avoid picking random languages
        # URL encoding the movie name
        import urllib.parse
        encoded_name = urllib.parse.quote(movie_name)
        search_url = f"https://www.opensubtitles.org/en/search2/sublanguageid-eng/moviename-{encoded_name}"
        
        print(f"Navigating to OpenSubtitles English search: {search_url}")
        driver.get(search_url)
        
        print("Waiting for results...")
        try:
             WebDriverWait(driver, 5).until(
                lambda d: d.find_elements(By.XPATH, "//a[contains(@href, '/subtitles/')]")
            )
        except:
             pass

        print(f"Page Title: {driver.title}")
        
        target_link = None
        all_subs = driver.find_elements(By.XPATH, "//a[contains(@href, '/subtitles/')]")
        
        valid_subs = []
        for a in all_subs:
            href = a.get_attribute("href")
            if re.search(r'/subtitles/\d+/', href):
                valid_subs.append(href)
        
        if valid_subs:
            target_link = valid_subs[0]
            print(f"Found {len(valid_subs)} English subtitles on OpenSubtitles. Picking first: {target_link}")
        else:
            print("No direct English subtitle links found on OpenSubtitles.")
            return None
        
        driver.get(target_link)
        
        try:
            download_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "bt-dwl"))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", download_btn)
            time.sleep(1) 
            print("Clicking OpenSubtitles download button via JS...")
            driver.execute_script("arguments[0].click();", download_btn)
            
        except Exception as e:
            print(f"Failed to crash-proof click on OpenSubtitles: {e}")
            return None
            
        return monitor_download(download_dir)

    except Exception as e:
        print(f"Error downloading from OpenSubtitles: {e}")
        return None

def download_from_subtitlecat(driver, movie_name, download_dir):
    print(f"Attempting download from SubtitleCat for: {movie_name}")
    try:
        driver.get("https://www.subtitlecat.com/")
        
        # Search
        search_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "search"))
        )
        search_input.clear()
        search_input.send_keys(movie_name)
        # Click search button or enter
        search_btn = driver.find_element(By.ID, "button-addon2")
        search_btn.click()
        
        try:
            # Wait for results
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "td a"))
            )
        except:
             print("No results found on SubtitleCat (timeout).")
             return None
        
        # Click first result
        results = driver.find_elements(By.CSS_SELECTOR, "td a")
        if not results:
            print("No results found on SubtitleCat.")
            return None
            
        first_result_href = results[0].get_attribute("href")
        print(f"Clicking first result: {first_result_href}")
        driver.get(first_result_href)
        
        # Find English download button (id="download_en")
        try:
            # Check if we are on the page with "download_en"
            download_link = WebDriverWait(driver, 5).until(
                 EC.presence_of_element_located((By.ID, "download_en"))
            )
            print(f"Found English download link: {download_link.get_attribute('href')}")
            
            # Simple click usually works for direct href
            driver.execute_script("arguments[0].click();", download_link)
            
            return monitor_download(download_dir)
            
        except:
             print("Direct English download button not found. Searching page for 'English'...")
             return None

    except Exception as e:
        print(f"Error downloading from SubtitleCat: {e}")
        return None

def monitor_download(download_dir, timeout=30):
    print("Waiting for file...")
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        files = list(download_dir.glob("*"))
        for f in files:
            if (f.suffix == '.zip' or f.suffix == '.srt') and (time.time() - f.stat().st_mtime < 60):
                print(f"Downloaded: {f.name}")
                if f.suffix == '.zip':
                    return extract_zip(f, download_dir)
                return f
        time.sleep(1)
        
    print("Download timed out.")
    return None

def extract_zip(zip_path, extract_to):
    print("Extracting zip...")
    final_srt = None
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
            for name in zip_ref.namelist():
                if name.endswith('.srt'):
                    final_srt = extract_to / name
                    break
        os.remove(zip_path)
    except zipfile.BadZipFile:
        print("Bad zip file.")
        return None
    return final_srt

def download_subtitle(movie_name, download_dir):
    print(f"Searching subtitles for: {movie_name}")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.set_capability("pageLoadStrategy", "eager")
    
    prefs = {"download.default_directory": str(download_dir)}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=chrome_options)
    driver.set_page_load_timeout(30)
    
    final_srt = None
    try:
        # Try OpenSubtitles first
        final_srt = download_from_opensubtitles(driver, movie_name, download_dir)
        
        # If failed, try SubtitleCat
        if not final_srt:
            print("OpenSubtitles failed or found nothing. Trying SubtitleCat...")
            final_srt = download_from_subtitlecat(driver, movie_name, download_dir)
            
    finally:
        driver.quit()
        
    return final_srt

if __name__ == "__main__":
    # Test
    # download_subtitle("Avengers Infinity War 2018", Path.cwd())
    pass
