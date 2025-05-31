from flask import Flask, request, jsonify
from dataclasses import dataclass
import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)
import requests
from transformers import pipeline

app = Flask(__name__)

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
    except TranscriptsDisabled as e:
        return "Transcripts are disabled for this video"
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
    subtitles = "\n".join(
        [f"{sbt['start']}: {sbt['text']}" for sbt in subtitles if sbt["text"] != "[Music]"]
    )
    return subtitles

def download_thumbnail(video_id):
    img_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
    img_data = requests.get(img_url).content
    with open('thumbnail.jpg', 'wb') as handler:
        handler.write(img_data)

# Load the summarizer once
summarizer = pipeline("summarization")

def summarize_text_chunks(text):
    num_iters = int(len(text) / 1000)
    summarized_text = []
    for i in range(0, num_iters + 1):
        chunk = text[i * 1000: (i + 1) * 1000]
        if not chunk.strip():
            continue
        out = summarizer(chunk, min_length=5, max_length=20)
        summarized_text.append(out[0]['summary_text'])
    return summarized_text

@app.route('/summarize', methods=['POST'])
def summarize_video():
    data = request.get_json()
    video_url = data.get("url")
    if not video_url:
        return jsonify({"error": "No URL provided"}), 400

    try:
        info = extract_video_information(video_url)
        transcript = get_transcripts(info.id)
        download_thumbnail(info.id)
        if "No English transcript" in transcript or "disabled" in transcript:
            return jsonify({"error": transcript}), 400
        summary = summarize_text_chunks(transcript)
        return jsonify({
            "title": info.title,
            "channel": info.channel,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
