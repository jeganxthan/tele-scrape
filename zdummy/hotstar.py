# hotstar_last_of_us_scraper.py
import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- CONFIG ----------
SEARCH_TEXT = "last of us"
OUTPUT_FILE = "last_of_us_hotstar.json"
HOTSTAR_URL = "https://www.hotstar.com/in/explore"
# ----------------------------

def start_driver():
    chrome_options = Options()
    # comment out headless if site blocks automation or you want to see the browser
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(options=chrome_options)
    driver.set_window_size(1280, 900)
    return driver

def safe_find(driver, by, selector, timeout=10):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except Exception:
        return None

def safe_find_all(driver, by, selector, timeout=8):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, selector)))
    except Exception:
        return []

def click_element(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center', inline:'center'});", el)
        WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, ".")))  # quick check
        el.click()
        return True
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", el)
            return True
        except Exception:
            return False

def extract_text_or_none(el):
    try:
        t = el.text.strip()
        return t if t else None
    except:
        return None

def main():
    driver = start_driver()
    try:
        driver.get(HOTSTAR_URL)
        wait = WebDriverWait(driver, 15)

        # Wait for search bar by id 'searchBar' (provided in user's HTML)
        search_input = safe_find(driver, By.ID, "searchBar", timeout=12)
        if not search_input:
            # fallback: try input with placeholder text
            inputs = driver.find_elements(By.XPATH, "//input[contains(@placeholder, 'Movies, shows and more') or contains(@placeholder, 'Search')]")
            search_input = inputs[0] if inputs else None

        if not search_input:
            print("Search input not found; try running the script with visible browser (non-headless) and check selectors.")
            driver.quit()
            return

        # Focus + type
        try:
            search_input.clear()
        except:
            pass
        search_input.send_keys(SEARCH_TEXT)
        time.sleep(0.6)
        # Press Enter to perform search
        search_input.send_keys(Keys.ENTER)

        # wait for results container
        time.sleep(1.0)
        # Try to click the exact show name "The Last Of Us"
        # There may be several ways the title is shown; use XPath contains text
        show_elem = None
        try:
            show_elem = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    "//p[contains(normalize-space(.), 'The Last Of Us') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'last of us')]"
                ))
            )
        except Exception:
            # sometimes result is an anchor or span
            candidates = driver.find_elements(By.XPATH, "//*[contains(text(), 'The Last Of Us') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'last of us')]")
            show_elem = candidates[0] if candidates else None

        if not show_elem:
            print("Show element 'The Last Of Us' not found in results. Inspect selectors or try non-headless mode.")
            driver.quit()
            return

        # Click the show to go to details page
        driver.execute_script("arguments[0].click();", show_elem)
        time.sleep(1.5)

        # Wait for details page to load some identifying element
        # We'll attempt to grab title and poster
        time.sleep(2.0)
        details = {}

        # Title
        title_el = safe_find(driver, By.XPATH, "//h1 | //h2 | //p[contains(@class,'TITLE') and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'last of us')]", timeout=6)
        if title_el:
            details["show_title"] = extract_text_or_none(title_el)
        else:
            # fallback: read document title
            details["show_title"] = driver.title

        # Try to extract poster image (common approach: img with role img or poster class)
        poster_url = None
        try:
            imgs = driver.find_elements(By.XPATH, "//img[contains(@src, 'http') and (contains(@class,'poster') or contains(@alt, 'poster') or contains(@class,'Image') )]")
            if imgs:
                poster_url = imgs[0].get_attribute("src")
        except:
            poster_url = None
        details["Poster"] = poster_url

        # Rating / year / seasons / languages: try to find the container with tags (user provided html examples)
        try:
            # Attempt to read the tag block with data-testid or classes
            tag_block = safe_find(driver, By.XPATH, "//*[@data-testid='tagFlipperEnriched' or contains(@class,'tagFlipperDetailsPage') or contains(@class,'tagFlipper')]", timeout=6)
            if tag_block:
                # collect inner text tags (each span with text)
                tags = []
                for span in tag_block.find_elements(By.XPATH, ".//span//span"):
                    txt = span.text.strip()
                    if txt and len(txt) < 60:
                        tags.append(txt)
                details["genres_or_tags"] = tags
        except:
            details["genres_or_tags"] = []

        # Another block for year / rating / seasons etc (the long div in user's HTML)
        try:
            meta_block = driver.find_element(By.XPATH, "//*[contains(@aria-label,'Release Year') or contains(@class,'_3m3OVvWz9fNSmKyL59AI89') or contains(@data-testid,'textTag')]")
            meta_text = meta_block.text.strip()
            details["meta_block_text"] = meta_text
        except:
            details.setdefault("meta_block_text", None)

        # Description
        try:
            desc_candidates = driver.find_elements(By.XPATH, "//div[contains(@class,'description') or contains(@class,'synopsis') or //p[contains(@class,'DESCRIPTION')]]")
            description = None
            if desc_candidates:
                description = desc_candidates[0].text.strip()
            else:
                # generic fallback: look for a paragraph that is long
                ps = driver.find_elements(By.TAG_NAME, "p")
                for p in ps:
                    t = p.text.strip()
                    if t and len(t) > 50 and 'season' not in t.lower():
                        description = t
                        break
            details["description"] = description
        except:
            details["description"] = None

        # cast / creators / audio / subtitles - attempt some generic selectors
        details["starring"] = None
        details["creators"] = None
        details["audio"] = None
        details["subtitles"] = None

        # SEASONS: find season buttons and iterate
        seasons_data = {}
        # First gather season buttons
        time.sleep(1.0)
        # Attempt to find season buttons by button text/value like 'Season 1'
        season_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Season') or contains(., 'season') or @value[contains(., 'Season')]]")
        # Deduplicate by visible text
        seen = set()
        unique_buttons = []
        for b in season_buttons:
            try:
                text = b.text.strip()
                if not text:
                    text = b.get_attribute("value") or b.get_attribute("aria-label") or ""
                if text and text not in seen:
                    seen.add(text)
                    unique_buttons.append(b)
            except:
                continue

        # If no buttons found, try other approach: clickable elements labelled Season 1, Season 2 as spans
        if not unique_buttons:
            alt_btns = driver.find_elements(By.XPATH, "//*[contains(text(),'Season') or contains(text(),'season')]")
            for b in alt_btns:
                txt = b.text.strip()
                if txt and txt not in seen and 'season' in txt.lower():
                    seen.add(txt)
                    unique_buttons.append(b)

        # If still empty, try to find a dropdown of seasons
        if not unique_buttons:
            sel = driver.find_elements(By.TAG_NAME, "select")
            for s in sel:
                options = s.find_elements(By.TAG_NAME, "option")
                for opt in options:
                    txt = opt.text.strip()
                    if 'season' in txt.lower():
                        # will handle by selecting via JS later
                        unique_buttons.append(opt)

        # If still empty: try clicking 'Seasons' tab - but continue with what we have
        print(f"Found {len(unique_buttons)} season buttons (may include duplicates).")

        # If no seasons found assume a single season present
        if not unique_buttons:
            # try to parse episodes from the page as-is (one season)
            season_name = "Season 1"
            seasons_data[season_name] = []
            # We'll fall through to scrape episodes below without clicking seasons
            season_buttons = []
            unique_buttons = []

        # iterate each season button and collect episodes
        # We'll attempt clicking each button then scraping episode cards that appear
        if unique_buttons:
            for idx, btn in enumerate(unique_buttons, start=1):
                try:
                    # get readable season name
                    s_text = btn.text.strip() or btn.get_attribute("value") or f"Season {idx}"
                except:
                    s_text = f"Season {idx}"
                season_name = s_text
                print("Processing", season_name)
                # click the season button
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                    time.sleep(0.2)
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    try:
                        btn.click()
                    except:
                        pass
                time.sleep(1.0)

                # After clicking season, locate episode cards
                # Try a few common selectors for episode tiles/cards
                episodes = []
                # candidate containers
                possible_selectors = [
                    "//div[contains(@class,'episode') or contains(@data-testid,'episode') or contains(@class,'tile') or contains(@class,'content-card')]",
                    "//a[contains(@href,'/show/') or contains(@href,'/watch/') or contains(@class,'episode')]",
                    "//div[contains(@class,'List')]/div[contains(@class,'Card') or contains(@class,'_2VQf5SfKuLjiPBZydt_iR2')]",
                    "//li[contains(@class,'episode') or contains(@class,'grid-item')]"
                ]
                found_cards = []
                for sel in possible_selectors:
                    els = driver.find_elements(By.XPATH, sel)
                    if els and len(els) > 0:
                        found_cards = els
                        break

                # If still none, try a more general approach - find anchor tags with image + title inside
                if not found_cards:
                    anchors = driver.find_elements(By.XPATH, "//a[.//img and (.//h3 or .//p or .//span)]")
                    found_cards = anchors[:200]

                # Deduplicate DOM elements
                unique_cards = []
                seen_ids = set()
                for card in found_cards:
                    try:
                        uid = card.get_attribute("innerHTML")[:200]
                        if uid not in seen_ids:
                            seen_ids.add(uid)
                            unique_cards.append(card)
                    except:
                        unique_cards.append(card)

                for card in unique_cards:
                    try:
                        # title - try a few subselectors
                        title = None
                        title_el = None
                        for tsel in [".//h3", ".//h4", ".//h2", ".//p[contains(@class,'title')]", ".//span[contains(@class,'title')]", ".//p[contains(@class,'TITLE')]", ".//p[contains(@class,'title')]"]:
                            try:
                                title_el = card.find_element(By.XPATH, tsel)
                                if title_el and title_el.text.strip():
                                    title = title_el.text.strip()
                                    break
                            except:
                                title = None
                        # description
                        description = None
                        for dsel in [".//p[contains(@class,'desc')]", ".//p[contains(@class,'description')]", ".//div[contains(@class,'synopsis')]", ".//p"]:
                            try:
                                d_el = card.find_element(By.XPATH, dsel)
                                txt = d_el.text.strip()
                                if txt and len(txt) > 5:
                                    description = txt
                                    break
                            except:
                                continue
                        # duration (sometimes small text)
                        duration = None
                        try:
                            dur_el = card.find_element(By.XPATH, ".//*[contains(text(),'m') or contains(text(),'min') or contains(@class,'duration')]")
                            if dur_el:
                                dur_txt = dur_el.text.strip()
                                if len(dur_txt) < 20:
                                    duration = dur_txt
                        except:
                            duration = None

                        # image URL
                        image_url = None
                        try:
                            img = card.find_element(By.XPATH, ".//img")
                            if img:
                                image_url = img.get_attribute("src") or img.get_attribute("data-src")
                        except:
                            image_url = None

                        # Compose episode object
                        # Some cards may not be episodes (could be placeholders). Heuristics: must have title or image.
                        if title or image_url or description:
                            ep = {
                                "title": title or "",
                                "description": description or "",
                                "duration": duration or "",
                                "image_url": image_url or ""
                            }
                            episodes.append(ep)
                    except Exception as e:
                        # skip bad card
                        continue

                # Trim duplicates by title
                clean_eps = []
                seen_titles = set()
                for ep in episodes:
                    t = (ep.get("title") or "").strip()
                    if not t or t in seen_titles:
                        continue
                    seen_titles.add(t)
                    clean_eps.append(ep)

                seasons_data[season_name] = clean_eps
                # small wait before next season click
                time.sleep(0.8)

        else:
            # fallback parsing if no season buttons found: try to scrape episodes on page
            eps = []
            cards = driver.find_elements(By.XPATH, "//a[.//img and (.//h3 or .//p or .//span)]")
            for card in cards:
                try:
                    title = ""
                    try:
                        title = card.find_element(By.XPATH, ".//h3").text.strip()
                    except:
                        try:
                            title = card.find_element(By.XPATH, ".//p").text.strip()
                        except:
                            title = ""
                    description = ""
                    try:
                        description = card.find_element(By.XPATH, ".//p").text.strip()
                    except:
                        description = ""
                    image_url = ""
                    try:
                        image_url = card.find_element(By.XPATH, ".//img").get_attribute("src")
                    except:
                        image_url = ""
                    eps.append({"title": title, "description": description, "duration": "", "image_url": image_url})
                except:
                    continue
            seasons_data["Season 1"] = eps

        # Compose final JSON similar to sample structure
        final = {
            "show_title": details.get("show_title"),
            "year": None,
            "seasons": None,
            "rating": None,
            "genre": None,
            "description": details.get("description"),
            "starring": details.get("starring"),
            "creators": details.get("creators"),
            "genres": details.get("genres_or_tags"),
            "show_characteristics": details.get("meta_block_text"),
            "audio": details.get("audio"),
            "subtitles": details.get("subtitles"),
            "cast": details.get("starring"),
            "Poster": details.get("Poster"),
            "Logo": None,
            "seasons_data": []
        }

        # try to parse year/rating/seasons from meta_block_text heuristically
        meta = details.get("meta_block_text") or ""
        if meta:
            # naive splits
            parts = [p.strip() for p in meta.split() if p.strip()]
            # attempt year as 4-digit number
            import re
            m = re.search(r"20\d{2}|19\d{2}", meta)
            if m:
                final["year"] = m.group(0)
            # seasons
            s_m = re.search(r"(\d+)\s*Seasons?|Season\s*(\d+)", meta, re.I)
            if s_m:
                final["seasons"] = s_m.group(0)
            # rating like A / U / 16+
            r_m = re.search(r"\b([A-Z0-9\+\-]{1,6})\b", meta)
            if r_m:
                final["rating"] = r_m.group(0)

        # convert seasons_data dict into the JSON array style in sample
        seasons_array = []
        for sname, episodes in seasons_data.items():
            seasons_array.append({sname: [
                {
                    "title": e.get("title") or "",
                    "description": e.get("description") or "",
                    "duration": e.get("duration") or "",
                    "image_url": e.get("image_url") or ""
                } for e in episodes
            ]})
        final["seasons_data"] = seasons_array

        # Save JSON
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final, f, ensure_ascii=False, indent=2)

        print("Saved output to", OUTPUT_FILE)
    except Exception as e:
        print("Error:", e)
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    main()
