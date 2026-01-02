import os
import sys
import time
import re
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

def setup_driver():
    print("Setting up Chrome driver...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--mute-audio") # Mute audio to prevent playback sound
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("Chrome driver setup successful.")
    return driver

def download_file(url, folder, filename, cookies):
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # Sanitize filename
    filename = "".join([c for c in filename if c.isalnum() or c in (' ', '.', '-', '_')]).strip()
    filepath = os.path.join(folder, filename)
    
    if os.path.exists(filepath) and os.path.getsize(filepath) > 1024 * 1024: # Check if file exists and is > 1MB
        print(f"    Skipping {filename}, already exists and seems valid.")
        return

    print(f"    Downloading {filename}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://animeheaven.me/"
    }
    
    session_cookies = {c['name']: c['value'] for c in cookies}
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with requests.get(url, headers=headers, cookies=session_cookies, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
            print(f"    Finished downloading {filename}")
            return # Success, exit function
        except Exception as e:
            print(f"    Error downloading {filename} (Attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = 5 * (attempt + 1)
                print(f"    Waiting {wait_time}s before retrying...")
                time.sleep(wait_time)
            else:
                print(f"    Failed to download {filename} after {max_retries} attempts.")
                if os.path.exists(filepath):
                    os.remove(filepath)

def scrape_anime(query):
    driver = setup_driver()
    try:
        # 1. Search
        search_url = f"https://animeheaven.me/search.php?s={requests.utils.quote(query)}"
        print(f"Searching for: {query}")
        driver.get(search_url)
        
        # Get all matching anime containers from search results
        containers = driver.find_elements(By.CSS_SELECTOR, ".similarimg")
        if not containers:
            print("No results found.")
            return

        anime_links = []
        for container in containers:
            try:
                link_elem = container.find_element(By.CSS_SELECTOR, ".similarname a")
                link = link_elem.get_attribute("href")
                name = link_elem.text
                if query.lower() in name.lower():
                    anime_links.append((name, link))
            except:
                continue

        print(f"Found {len(anime_links)} series matching '{query}'.")
        DOWNLOAD_ROOT = os.path.join(os.getcwd(), "downloads")

        main_folder = os.path.join(DOWNLOAD_ROOT, query.title())
        if not os.path.exists(main_folder):
            os.makedirs(main_folder)

        episode_counter = 1
        for series_name, series_link in anime_links:
            print(f"\nProcessing Series: {series_name}")
            
            # Pre-list existing files to skip faster
            existing_files = []
            if os.path.exists(main_folder):
                existing_files = [f for f in os.listdir(main_folder) if f.lower().endswith('.mp4')]
                # Only consider valid files (>1MB)
                existing_files = [f for f in existing_files if os.path.getsize(os.path.join(main_folder, f)) > 1024 * 1024]

            driver.get(series_link)
            
            # 2. Get Episode Metadata (ID and Episode Number)
            # The IDs are in the <a> tags
            episode_elements = driver.find_elements(By.CSS_SELECTOR, "a.c:has(div.trackep0.watch)")
            
            episodes = []
            for el in episode_elements:
                ep_id = el.get_attribute("id")
                try:
                    ep_num = el.find_element(By.CSS_SELECTOR, ".watch2").text.strip()
                    ep_num = "".join(filter(str.isdigit, ep_num)) # Keep only digits for safer matching
                    episodes.append({"id": ep_id, "num": ep_num})
                except:
                    continue
            
            # Reverse to start from Episode 1
            episodes.reverse()
            print(f"Found {len(episodes)} episodes.")

            for ep_data in episodes:
                try:
                    ep_id = ep_data["id"]
                    ep_num = ep_data["num"]
                    
                    # Quick check if episode already exists
                    # Look for "{query} {episode_counter}.mp4"
                    existing_files_lower = {f.lower() for f in existing_files}
                    target_filename = f"{query.title()} {episode_counter}.mp4"
                    
                    if target_filename.lower() in existing_files_lower:
                        print(f"  Skipping Episode {ep_num}, already exists as {target_filename}.")
                        episode_counter += 1
                        continue

                    print(f"  Scraping Episode {ep_num} (ID: {ep_id})...")
                    
                    # Navigate to series page again if needed, or just set cookie and go to gate.php
                    # Actually, clicking the element is more reliable
                    try:
                        ep_btn = driver.find_element(By.ID, ep_id)
                        driver.execute_script("arguments[0].click();", ep_btn)
                    except:
                        # If element not found (maybe page changed), reload and click
                        driver.get(series_link)
                        ep_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, ep_id)))
                        driver.execute_script("arguments[0].click();", ep_btn)
                    
                    video_url = None
                    
                    if not video_url:
                        # Try to find video URL in source tags
                        sources = driver.find_elements(By.CSS_SELECTOR, "video source")
                        for src in sources:
                            s_url = src.get_attribute("src")
                            if s_url and ".mp4" in s_url:
                                if "error" not in s_url:
                                    video_url = s_url
                                    break
                                video_url = s_url

                        if not video_url:
                            try:
                                video_elem = driver.find_element(By.TAG_NAME, "video")
                                video_url = video_elem.get_attribute("src")
                            except:
                                pass
                        
                        if not video_url:
                            scripts = driver.find_elements(By.TAG_NAME, "script")
                            for script in scripts:
                                content = script.get_attribute("innerHTML")
                                if ".mp4" in content:
                                    match = re.search(r'(https://[^"\']+\.mp4[^"\']*)', content)
                                    if match:
                                        video_url = match.group(1).replace("&amp;", "&")
                                        break
                    
                    # Wait for title to update and video to appear
                    time.sleep(2) # Reduced from 3 to 2
                    
                    if video_url:
                        filename = f"{query.title()} {episode_counter}.mp4"
                        download_file(video_url, main_folder, filename, driver.get_cookies())
                        episode_counter += 1
                    else:
                        print(f"    Could not find video URL for Episode {ep_num}")
                        
                except Exception as e:
                    print(f"    Error processing episode: {e}")
                    continue

    finally:
        driver.quit()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 anime.py \"anime name\"")
    else:
        print("DEBUG: Calling scrape_anime with:", sys.argv[1])
        scrape_anime(sys.argv[1])
