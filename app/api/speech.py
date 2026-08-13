import base64
import tempfile
import whisper
import subprocess
import os

from flask import Blueprint, request, jsonify

speech_api = Blueprint("speech_api", __name__)

model = whisper.load_model("base")

# YOUR FFMPEG PATH
FFMPEG_PATH = r"C:\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"


@speech_api.route("/api/speech_to_text", methods=["POST"])
def speech_to_text():

    try:

        data = request.json
        audio_base64 = data.get("audio")

        if not audio_base64:
            return jsonify({
                "ok": False,
                "error": "No audio"
            }), 400

        print("✅ Audio received")

        # remove base64 prefix
        audio_base64 = audio_base64.split(",")[1]

        audio_bytes = base64.b64decode(audio_base64)

        # save webm
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as f:

            f.write(audio_bytes)

            webm_path = f.name

        print("✅ Webm saved:", webm_path)

        # wav path
        wav_path = webm_path.replace(".webm", ".wav")

        # ffmpeg convert
        result = subprocess.run([
            FFMPEG_PATH,
            "-y",
            "-i",
            webm_path,
            wav_path
        ])

        print("FFMPEG RETURN CODE:", result.returncode)

        # verify wav exists
        if not os.path.exists(wav_path):

            return jsonify({
                "ok": False,
                "error": "WAV not created"
            }), 500

        print("✅ WAV created")

        # transcribe
        result = model.transcribe(wav_path)

        text = result["text"].strip()

        print("✅ TRANSCRIBED:", text)

        return jsonify({
            "ok": True,
            "text": text
        })

    except Exception as e:

        print("❌ Whisper error:", e)

        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500