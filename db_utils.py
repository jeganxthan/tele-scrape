import os
import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# MONGO_URI = os.getenv("MONGO_URI") # Removed global assignment
DB_NAME = "series_db"
COLLECTION_NAME = "series_data"
MOVIE_COLLECTION_NAME = "movie_data"

def get_db_connection():
    """Establishes a connection to the MongoDB database and refreshes environment variables."""
    try:
        load_dotenv(override=True) # Force reload
        mongo_uri = os.getenv("MONGO_URI")
        
        if not mongo_uri:
            print("❌ MONGO_URI not found in environment variables.")
            return None
            
        client = MongoClient(mongo_uri)
        # Test connection
        client.admin.command('ping')
        return client
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_db():
    """Initializes the database (creates indexes)."""
    client = get_db_connection()
    if not client:
        return

    try:
        db = client[DB_NAME]
        
        # Series collection index
        collection = db[COLLECTION_NAME]
        collection.create_index("show_title", unique=True)
        
        # Movie collection index
        movie_collection = db[MOVIE_COLLECTION_NAME]
        movie_collection.create_index("title", unique=True)
        
        print("✅ Database initialized (MongoDB indexes created).")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

def save_show_data(data):
    """Saves the entire scraped show data as a JSON document."""
    # Filter out placeholders before saving
    data = remove_non_filemoon_episode_urls(data)
    
    client = get_db_connection()
    if not client:
        return False

    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        show_title = data.get("show_title")
        if not show_title:
            print("❌ Cannot save data: 'show_title' is missing from data dictionary.")
            print(f"Data keys: {list(data.keys())}")
            return False

        # Check season data count
        seasons_data = data.get("seasons_data", [])
        total_episodes = sum(len(list(s.values())[0]) for s in seasons_data if s and list(s.values()))
        
        print(f"Attempting to save show: '{show_title}'")
        print(f"📊 Stats: {len(seasons_data)} seasons, {total_episodes} valid episodes.")

        # Add/Update timestamp and category
        data["created_at"] = datetime.datetime.utcnow()
        if "category" not in data:
            data["category"] = "series"

        # Insert or Update (Upsert)
        collection.replace_one(
            {"show_title": show_title},
            data,
            upsert=True
        )

        print(f"✅ Full JSON data for '{show_title}' saved to MongoDB.")
        return True

    except Exception as e:
        print(f"❌ Failed to save data: {e}")
        return False

def save_movie_data(data):
    """Saves the scraped movie data as a JSON document in movie_data collection."""
    client = get_db_connection()
    if not client:
        return False

    try:
        db = client[DB_NAME]
        collection = db[MOVIE_COLLECTION_NAME]
        
        title = data.get("title")
        if not title:
            print("❌ Cannot save data: 'title' is missing from data dictionary.")
            print(f"Data keys: {list(data.keys())}")
            return False

        print(f"Attempting to save movie: '{title}'")

        # Add/Update timestamp
        data["created_at"] = datetime.datetime.utcnow()
        if "category" not in data:
            data["category"] = "movie"

        # Insert or Update (Upsert)
        collection.replace_one(
            {"title": title},
            data,
            upsert=True
        )

        print(f"✅ Full JSON data for movie '{title}' saved to MongoDB's {MOVIE_COLLECTION_NAME}.")
        return True

    except Exception as e:
        print(f"❌ Failed to save movie data: {e}")
        return False

def get_all_shows():
    """Retrieves a list of all stored shows."""
    client = get_db_connection()
    if not client:
        return []

    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Project only needed fields
        cursor = collection.find({}, {"show_title": 1, "created_at": 1, "_id": 1}).sort("show_title", 1)
        
        shows = []
        for doc in cursor:
            shows.append({
                "id": str(doc["_id"]),
                "title": doc.get("show_title"),
                "created_at": doc.get("created_at")
            })
        
        return shows
    except Exception as e:
        print(f"❌ Failed to fetch shows: {e}")
        return []

def get_show_data(title):
    """Retrieves the full JSON data for a specific show."""
    client = get_db_connection()
    if not client:
        return None

    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        
        # Find by show_title
        doc = collection.find_one({"show_title": title}, {"_id": 0})
        return doc
    except Exception as e:
        print(f"❌ Failed to fetch show data: {e}")
        return None

# ---------------- Helper: Strict FileMoon URL filter ----------------
import re
# Keep only URLs that match: https?://(www.)?filemoon.in/e/<id> (optionally trailing slash or query)
FILEMOON_EPISODE_REGEX = re.compile(
    r"^https?://(?:www\.)?filemoon\.in/e/[A-Za-z0-9_-]+(?:/)?(?:\?.*)?$",
    re.IGNORECASE
)

def is_valid_filemoon_episode_url(url: str) -> bool:
    """Return True only if the URL matches a real FileMoon episode pattern."""
    if not url:
        return False
    url = url.strip()
    # Quick reject placeholder
    if "placeholder" in url.lower():
        return False
    # Match strict FileMoon /e/ pattern
    if FILEMOON_EPISODE_REGEX.match(url):
        return True
    return False

