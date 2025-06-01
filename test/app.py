# main.py
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route("/summarize", methods=["POST"])
def summarize_video():
    data = request.get_json()
    video_url = data.get("url")
    # Run yt-dlp + transcript + summary here
    return jsonify({
        "title": "Sample title",
        "channel": "Channel name",
        "video_id": "abc123",
        "summary": "This is a short summary.",
        "transcript": "Full transcript here."
    })

app.run(host="0.0.0.0", port=5000, debug=True)
