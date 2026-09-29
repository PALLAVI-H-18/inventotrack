from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # lets the React frontend call this API later

@app.route("/")
def home():
    return jsonify({"message": "InventoTrack backend is running"})

@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)