def remove_non_filemoon_episode_urls(data: dict) -> dict:
    """
    Walk data['seasons_data'] and keep only episodes whose 'url' matches is_valid_filemoon_episode_url().
    Returns cleaned data.
    """
    if not data:
        return data

    seasons = data.get("seasons_data", [])
    cleaned_seasons = []

    for season_entry in seasons:
        if not isinstance(season_entry, dict):
            continue
        new_season_entry = {}
        for season_key, episodes in season_entry.items():
            if not isinstance(episodes, list):
                continue
            cleaned_eps = []
            for ep in episodes:
                ep_url = (ep.get("url") or "").strip()
                if not is_valid_filemoon_episode_url(ep_url):
                    print(f"Skipping DB save for placeholder/invalid episode: {ep.get('filename')}")
                    continue
                cleaned_eps.append(ep)
            if cleaned_eps:
                new_season_entry[season_key] = cleaned_eps
        if new_season_entry:
            cleaned_seasons.append(new_season_entry)

    data["seasons_data"] = cleaned_seasons
    
    # DEBUG LOGGING
    total_input_eps = sum(len(list(s.values())[0]) for s in seasons if isinstance(s, dict) and list(s.values()))
    total_output_eps = sum(len(list(s.values())[0]) for s in cleaned_seasons if isinstance(s, dict) and list(s.values()))
    
    print(f"DEBUG: remove_non_filemoon_episode_urls: Input={total_input_eps} eps, Output={total_output_eps} eps.")
    if total_input_eps > 0 and total_output_eps == 0:
        print("⚠️ WARNING: All episodes were filtered out as placeholders/invalid!")
    
    return data



def update_episode_data(show_title, season_num, episode_num, updates):
    """
    Updates specific fields for an episode in the database.
    season_num: int or string (will be matched against stored format)
    episode_num: int or string
    updates: dict of fields to update (e.g. {"subtitle_file": "..."})
    """
    client = get_db_connection()
    if not client:
        return False

    try:
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]

        # We need to find the correct season key (e.g. "Season 01" or "1")
        # The schema seems to be: seasons_data: [{"Season 01": [...]}, ...]
        # This structure is a bit awkward to query directly with array filters if keys are dynamic.
        # Let's fetch the doc, update in python, and save back. 
        # (For high concurrency this is bad, but for this single-user bot it's fine).
        
        doc = collection.find_one({"show_title": show_title})
        if not doc:
            print(f"❌ Show '{show_title}' not found for update.")
            return False

        seasons_data = doc.get("seasons_data", [])
        modified = False

        # Normalize inputs
        target_season_int = int(season_num)
        target_episode_int = int(episode_num)

        for season_entry in seasons_data:
            # season_entry is like {"Season 01": [episodes...]}
            for s_key, episodes in season_entry.items():
                # Extract number from s_key "Season 01" -> 1
                try:
                    s_key_num = int(re.search(r'(\d+)', s_key).group(1))
                except:
                    continue
                
                if s_key_num == target_season_int:
                    # Found season, look for episode
                    for ep in episodes:
                        # ep has "episode_number": "01" or 1
                        try:
                            ep_num = int(ep.get("episode_number", -1))
                        except:
                            continue
                        
                        if ep_num == target_episode_int:
                            # Found episode, apply updates
                            for k, v in updates.items():
                                ep[k] = v
                            modified = True
        
        if modified:
            collection.replace_one({"_id": doc["_id"]}, doc)
            print(f"✅ Updated episode S{target_season_int:02d}E{target_episode_int:02d} for '{show_title}'.")
            return True
        else:
            print(f"⚠️ Episode S{target_season_int:02d}E{target_episode_int:02d} not found in '{show_title}'.")
            return False

    except Exception as e:
        print(f"❌ Failed to update episode data: {e}")
        return False

# ---------------- Popular Titles Management ----------------
POPULAR_COLLECTION_NAME = "popular_titles"

from bson.objectid import ObjectId

def get_popular_titles():
    """Retrieves all popular titles sorted by order."""
    client = get_db_connection()
    if not client: return []
    
    try:
        db = client[DB_NAME]
        collection = db[POPULAR_COLLECTION_NAME]
        # Return list with _id as string, sorted by order
        docs = list(collection.find({}).sort("order", 1))
        for d in docs:
            d['id'] = str(d['_id'])
            del d['_id']
        return docs
    except Exception as e:
        print(f"❌ Failed to get popular titles: {e}")
        return []

def add_popular_title(title, category="movie"):
    """Adds a title to popular collection with auto-incremented order."""
    client = get_db_connection()
    if not client: return None
    
    try:
        db = client[DB_NAME]
        collection = db[POPULAR_COLLECTION_NAME]
        
        # Check duplicate
        if collection.find_one({"title": title}):
            return False # Already exists
        
        # Get max order and increment
        max_doc = collection.find_one(sort=[("order", -1)])
        next_order = (max_doc.get("order", -1) + 1) if max_doc else 0
            
        res = collection.insert_one({
            "title": title,
            "category": category,
            "order": next_order,
            "added_at": datetime.datetime.utcnow()
        })
        return str(res.inserted_id)
    except Exception as e:
        print(f"❌ Failed to add popular title: {e}")
        return None

def remove_popular_title(doc_id):
    """Removes a title by ID."""
    client = get_db_connection()
    if not client: return False
    
    try:
        db = client[DB_NAME]
        collection = db[POPULAR_COLLECTION_NAME]
        
        res = collection.delete_one({"_id": ObjectId(doc_id)})
        return res.deleted_count > 0
    except Exception as e:
        print(f"❌ Failed to remove popular title: {e}")
        return False

def reorder_popular_titles(ordered_ids):
    """Reorders popular titles based on provided ID array."""
    client = get_db_connection()
    if not client: return False
    
    try:
        db = client[DB_NAME]
        collection = db[POPULAR_COLLECTION_NAME]
        
        # Update each document with its new order
        for index, doc_id in enumerate(ordered_ids):
            collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {"order": index}}
            )
        
        print(f"✅ Reordered {len(ordered_ids)} popular titles")
        return True
    except Exception as e:
        print(f"❌ Failed to reorder popular titles: {e}")
        return False

