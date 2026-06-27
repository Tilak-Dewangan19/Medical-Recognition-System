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
    from google import genai as google_genai
    from google.genai import types as genai_types
except Exception:
    google_genai = None
    genai_types = None

try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    import pydicom
    from pydicom import dcmread
except Exception:
    pydicom = None
    dcmread = None

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
# Use Flash 2.5 by default to enable up-to-date multimodal processing
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK", "").strip() or None

vis_model = None
gemini_client = None

if API_KEY:
    if google_genai is not None:
        try:
            gemini_client = google_genai.Client(api_key=API_KEY)
            vis_model = gemini_client.models
        except Exception:
            gemini_client = None
            vis_model = None
    elif genai is not None:
        try:
            genai.configure(api_key=API_KEY)
            vis_model = genai.GenerativeModel(MODEL_NAME)
        except Exception:
            vis_model = None

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


# Function to generate content
def gen_image(prompt, image):
    if not API_KEY or (vis_model is None and gemini_client is None):
        return None

    max_retries = 3
    backoff = 1
    last_exc = None

    models_to_try = [MODEL_NAME]
    if FALLBACK_MODEL and FALLBACK_MODEL != MODEL_NAME:
        models_to_try.append(FALLBACK_MODEL)

    for model in models_to_try:
        for attempt in range(1, max_retries + 1):
            try:
                if gemini_client is not None and genai_types is not None:
                    image_bytes = _image_to_bytes(image)
                    response = gemini_client.models.generate_content(
                        model=model,
                        contents=[
                            prompt,
                            genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                        ],
                    )
                    return getattr(response, "text", None)

                try:
                    model_inst = genai.GenerativeModel(model)
                except Exception:
                    model_inst = vis_model

                response = model_inst.generate_content([prompt, image])
                return getattr(response, "text", None)

            except Exception as exc:
                last_exc = exc
                msg = str(exc).lower()
                is_transient = any(token in msg for token in ["503", "unavailable", "high demand", "temporar", "quota", "429", "rate limit", "overloaded"])
                if is_transient and attempt < max_retries and model == models_to_try[-1]:
                    time.sleep(backoff)
                    backoff *= 2
                    continue
                if is_transient:
                    break
                raise

    if last_exc:
        raise last_exc
    return None


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


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        image_prompt = '''
                - Generate a very detailed medical description for the given image.
                - Identify and describe any relevant medical conditions, anomalies, or abnormalities present in the image.
                - Additionally, provide insights into any potential treatments or recommended actions based on the observed medical features.
                - Please ensure the generated content is accurate and clinically relevant.
                - Please don't provide false and misleading information.
                '''

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

        if not API_KEY or vis_model is None:
            return render_template('index.html', response_text="Gemini API is not configured. Please set GOOGLE_API_KEY in the environment or .env file.", image_url=image_url)

        try:
            response_text = gen_image(image_prompt, image)
        except Exception as exc:
            message = str(exc)
            if "quota" in message.lower() or "429" in message:
                return render_template('index.html', response_text="Gemini API quota exceeded. Please try again later or use a different API key.")
            if "api key" in message.lower() or "permission" in message.lower() or "forbidden" in message.lower():
                return render_template('index.html', response_text="Gemini API access failed. Please check your API key and permissions.")
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
    app.run(debug=True)