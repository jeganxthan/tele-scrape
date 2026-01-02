import os
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

FILEMOON_USERNAME = os.getenv("FILEMOON_USERNAME")
FILEMOON_PASSWORD = os.getenv("FILEMOON_PASSWORD")
FILEMOON_DASHBOARD_URL = os.getenv("FILEMOON_DASHBOARD_URL", "https://filemoon.in/dashboard")
BRAVE_PATH = "/usr/bin/brave-browser"

def human_delay(min_sec=1, max_sec=3):
    """Add random delay to mimic human behavior"""
    time.sleep(random.uniform(min_sec, max_sec))

def setup_driver(headless=False):
    """Setup Selenium driver with anti-detection measures"""
    print("Setting up browser for FileMoon...")
    chrome_options = Options()
    
    # Use Brave if available
    if os.path.exists(BRAVE_PATH):
        chrome_options.binary_location = BRAVE_PATH
        print(f"Using Brave browser at: {BRAVE_PATH}")
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Anti-detection measures
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--mute-audio")
    
    # Randomize user agent slightly
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(30)
    
    # Execute CDP commands to hide webdriver
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": driver.execute_script("return navigator.userAgent").replace('Headless', '')
    })
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    print("Browser setup complete.")
    return driver

def login_to_filemoon(driver):
    """Login to FileMoon dashboard"""
    if not FILEMOON_USERNAME or not FILEMOON_PASSWORD:
        raise ValueError("FileMoon credentials not found in .env file. Please set FILEMOON_USERNAME and FILEMOON_PASSWORD")
    
    print("Logging into FileMoon...")
    
    # Navigate to login page
    driver.get("https://filemoon.in/login")
    human_delay(2, 4)
    
    try:
        # Wait for and fill username/login
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "login-name"))
        )
        human_delay(0.5, 1)
        username_field.send_keys(FILEMOON_USERNAME)
        
        human_delay(0.5, 1.5)
        
        # Fill password
        password_field = driver.find_element(By.ID, "login-pass")
        password_field.send_keys(FILEMOON_PASSWORD)
        
        human_delay(1, 2)
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        human_delay(3, 5)
        
        # Verify login success by checking if we're on dashboard
        if "dashboard" in driver.current_url.lower() or "videos" in driver.current_url.lower():
            print("✅ Successfully logged into FileMoon")
            return True
        else:
            print("❌ Login may have failed. Current URL:", driver.current_url)
            return False
            
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

def find_video_by_file_code(driver, file_code):
    """Navigate to video edit page using file code"""
    print(f"Navigating to edit page for file code: {file_code}")
    
    # Direct URL to edit page
    edit_url = f"https://filemoon.in/edit/file/{file_code}"
    driver.get(edit_url)
    human_delay(2, 4)
    
    # Verify we're on the edit page
    if f"/edit/file/{file_code}" in driver.current_url:
        print(f"✅ Successfully navigated to edit page for {file_code}")
        return True
    else:
        print(f"❌ Failed to navigate to edit page. Current URL: {driver.current_url}")
        return False

