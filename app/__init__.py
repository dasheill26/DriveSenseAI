import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()


def create_app():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    app = Flask(
        __name__,
        template_folder=os.path.join(project_root, "templates"),
        static_folder=os.path.join(project_root, "static")
    )

    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # MAIN ROUTES
    from .routes import main
    app.register_blueprint(main)

    # IMAGE AI
    try:
        from app.api.analyze_image import image_api
        app.register_blueprint(image_api)
        print("✅ Image API loaded")
    except Exception as e:
        print("❌ Image API error:", e)

    # 🔥 WHISPER SPEECH
    try:
        from app.api.speech import speech_api
        app.register_blueprint(speech_api)
        print("✅ Speech API loaded")
    except Exception as e:
        print("❌ Speech API error:", e)

    return app