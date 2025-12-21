from flask import Flask, request, jsonify
from imdb_scraper import scrape_imdb
from filemoon_converter import fill_filemoon_urls

app = Flask(__name__)

@app.route('/')
def index():
    return """
    <h1>IMDb Scraper API</h1>
    <p>Use <code>/scrape_imdb?query=SHOW_NAME</code> to scrape IMDb data.</p>
    <p>Example: <a href="/scrape_imdb?query=The Witcher">/scrape_imdb?query=The Witcher</a></p>
    """

@app.route('/scrape_imdb', methods=['GET'])
def scrape_imdb_endpoint():
    query = request.args.get('query')
    
    if not query:
        return jsonify({"error": "Query parameter is required. Use ?query=SHOW_NAME"}), 400
    
    try:
        print(f"Scraping IMDb for: {query}")
        
        # Scrape IMDb
        data = scrape_imdb(query)
        
        # Fill FileMoon URLs
        print("Filling FileMoon URLs...")
        data = fill_filemoon_urls(data)
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Use port 5002 to avoid conflict with existing scraper_api.py on 5001
    app.run(host='0.0.0.0', port=5002, debug=False)