def upload_subtitle(driver, subtitle_path, language="English"):
    """Upload subtitle file to FileMoon video"""
    print(f"Uploading subtitle: {subtitle_path}")
    
    if not os.path.exists(subtitle_path):
        print(f"❌ Subtitle file not found: {subtitle_path}")
        return False
    
    try:
        # Wait for the subtitle upload section
        human_delay(1, 2)
        
        # Find the file input for subtitle upload
        # Based on the screenshot, look for file input in the "Choose Subtitles" section
        file_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
        
        subtitle_input = None
        for input_elem in file_inputs:
            # Look for the one related to subtitles (might have specific name or nearby label)
            parent_text = input_elem.find_element(By.XPATH, "./ancestor::div[contains(@class, 'form') or contains(@class, 'upload')]").text.lower()
            if "subtitle" in parent_text or "sub" in parent_text:
                subtitle_input = input_elem
                break
        
        if not subtitle_input:
            # Fallback: try to find by looking for "Browse" button context
            print("Trying alternative method to find subtitle input...")
            subtitle_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file'][accept*='srt'], input[type='file'][accept*='subtitle']"))
            )
        
        if subtitle_input:
            # Upload the file
            subtitle_input.send_keys(os.path.abspath(subtitle_path))
            print(f"✅ Subtitle file selected: {os.path.basename(subtitle_path)}")
            human_delay(1, 2)
            
            # Select language from dropdown if available
            try:
                language_dropdown = Select(driver.find_element(By.NAME, "subtitle_language"))
                language_dropdown.select_by_visible_text(language)
                print(f"✅ Language set to: {language}")
                human_delay(0.5, 1)
            except NoSuchElementException:
                print("⚠️ Language dropdown not found, skipping...")
            
            # Click "Upload Subtitles" button
            upload_buttons = driver.find_elements(By.TAG_NAME, "button")
            for button in upload_buttons:
                if "upload" in button.text.lower() and "subtitle" in button.text.lower():
                    human_delay(1, 2)
                    button.click()
                    print("✅ Clicked 'Upload Subtitles' button")
                    human_delay(3, 5)
                    break
            
            # Verify upload success
            # Look for success message or subtitle appearing in the list
            try:
                success_indicator = driver.find_element(By.XPATH, "//*[contains(text(), 'success') or contains(text(), 'uploaded')]")
                print("✅ Subtitle uploaded successfully!")
                return True
            except NoSuchElementException:
                print("⚠️ Upload completed but couldn't verify success message")
                return True
                
        else:
            print("❌ Could not find subtitle file input")
            return False
            
    except Exception as e:
        print(f"❌ Error uploading subtitle: {e}")
        # Save screenshot for debugging
        try:
            screenshot_path = f"filemoon_upload_error_{int(time.time())}.png"
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved: {screenshot_path}")
        except:
            pass
        return False

def get_file_code_from_csv(video_filename, csv_path="filemoon_files.csv"):
    """Get FileMoon file code from CSV by matching video filename"""
    import csv
    
    if not os.path.exists(csv_path):
        print(f"⚠️ CSV file not found: {csv_path}")
        return None
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Match by filename or title
                csv_filename = row.get('filename') or row.get('title', '')
                if video_filename in csv_filename or (video_filename and os.path.splitext(video_filename)[0] in csv_filename):
                    file_code = row.get('file_code', '')
                    if file_code:
                        print(f"✅ Found file code for {video_filename}: {file_code}")
                        return file_code
        
        print(f"⚠️ No file code found for {video_filename} in CSV")
        return None
        
    except Exception as e:
        print(f"❌ Error reading CSV: {e}")
        return None

def upload_subtitle_to_filemoon(video_filename, subtitle_path, headless=False):
    """
    Main function to upload subtitle to FileMoon for a specific video
    
    Args:
        video_filename (str): Name of the video file
        subtitle_path (str): Path to the subtitle file
        headless (bool): Run browser in headless mode
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Get file code from CSV
    file_code = get_file_code_from_csv(video_filename)
    if not file_code:
        print(f"❌ Cannot upload subtitle: file code not found for {video_filename}")
        return False
    
    driver = None
    try:
        driver = setup_driver(headless=headless)
        
        # Login
        if not login_to_filemoon(driver):
            return False
        
        # Navigate to video edit page
        if not find_video_by_file_code(driver, file_code):
            return False
        
        # Upload subtitle
        success = upload_subtitle(driver, subtitle_path)
        
        return success
        
    except Exception as e:
        print(f"❌ Error in upload process: {e}")
        return False
        
    finally:
        if driver:
            human_delay(2, 3)
            driver.quit()
            print("Browser closed.")

if __name__ == "__main__":
    # Test the uploader
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python filemoon_subtitle_uploader.py <video_filename> <subtitle_path>")
        sys.exit(1)
    
    video_filename = sys.argv[1]
    subtitle_path = sys.argv[2]
    
    success = upload_subtitle_to_filemoon(video_filename, subtitle_path, headless=False)
    
    if success:
        print("\n✅ Subtitle upload completed successfully!")
    else:
        print("\n❌ Subtitle upload failed!")
