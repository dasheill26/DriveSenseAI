from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch

try:
    processor = BlipProcessor.from_pretrained(
        "Salesforce/blip-image-captioning-base"
    )
    model = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base"
    )
    model.eval()
except Exception as e:
    processor = None
    model = None
    print("MODEL LOAD ERROR:", e)


def analyze_image(path):
    if processor is None or model is None:
        return "I couldn't load the vision model."

    try:
        image = Image.open(path).convert("RGB")
        image = image.resize((512, 512))

        inputs = processor(image, return_tensors="pt")

        with torch.no_grad():
            output = model.generate(**inputs, max_length=30)

        caption = processor.decode(output[0], skip_special_tokens=True)

        # 🔥 CLEAN + SIMPLIFY OUTPUT
        caption = caption.lower()

        return f"I can see: {caption}"

    except Exception as e:
        return "I couldn't understand the image properly."