from flask import Flask, request, jsonify
from data import scrape_hotstar

app = Flask(__name__)

@app.route('/scrape', methods=['GET'])
def scrape():
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400
    
    try:
        data = scrape_hotstar(query)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
