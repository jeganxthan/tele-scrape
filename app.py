import asyncio
import os
import re
import json
import sys
from telethon import TelegramClient, errors
from dotenv import load_dotenv
from subtitle_generator import SubtitleGenerator

load_dotenv()

# ============== CONFIGURATION ==============
API_ID = int(os.getenv("API_ID", 34616802))
API_HASH = os.getenv("API_HASH", "b19339ceab122576f62b3886e267f35d")
SESSION_NAME = "series_session"
TARGET_CHAT = "hosico_catsbot"
DOWNLOAD_DIR = "downloads/"
SCAN_LIMIT = None
MAX_CONCURRENT_DOWNLOADS = 3

# Subtitle Generation Configuration
ENABLE_SUBTITLES = True  # Set to False to disable subtitle generation
WHISPER_MODEL = "base"   # Options: tiny, base, small, medium, large
SUBTITLE_LANGUAGE = "en" # None for auto-detect, or specify like "en", "es", "ja"
# ===========================================

def extract_episode_info(text):
    info = {}
    if not text:
        return info

    # Match the markdown fields as in your example
    patterns = {
        "series": r"\*\*○ Series:\*\* `([^`]+)`",
        "language": r"\*\*○ Language:\*\* `([^`]+)`|○ Language:\s*([^\n`]+)",
        "resolution": r"\*\*○ Resolution:\*\* `([^`]+)`",
        "codec": r"\*\*○ Codec:\*\* `([^`]+)`",
        "episode_title": r"\*\*○ Episode Title:\*\* `([^`]+)`",
        "episode_number_raw": r"\*\*○ Episode Number:\*\* `([^`]+)`",
        "released_on": r"\*\*○ Released on:\*\* `([^`]+)`",
        "rating": r"\*\*○ Episode Rating:\*\* `([^`]+)`",
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # group(1) may be None for the Language second alternative; pick the first non-None
            captured = next((g for g in match.groups() if g), None)
            if captured:
                info[key] = captured.strip()

    # parse episode_number_raw like "1/9" -> episode_number, total_episodes_in_season
    if "episode_number_raw" in info:
        ep_raw = info["episode_number_raw"]
        m = re.match(r'(\d+)\s*/\s*(\d+)', ep_raw)
        if m:
            info["episode_number"] = m.group(1)
            info["total_episodes_in_season"] = m.group(2)
        else:
            # fallback: take digits
            digits = re.search(r'(\d+)', ep_raw)
            if digits:
                info["episode_number"] = digits.group(1)
        del info["episode_number_raw"]

    if info.get("series"):
        info["series"] = info["series"].replace('`', '').strip()

    return info

def parse_filename_for_info(filename):
    """
    Robust filename parsing:
    Accepts separators ., _, or spaces.
    Example matches:
      Stranger.Things.S04E01.1080p...mkv
      Stranger_Things_S04E01_...mkv
      Stranger Things S04E01 ...mkv
    Returns dict with 'series', 'season_number', 'episode_number' when possible.
    """
    file_info = {}

    # Normalize filename for matching but keep original for series extraction
    # Regex:
    #  - series name: everything up to separator + SXXEYY
    #  - allow separators '.', '_', or space between tokens
    pattern = re.compile(r'(.+?)[._\s]S(\d{1,2})E(\d{1,3})(?:[._\s].*)?\.[^.]+$',
                         re.IGNORECASE)
    match = pattern.match(filename)
    if match:
        raw_series = match.group(1)
        # replace separators with spaces, then strip and normalize spacing
        series_clean = re.sub(r'[._\s]+', ' ', raw_series).strip()
        file_info["series"] = series_clean
        file_info["season_number"] = match.group(2).zfill(2)  # keep as zero-padded string
        file_info["episode_number"] = match.group(3).zfill(2)
        return file_info

    # Try alternate simpler pattern: e.g., "Stranger.Things.S04.E01..."
    alt = re.compile(r'(.+?)[._\s]S?(\d{1,2})[._\s]E?(\d{1,3}).*\.[^.]+$', re.IGNORECASE)
    m2 = alt.match(filename)
    if m2:
        raw_series = m2.group(1)
        series_clean = re.sub(r'[._\s]+', ' ', raw_series).strip()
        file_info["series"] = series_clean
        file_info["season_number"] = m2.group(2).zfill(2)
        file_info["episode_number"] = m2.group(3).zfill(2)
    # Try alternate simpler pattern: e.g., "Stranger.Things.S04.E01..."
    alt = re.compile(r'(.+?)[._\s]S?(\d{1,2})[._\s]E?(\d{1,3}).*\.[^.]+$', re.IGNORECASE)
    m2 = alt.match(filename)
    if m2:
        raw_series = m2.group(1)
        series_clean = re.sub(r'[._\s]+', ' ', raw_series).strip()
        file_info["series"] = series_clean
        file_info["season_number"] = m2.group(2).zfill(2)
        file_info["episode_number"] = m2.group(3).zfill(2)
    return file_info

async def process_message(client, msg, semaphore, series_data, downloaded_episodes_tracker, counter_lock, counter_container):
    if not msg.media or not hasattr(msg.media, 'document') or not msg.media.document:
        return

    # print(f"\n--- Processing message {msg.id} ---") # Reduced logging

    # get filename if provided by the document attributes
    file_name_from_media = None
    for attr in getattr(msg.media.document, 'attributes', []):
        if hasattr(attr, 'file_name') and attr.file_name:
            file_name_from_media = attr.file_name
            break

    file_info_from_filename = {}
    if file_name_from_media:
        file_info_from_filename = parse_filename_for_info(file_name_from_media)
        # print(f"Extracted Info from Filename: {file_info_from_filename}")

    info = extract_episode_info(msg.text or "")
    # print(f"Extracted Info from Message Text: {info}")

    # Prioritize filename parsing for series/season/episode when present
    if file_info_from_filename.get("series"):
        info["series"] = file_info_from_filename["series"]
    if file_info_from_filename.get("season_number"):
        # keep as zero-padded string
        info["season_number"] = file_info_from_filename["season_number"]
    if file_info_from_filename.get("episode_number"):
        info["episode_number"] = file_info_from_filename["episode_number"].lstrip("0") or "0"

    # If info lacks episode or series, skip
    if not info.get("series") or not info.get("episode_number"):
        # print(f"⚠️ Skipping message {msg.id} (missing series or episode info).")
        return

    series_name = info["series"].strip()
    # episode_number may be zero-padded, convert to int
    try:
        episode_num = int(re.sub(r'\D', '', info["episode_number"]))
    except Exception:
        # print(f"⚠️ Skipping message {msg.id} (invalid episode number: {info.get('episode_number')}).")
        return

    # Determine season number:
    if info.get("season_number"):
        # season_number could be '04' or '4' — normalize to int then back to zero-padded string
        current_season = int(re.sub(r'\D', '', str(info["season_number"])))
    else:
        # fallback: default to 1 if no season info anywhere
        current_season = 1

    season_num_str = str(current_season).zfill(2)
    info["season_number"] = season_num_str

    # init trackers
    if series_name not in downloaded_episodes_tracker:
        downloaded_episodes_tracker[series_name] = {}
    if season_num_str not in downloaded_episodes_tracker[series_name]:
        downloaded_episodes_tracker[series_name][season_num_str] = {"episodes": set(), "total_expected": None}

    if info.get("total_episodes_in_season"):
        try:
            downloaded_episodes_tracker[series_name][season_num_str]["total_expected"] = int(info["total_episodes_in_season"])
        except Exception:
            pass

    # Build filesystem names
    # safe series folder name: remove punctuation, replace spaces with underscore
    series_clean = re.sub(r'[^\w\s-]', '', series_name).strip().replace(' ', '_')
    season_folder_name = f"Season {int(season_num_str):02d}"
    file_name_prefix = f"{series_clean}_S{int(season_num_str):02d}E{int(episode_num):02d}"

    local_series_folder = os.path.join(DOWNLOAD_DIR, series_clean)
    local_season_folder = os.path.join(local_series_folder, season_folder_name)
    os.makedirs(local_season_folder, exist_ok=True)

    # determine extension from document attributes if present
    file_ext = ".mkv"
    if msg.media and getattr(msg.media, 'document', None):
        for attr in getattr(msg.media.document, 'attributes', []):
            if hasattr(attr, 'file_name') and attr.file_name:
                _, detected_ext = os.path.splitext(attr.file_name)
                if detected_ext:
                    file_ext = detected_ext
                break

    full_file_name = f"{file_name_prefix}{file_ext}"
    local_file_path = os.path.join(local_season_folder, full_file_name)

    if os.path.exists(local_file_path):
        print(f"⏩ Skipping '{full_file_name}': Exists.")
        downloaded_episodes_tracker[series_name][season_num_str]["episodes"].add(episode_num)
        return

    # Only attempt to download if the document mime looks like a video/matroska or generic video
    try:
        mime = getattr(msg.media.document, 'mime_type', '') or ''
        if 'matroska' in mime.lower() or mime.lower().startswith('video/'):
            async with semaphore:
                print(f"⬇️  Downloading '{full_file_name}'...")
                
                # Progress callback closure
                last_reported = [-1]
                def progress_callback(current, total):
                    if not total: return
                    percentage = int((current / total) * 100)
                    # Report every 10%
                    if percentage // 10 > last_reported[0] // 10:
                        print(f"   ⏳ {full_file_name}: {percentage}%")
                        last_reported[0] = percentage
                    elif percentage == 100 and last_reported[0] != 100:
                        print(f"   ⏳ {full_file_name}: 100%")
                        last_reported[0] = 100

                file_path = await client.download_media(
                    msg,
                    file=local_file_path,
                    progress_callback=progress_callback
                )
                if file_path:
                    print(f"✅ Finished '{full_file_name}'")
                    
                    # Generate subtitles if enabled
                    subtitle_path = None
                    if ENABLE_SUBTITLES:
                        try:
                            print(f"📝 Generating subtitles for '{full_file_name}'...")
                            generator = SubtitleGenerator(
                                model_name=WHISPER_MODEL,
                                language=SUBTITLE_LANGUAGE
                            )
                            success, subtitle_path, error = await asyncio.to_thread(generator.generate_subtitles, file_path)
                            if success:
                                print(f"✅ Subtitles generated: {os.path.basename(subtitle_path)}")
                                info["subtitle_file"] = os.path.basename(subtitle_path)
                            else:
                                print(f"⚠️ Subtitle generation failed: {error}")
                        except Exception as e:
                            print(f"⚠️ Subtitle generation error: {e}")
                    
                    try:
                        await msg.delete()
                        print(f"🗑️ Deleted message {msg.id}")
                    except Exception as e:
                        print(f"⚠️ Failed to delete message {msg.id}: {e}")
                    info["file"] = os.path.basename(file_path)

                    # update series_data structure
                    # Note: Dictionary operations are thread-safe in Python (GIL), and we are in a single-threaded async loop
                    # so this is safe without locks unless we await inside the critical section.
                    if series_name not in series_data["series"]:
                        series_data["series"][series_name] = {"seasons": {}}
                    if season_num_str not in series_data["series"][series_name]["seasons"]:
                        series_data["series"][series_name]["seasons"][season_num_str] = {"episodes": [], "total_episodes": None}

                    if info.get("total_episodes_in_season"):
                        try:
                            series_data["series"][series_name]["seasons"][season_num_str]["total_episodes"] = int(info["total_episodes_in_season"])
                        except Exception:
                            pass

                    series_data["series"][series_name]["seasons"][season_num_str]["episodes"].append(info)

                    # tracker add
                    downloaded_episodes_tracker[series_name][season_num_str]["episodes"].add(episode_num)
                    if info.get("total_episodes_in_season"):
                        try:
                            downloaded_episodes_tracker[series_name][season_num_str]["total_expected"] = int(info["total_episodes_in_season"])
                        except Exception:
                            pass

                    async with counter_lock:
                        counter_container[0] += 1
                else:
                    print(f"⚠️ Failed '{full_file_name}'")
        else:
            # print(f"   ⚠️ Skipping message {msg.id}: Not a video (mime='{mime}').")
            pass
    except errors.RPCError as rpc:
        print(f"   ⚠️ RPC error for {full_file_name}:", rpc)
    except Exception as ex:
        print(f"   ⚠️ Failed to download {full_file_name}:", ex)

async def main():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    print("🚀 Starting Telegram client...")
    await client.start()
    me = await client.get_me()
    print("✅ Logged in as:", getattr(me, 'username', me.first_name if me else 'Unknown'))

    try:
        target = await client.get_entity(TARGET_CHAT)
    except Exception as e:
        print(f"❌ Could not resolve '{TARGET_CHAT}': {e}")
        await client.disconnect()
        return

    print("📥 Scanning chat:", getattr(target, "title", TARGET_CHAT))
    series_data = {"series": {}}
    downloaded_episodes_tracker = {}  # {series: {season_str: {"episodes": set(int), "total_expected": int|None}}}
    
    # Shared mutable container for count
    counter_container = [0]
    counter_lock = asyncio.Lock()

    all_messages = []
    async for msg in client.iter_messages(target, limit=SCAN_LIMIT):
        all_messages.append(msg)
    all_messages.sort(key=lambda m: m.id)

    print(f"Found {len(all_messages)} messages. Processing...")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
    tasks = []

    for msg in all_messages:
        task = asyncio.create_task(
            process_message(
                client, 
                msg, 
                semaphore, 
                series_data, 
                downloaded_episodes_tracker, 
                counter_lock, 
                counter_container
            )
        )
        tasks.append(task)

    if tasks:
        await asyncio.gather(*tasks)

    # Save metadata JSON per series
    print("\n--- Season Completion Summary ---")
    if series_data["series"]:
        for sname, sinfo in series_data["series"].items():
            s_clean = re.sub(r'[^\w\s-]', '', sname).strip().replace(' ', '_')
            json_path = os.path.join(DOWNLOAD_DIR, f"{s_clean}.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(sinfo, f, indent=4, ensure_ascii=False)
            print(f"\n🧾 Metadata for '{sname}' saved to: {json_path}")

            for season_num, season_details in sinfo["seasons"].items():
                total_expected = season_details.get("total_episodes")
                downloaded_count = len(season_details["episodes"])
                if total_expected is not None and downloaded_count == total_expected:
                    print(f"✅ Series '{sname}', Season {season_num} is complete ({downloaded_count}/{total_expected}).")
                elif total_expected is not None:
                    print(f"⏳ Series '{sname}', Season {season_num} is {downloaded_count}/{total_expected} complete.")
                else:
                    print(f"ℹ️ Series '{sname}', Season {season_num} has {downloaded_count} episodes downloaded (total unknown).")
    else:
        print("No series data to process.")

    print(f"\n🎉 Completed. Total episodes downloaded: {counter_container[0]}")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
