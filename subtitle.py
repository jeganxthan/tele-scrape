
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
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

# Config
MOVIE_DIR = os.path.join(os.getcwd(), "movie")
BRAVE_PATH = "/usr/bin/brave-browser"  # Adjust if needed based on `which brave-browser`

def setup_driver():
    print("Setting up Brave driver...")
    chrome_options = Options()
    
    # Use Brave if available
    if os.path.exists(BRAVE_PATH):
        chrome_options.binary_location = BRAVE_PATH
        print(f"Using Brave binary at: {BRAVE_PATH}")
    else:
        print("Brave not found at default location, proceeding with default Chrome...")

    chrome_options.add_argument("--headless") # Comment out to see the browser
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--mute-audio")
    
    # Setup driver - using ChromeDriverManager but pointing to Brave binary
    # Note: For Brave, we still use ChromeDriver.
    # ChromeType.BRAVE can be flaky, so we use standard ChromeDriverManager which pulls latest chromedriver
    # This usually works if Brave is relatively up to date.
    service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    print("Driver setup successful.")
    return driver

def clean_movie_name(filename):
    # Remove extension
    name = os.path.splitext(filename)[0]
    # Replace dots, underscores with spaces
    name = name.replace('.', ' ').replace('_', ' ')
    # Try to clean up common scene tags
    # Example: Avengers.Age.of.Ultron.2015.1080p.BluRay -> Avengers Age of Ultron 2015
    # We strip everything after the year usually, or look for 1080p/720p/BluRay
    
    # Regex to find year (19xx or 20xx)
    match = re.search(r'\b(19|20)\d{2}\b', name)
    if match:
        # Keep up to the year
        end_idx = match.end()
        name = name[:end_idx]
    else:
        # If no year, just try to strip common tech words
        tech_words = ["1080p", "720p", "480p", "BluRay", "WEBRip", "BRRip", "YIFY", "x264", "x265", "subs"]
        for word in tech_words:
            idx = name.lower().find(word.lower())
            if idx != -1:
                name = name[:idx]
    
    return name.strip()

