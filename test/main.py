from flask import Flask, request, jsonify, send_file
from dataclasses import dataclass
import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
from transformers import pipeline
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

from flask_cors import CORS
app = Flask(__name__)
CORS(app)

@dataclass(frozen=True)
class VideoInfo:
    id: str
    title: str
    url: str
    duration: int
    channel: str
    channel_url: str

def extract_video_information(url: str) -> VideoInfo:
    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=False)
        return VideoInfo(
            id=info_dict.get("id"),
            title=info_dict.get("title"),
            url=info_dict.get("webpage_url"),
            duration=info_dict.get("duration"),
            channel=info_dict.get("channel"),
            channel_url=info_dict.get("channel_url"),
        )

def get_transcripts(video_id: str) -> str:
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except TranscriptsDisabled:
        return "Transcripts are disabled for this video."

    try:
        transcript = transcript_list.find_manually_created_transcript(["en"])
    except NoTranscriptFound:
        try:
            transcript = transcript_list.find_generated_transcript(["en"])
        except NoTranscriptFound:
            return "No English transcript available for this video."

    subtitles = transcript.fetch()
    if not subtitles:
        return "Failed to fetch transcript data or transcript data is empty."

    # Combine into paragraphs every ~4 lines
    lines = [sbt.text for sbt in subtitles if sbt.text != "[Music]"]
    paragraphs = [" ".join(lines[i:i+4]) for i in range(0, len(lines), 4)]
    
    return "\n\n".join(paragraphs)

def summarize_text_chunks(text):
    summarized_text = []
    num_iters = int(len(text) / 1000)
    print(f"Summarizing in {num_iters + 1} chunks...")

    for i in range(0, num_iters + 1):
        chunk = text[i * 1000: (i + 1) * 1000]
        if not chunk.strip():
            continue

        input_length = len(chunk.split())
        max_len = min(100, max(20, int(input_length * 0.6)))
        min_len = min(30, max(5, int(input_length * 0.3)))

        print(f"Chunk {i+1}/{num_iters+1}: summarizing {input_length} words...")
        out = summarizer(chunk, min_length=min_len, max_length=max_len)
        summarized_text.append(out[0]['summary_text'])

    print("Summarization complete.")
    return " ".join(summarized_text)

@app.route("/")
def home():
    return send_file("home.html")

@app.route('/summarize', methods=['POST'])
def summarize_video():
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON received"}), 400

        video_url = data.get("url")
        if not video_url:
            return jsonify({"error": "No URL provided"}), 400

        info = extract_video_information(video_url)
        transcript = get_transcripts(info.id)
        summary = summarize_text_chunks(transcript)

        return jsonify({
            "video_id": info.id,
            "title": info.title,
            "channel": info.channel,
            "transcript": transcript,
            "summary": summary
        })

    except Exception as e:
        print("ERROR:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

