import base64
import io
import os
from pathlib import Path
from PIL import Image
import time
import re
from markupsafe import escape as markupsafe_escape
from dotenv import load_dotenv
from flask import Flask, request, render_template, url_for
from werkzeug.utils import secure_filename

try:
    import pydicom
    from pydicom import dcmread
except Exception:
    pydicom = None
    dcmread = None

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip() or "openai/gpt-4o-mini"


def _has_openrouter_config():
    cleaned = (OPENROUTER_API_KEY or "").strip()
    if not cleaned:
        return False
    if cleaned in {"...", "your_openrouter_api_key", "your_key_here"}:
        return False
    if cleaned.startswith("sk-or") and len(cleaned) < 20:
        return False
    if "..." in cleaned:
        return False
    return True

app = Flask(__name__)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp', '.dcm', '.dicom'}

# Directory to store uploaded images for display
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'static' / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _image_to_bytes(image):
    buffer = io.BytesIO()
    image_format = getattr(image, "format", None) or "PNG"
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def _call_openrouter(prompt, image):
    if not _has_openrouter_config():
        return None

    try:
        import requests
    except Exception:
        raise RuntimeError("requests package is required for OpenRouter fallback")

    image_bytes = _image_to_bytes(image)
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful medical image analysis assistant."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        },
                    },
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("choices", [{}])[0].get("message", {}).get("content", "")


# Function to generate content
def gen_image(prompt, image):
    if not _has_openrouter_config():
        return None

    try:
        return _call_openrouter(prompt, image)
    except Exception as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc


def load_image_from_upload(uploaded_file):
    uploaded_file.stream.seek(0)
    file_extension = Path(uploaded_file.filename).suffix.lower()

    try:
        image = Image.open(uploaded_file)
        image.load()
        return image
    except Exception:
        if file_extension in {'.dcm', '.dicom'} and dcmread is not None:
            uploaded_file.stream.seek(0)
            dataset = dcmread(uploaded_file)
            pixel_array = getattr(dataset, 'pixel_array', None)
            if pixel_array is not None:
                array = pixel_array
                if array.ndim == 2:
                    return Image.fromarray(array)
                if array.ndim >= 3:
                    return Image.fromarray(array[:, :, :3])
        raise


def is_medical_context_response(response_text):
    if not response_text:
        return False

    cleaned = response_text.strip().lower()
    if cleaned.startswith("yes"):
        return True

    if cleaned.startswith("no"):
        return False

    return "medical" in cleaned or "health" in cleaned or "diagnosis" in cleaned or "image" in cleaned


def validate(prompt):
    if not prompt:
        return "No"

    cleaned = prompt.strip().lower()
    if any(term in cleaned for term in ["medical", "diagnosis", "image", "anomaly", "abnormality", "condition"]):
        return "Yes"
    return "No"


def get_server_config():
    return {
        "host": os.getenv("HOST", "0.0.0.0"),
        "port": int(os.getenv("PORT", "5000")),
        "debug": False,
    }


def get_analysis_prompt():
    return (
        "You are analyzing an uploaded medical image. Provide a detailed but non-diagnostic visual description "
        "of the image contents. Describe visible structures, patterns, textures, landmarks, or abnormalities "
        "in a clear way that could help a clinician or user understand what is shown. If the image is an X-ray, "
        "ultrasound, MRI, wound, scan, or other medical image, mention the most relevant visible features and "
        "note that a qualified medical professional should review the image for interpretation."
    )


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        image_prompt = get_analysis_prompt()

        uploaded_file = request.files.get('file')
        if not uploaded_file or uploaded_file.filename == '':
            return render_template('index.html', response_text="Please upload a medical image first.")

        file_extension = Path(uploaded_file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            return render_template('index.html', response_text="Please upload a valid medical image file such as JPG, PNG, BMP, GIF, TIFF, or WebP.")

        try:
            # Save the uploaded file so we can display it alongside the generated text
            uploaded_file.stream.seek(0)
            filename = secure_filename(uploaded_file.filename)
            save_name = f"{int(time.time())}_{filename}"
            save_path = UPLOAD_DIR / save_name
            uploaded_file.stream.seek(0)
            uploaded_file.save(str(save_path))

            # Rewind and load image for model processing
            uploaded_file.stream.seek(0)
            image = load_image_from_upload(uploaded_file)
            image_url = url_for('static', filename=f'uploads/{save_name}')
        except Exception:
            return render_template('index.html', response_text="The uploaded file is not a valid image. Please try another file or convert a DICOM/X-ray scan to JPG or PNG.")

        if not _has_openrouter_config():
            return render_template('index.html', response_text="OpenRouter API is not configured or the key is invalid. Please set OPENROUTER_API_KEY to a real OpenRouter key in the environment or .env file.", image_url=image_url)

        try:
            response_text = gen_image(image_prompt, image)
        except Exception as exc:
            message = str(exc)
            if "quota" in message.lower() or "429" in message:
                return render_template('index.html', response_text="OpenRouter API quota exceeded. Please try again later or use a different API key.")
            if "api key" in message.lower() or "permission" in message.lower() or "forbidden" in message.lower():
                return render_template('index.html', response_text="OpenRouter API access failed. Please check your API key and permissions.")
            return render_template('index.html', response_text=f"The image could not be processed right now. Please try again. ({exc})", image_url=image_url)

        if response_text:
            # Convert simple markdown-like bold (**text**) into safe HTML <strong> for readability
            try:
                escaped = markupsafe_escape(response_text)
                # Replace **bold** with <strong>bold</strong>
                html_with_bold = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
                # Preserve line breaks
                response_html = html_with_bold.replace('\n', '<br/>')
            except Exception:
                response_html = markupsafe_escape(response_text).replace('\n', '<br/>')

            return render_template('index.html', response_text=response_text, response_html=response_html, image_url=image_url)
        else:
            return render_template('index.html', response_text="Please provide a valid medical image.", response_html=None, image_url=image_url)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(**get_server_config())