def download_subtitle(driver, movie_name, movie_dir):
    print(f"Searching for: {movie_name} on SubtitleCat")
    
    # Direct Search on SubtitleCat
    try:
        search_query = requests.utils.quote(movie_name)
        search_url = f"https://www.subtitlecat.com/index.php?search={search_query}"
        driver.get(search_url)
        time.sleep(2)  # Wait for page load

        # DEBUG: Dump source
        # with open("debug_page.html", "w") as f:
        #     f.write(driver.page_source)
        # print(" dumped page source to debug_page.html")
        
        # Check if we are on a list of results
        # Usually results are typical links. It seems to just list them.
        # Let's look for the first valid link that contains the movie name or "subtitles"
        
        # Based on user description, they clicked the "first link" on Google which took them to a page.
        # A direct search on subtitlecat probably lists movies.
        # Let's click the first result (table row or first link).
        
        # NOTE: I need to guess the structure of search results since I missed the HTML dump.
        # But usually main content is in a table or list.
        # Let's look for <a> tags in the main content area.
        
        # Heuristic: Find first <a> that has "subtitle" in href or title, or just the first main link.
        # Or look for class similar to "movie-link"
        
        # Let's try to just click the first link in the first column of the results table/list if existing.
        # Else, assume we might be directly on the page (unlikely).
        
        links = driver.find_elements(By.TAG_NAME, "a")
        target_page_link = None
        target_href = None
        
        query_parts = movie_name.lower().split()
        
        candidates = []
        for link in links:
            try:
                href = link.get_attribute("href")
                text = link.text.lower()
                if href and "/subs/" in href:
                    # Check if all parts of query are in text
                    if all(part in text for part in query_parts):
                         candidates.append((link, href)) # Store href
            except:
                continue

        if candidates:
             # Pick the first one that matches all words
             target_page_link, target_href = candidates[0]
             print(f"Found {len(candidates)} matching candidates. Picking: {target_page_link.text}")
        elif links: 
             # Fallback: Pick first /subs/ link if no exact match (risky but better than nothing)
             # But maybe we should just fail or print
             pass

        if target_href:
            print(f"Navigating to result: {target_href}")
            driver.get(target_href)
            time.sleep(3)
        else:
             print("No results found or already on page.")
        
        # Find STRICTLY English subtitle only
        sub_singles = driver.find_elements(By.CSS_SELECTOR, "div.sub-single")
        print(f"Found {len(sub_singles)} subtitle options.")
        
        target_link = None
        english_candidates = []
        
        for sub in sub_singles:
            try:
                is_english = False
                english_confidence = 0  # Track how confident we are it's English
                
                # Method 1: Check flag image (most reliable)
                try:
                    flag_img = sub.find_element(By.CSS_SELECTOR, "img.flag")
                    alt = flag_img.get_attribute("alt")
                    if alt and alt.lower() in ['en', 'gb', 'us', 'english']:
                        is_english = True
                        english_confidence += 3
                        print(f"  ✓ Found English flag: {alt}")
                except:
                    pass
                
                # Method 2: Check visible text for "English" (case-insensitive)
                sub_text = sub.text
                if "english" in sub_text.lower():
                    is_english = True
                    english_confidence += 2
                    print(f"  ✓ Found 'English' in text")
                
                # Method 3: Check link filename for English markers
                try:
                    link = sub.find_element(By.TAG_NAME, "a")
                    link_href = link.get_attribute("href")
                    if link_href:
                        link_href_lower = link_href.lower()
                        # Look for explicit English markers in filename
                        english_markers = ["-en.", ".eng.", "_en.", ".english.", "-english-", "_english_", ".en."]
                        if any(marker in link_href_lower for marker in english_markers):
                            is_english = True
                            english_confidence += 1
                            print(f"  ✓ Found English marker in filename")
                except:
                    pass
                
                # STRICT: Only accept if we have clear English indicators
                if is_english and english_confidence >= 2:
                    try:
                        link = sub.find_element(By.TAG_NAME, "a")
                        link_href = link.get_attribute("href")
                        if "download" in link.text.lower():
                            english_candidates.append((link, link_href, english_confidence))
                            print(f"  ✅ Valid English subtitle candidate (confidence: {english_confidence})")
                    except:
                        pass
                elif is_english:
                    print(f"  ⚠️ Skipping subtitle with low English confidence ({english_confidence})")
                    
            except Exception as e:
                continue
        
        # Pick the subtitle with highest English confidence
        if english_candidates:
            # Sort by confidence (highest first)
            english_candidates.sort(key=lambda x: x[2], reverse=True)
            target_link, link_href, confidence = english_candidates[0]
            print(f"\n✅ Selected ENGLISH subtitle (confidence: {confidence}): {link_href}")
        else:
            print("\n❌ No STRICTLY English subtitle found")
                
        if target_link:
            print("Found English subtitle. Downloading...")
            href = target_link.get_attribute("href")
            # ... (rest of download logic) ...
            
            # Construct full URL if relative
            if href.startswith("/"):
                base_url = "https://subtitlecat.com" # Assuming based on context
                # Actually we should get current url from driver to be safe about domain
                current_url = driver.current_url
                parsed_uri = requests.utils.urlparse(current_url)
                base_url = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
                href = base_url + href
            
            # Download with requests
            try:
                cookies = driver.get_cookies()
                session = requests.Session()
                for cookie in cookies:
                    session.cookies.set(cookie['name'], cookie['value'])
                
                # Fake headers
                headers = {
                    "User-Agent": driver.execute_script("return navigator.userAgent")
                }
                
                r = session.get(href, headers=headers)
                if r.status_code == 200:
                    # Determine filename
                    content_disp = r.headers.get("Content-Disposition")
                    sub_filename = None
                    if content_disp:
                        fname_match = re.search(r'filename="?([^"]+)"?', content_disp)
                        if fname_match:
                            sub_filename = fname_match.group(1)
                    
                    if not sub_filename:
                        sub_filename = f"{movie_name}.srt"
                    
                    # Ensure it ends with .srt (sometimes it's .zip)
                    save_path = os.path.join(movie_dir, sub_filename)
                    with open(save_path, "wb") as f:
                        f.write(r.content)
                    print(f"Downloaded subtitle to: {save_path}")
                    return save_path
                else:
                    print(f"Failed to download URL: {href} Status: {r.status_code}")
                    return None
            except Exception as e:
                print(f"Download request failed: {e}")
                return None
        else:
            print(f"No English subtitle found on this page. Dumping source to debug_detail_{movie_name[:10]}.html")
            with open(f"debug_detail_{movie_name[:10].replace(' ', '_')}.html", "w") as f:
                f.write(driver.page_source)
            return None
            
    except Exception as e:
        print(f"Error during subtitle search/download: {e}")
        return None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Download subtitles and optionally upload to FileMoon.")
    parser.add_argument("--skip-upload", action="store_true", help="Skip uploading subtitles to FileMoon")
    parser.add_argument("--headless", action="store_true", help="Run FileMoon upload in headless mode")
    args = parser.parse_args()

    if not os.path.exists(MOVIE_DIR):
        print(f"Movie directory not found: {MOVIE_DIR}")
        return

    # Get list of video files
    video_extensions = ('.mp4', '.mkv', '.avi')
    video_files = [f for f in os.listdir(MOVIE_DIR) if f.lower().endswith(video_extensions) and "burned" not in f.lower()]
    
    if not video_files:
        print("No video files found.")
        return

    driver = setup_driver()
    
    # Import FileMoon uploader if needed
    filemoon_uploader = None
    if not args.skip_upload:
        try:
            import filemoon_subtitle_uploader
            filemoon_uploader = filemoon_subtitle_uploader
            print("✅ FileMoon uploader loaded")
        except ImportError as e:
            print(f"⚠️ FileMoon uploader not available: {e}")
            print("Continuing with download-only mode...")
    
    try:
        upload_results = {"success": 0, "failed": 0, "skipped": 0}
        
        for video_file in video_files:
            print(f"\n{'='*60}")
            print(f"Processing: {video_file}")
            print(f"{'='*60}")
            full_video_path = os.path.join(MOVIE_DIR, video_file)
            
            clean_name = clean_movie_name(video_file)
            print(f"Cleaned Query: {clean_name}")
            
            # Download Subtitle
            sub_path = download_subtitle(driver, clean_name, MOVIE_DIR)
            
            if sub_path:
                print(f"✓ Subtitle downloaded successfully: {sub_path}")
                
                # Upload to FileMoon if not skipped
                if not args.skip_upload and filemoon_uploader:
                    print(f"\n📤 Uploading subtitle to FileMoon...")
                    try:
                        upload_success = filemoon_uploader.upload_subtitle_to_filemoon(
                            video_file, 
                            sub_path, 
                            headless=args.headless
                        )
                        if upload_success:
                            print(f"✅ Subtitle uploaded to FileMoon for {video_file}")
                            upload_results["success"] += 1
                        else:
                            print(f"❌ Failed to upload subtitle to FileMoon for {video_file}")
                            upload_results["failed"] += 1
                    except Exception as e:
                        print(f"❌ Error during FileMoon upload: {e}")
                        upload_results["failed"] += 1
                else:
                    if args.skip_upload:
                        print("⏭️  Skipping FileMoon upload (--skip-upload flag)")
                    upload_results["skipped"] += 1
            else:
                print("✗ Failed to download subtitle.")
                upload_results["skipped"] += 1
        
        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Total videos processed: {len(video_files)}")
        if not args.skip_upload and filemoon_uploader:
            print(f"FileMoon uploads successful: {upload_results['success']}")
            print(f"FileMoon uploads failed: {upload_results['failed']}")
            print(f"Skipped: {upload_results['skipped']}")
        print(f"{'='*60}")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    main()

