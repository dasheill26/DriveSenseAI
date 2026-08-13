from flask import Blueprint, request, jsonify
import base64
import requests

image_api = Blueprint("image_api", __name__)

OLLAMA_URL = "http://localhost:11434/api/generate"

# =========================================================
# IMAGE ANALYSIS
# =========================================================

@image_api.route("/api/analyze_image", methods=["POST"])
def analyze_image():

    try:

        data = request.get_json()

        # -----------------------------------------
        # VALIDATION
        # -----------------------------------------

        if not data:

            return jsonify({
                "ok": False,
                "error": "No request data received"
            })

        image = data.get("image")

        if not image:

            return jsonify({
                "ok": False,
                "error": "No image received"
            })

        if "," not in image:

            return jsonify({
                "ok": False,
                "error": "Invalid image format"
            })

        # -----------------------------------------
        # CLEAN BASE64
        # -----------------------------------------

        image_base64 = image.split(",")[1]

        # validate image
        try:

            base64.b64decode(image_base64)

        except Exception:

            return jsonify({
                "ok": False,
                "error": "Invalid base64 image"
            })

        # -----------------------------------------
        # AI PROMPT
        # -----------------------------------------

        prompt = """
You are DriveSense AI.

You are a professional automotive master technician.

Analyze this vehicle image carefully.

Describe EXACTLY what you can visually see.

Check for:

- dashboard warning lights
- engine faults
- fluid leaks
- tyre wear
- brake wear
- visible damage
- smoke
- rust
- disconnected parts
- worn components
- loose wires
- overheating signs

If the image is unclear,
say that clearly.

DO NOT guess things that are not visible.

Keep the response:
- accurate
- professional
- simple to understand
- structured nicely
"""

        # -----------------------------------------
        # CALL OLLAMA
        # -----------------------------------------

        response = requests.post(

            OLLAMA_URL,

            json={

                "model": "llava",

                "prompt": prompt,

                "images": [image_base64],

                "stream": False

            },

            timeout=180

        )

        # -----------------------------------------
        # RESPONSE CHECK
        # -----------------------------------------

        if response.status_code != 200:

            return jsonify({

                "ok": False,

                "error": f"Ollama error {response.status_code}",

                "details": response.text

            })

        # -----------------------------------------
        # JSON CHECK
        # -----------------------------------------

        try:

            result = response.json()

        except Exception:

            return jsonify({

                "ok": False,

                "error": "Invalid JSON returned from Ollama",

                "raw": response.text

            })

        # -----------------------------------------
        # GET ANSWER
        # -----------------------------------------

        answer = result.get("response", "").strip()

        if not answer:

            return jsonify({

                "ok": False,

                "error": "Model returned empty response",

                "raw": result

            })

        # -----------------------------------------
        # SUCCESS
        # -----------------------------------------

        return jsonify({

            "ok": True,

            "result": answer

        })

    # =====================================================
    # ERRORS
    # =====================================================

    except requests.exceptions.ConnectionError:

        return jsonify({

            "ok": False,

            "error": "Cannot connect to Ollama. Make sure Ollama is running."

        })

    except requests.exceptions.Timeout:

        return jsonify({

            "ok": False,

            "error": "Ollama timed out while analyzing image."

        })

    except Exception as e:

        print("IMAGE ANALYZE ERROR:", e)

        return jsonify({

            "ok": False,

            "error": str(e)

        })