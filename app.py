import io
import logging
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

# Load environment variables from .env for local development
load_dotenv(Path(__file__).resolve().parent / ".env")


GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK", "gemini-2.5-pro").strip() or "gemini-2.5-pro"


def _get_gemini_api_key():
    module_key = (GOOGLE_API_KEY or "").strip()
    if module_key and module_key not in {"...", "your_google_api_key", "your_key_here", "GOOGLE_API_KEY"}:
        return module_key

    for env_name in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_API_KEY"):
        value = os.getenv(env_name, "").strip()
        if value and value not in {"...", "your_google_api_key", "your_key_here", "GOOGLE_API_KEY"}:
            return value
    return ""


def _has_gemini_config(api_key=None):
    cleaned = (api_key if api_key is not None else _get_gemini_api_key()).strip()
    if not cleaned:
        return False
    if cleaned in {"...", "your_google_api_key", "your_key_here", "GOOGLE_API_KEY"}:
        return False
    if "..." in cleaned:
        return False
    return True

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
app.logger.setLevel(logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tif', '.tiff', '.webp', '.dcm', '.dicom'}

# Directory to store uploaded images for display
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / 'static' / 'uploads'
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def _get_gemini_client():
    api_key = _get_gemini_api_key()
    if not _has_gemini_config(api_key):
        raise RuntimeError("Gemini API key is not configured. Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment or .env file.")

    try:
        from google import genai
    except Exception as exc:
        raise RuntimeError("google-genai package is required for Gemini analysis") from exc

    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        raise RuntimeError(f"Unable to initialize Gemini client: {exc}") from exc


def _is_gemini_retryable_error(message):
    lowered = (message or "").lower()
    if not lowered:
        return False

    if "429" in lowered or "quota" in lowered or "rate limit" in lowered or "resource exhausted" in lowered:
        return True
    if "503" in lowered or "temporarily unavailable" in lowered or "high demand" in lowered or "overloaded" in lowered:
        return True
    if "model" in lowered and ("not found" in lowered or "unsupported" in lowered or "invalid" in lowered or "not available" in lowered or "not enabled" in lowered):
        return True
    return False


def _get_gemini_fallback_response():
    return (
        "The image was uploaded successfully, but the Gemini API is currently rate-limited or temporarily unavailable. "
        "A live AI description could not be retrieved right now. Please try again in a few minutes, or use a different API key or a higher-quota account. "
        "If this is urgent, please consult a qualified healthcare professional for review."
    )


def _call_gemini(prompt, image):
    client = _get_gemini_client()
    image_bytes = io.BytesIO()
    image.save(image_bytes, format=getattr(image, "format", None) or "PNG")
    image_bytes = image_bytes.getvalue()

    try:
        from google.genai import types
    except Exception as exc:
        raise RuntimeError("google-genai SDK does not expose the required types module") from exc

    image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/png")
    prompt_part = types.Part.from_text(text=prompt)

    models_to_try = []
    if GEMINI_MODEL:
        models_to_try.append(GEMINI_MODEL)
    if GEMINI_FALLBACK_MODEL and GEMINI_FALLBACK_MODEL != GEMINI_MODEL:
        models_to_try.append(GEMINI_FALLBACK_MODEL)

    last_error = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[prompt_part, image_part],
            )
            return getattr(response, "text", None) or ""
        except Exception as exc:
            message = str(exc)
            last_error = exc
            if _is_gemini_retryable_error(message) and len(models_to_try) > 1 and model_name != models_to_try[-1]:
                app.logger.warning("Gemini request failed for model %s; retrying with fallback model. Error: %s", model_name, message)
                continue
            break

    raise RuntimeError(f"Gemini request failed: {last_error}") from last_error


# Function to generate content
def gen_image(prompt, image):
    if not _has_gemini_config():
        return None

    try:
        return _call_gemini(prompt, image)
    except Exception as exc:
        lowered = str(exc).lower()
        if _is_gemini_retryable_error(lowered):
            app.logger.warning("Gemini service unavailable, returning fallback description. Error: %s", exc)
            return _get_gemini_fallback_response()
        raise


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


def log_startup_config():
    """Log startup configuration for debugging deployment issues"""
    app.logger.info("="*60)
    app.logger.info("STARTUP CONFIGURATION DIAGNOSTICS")
    app.logger.info("="*60)
    
    # Check API Key
    api_key = _get_gemini_api_key()
    if api_key and _has_gemini_config(api_key):
        app.logger.info(f"✓ Google API Key is configured (length: {len(api_key)})")
    else:
        app.logger.error("✗ Google API Key is NOT configured properly!")
        app.logger.error("   - Check that GOOGLE_API_KEY environment variable is set")
        app.logger.error("   - In local dev: add to .env file")
        app.logger.error("   - In production: set via platform config (Heroku, Railway, etc)")
    
    # Check models
    app.logger.info(f"✓ Primary model: {GEMINI_MODEL}")
    app.logger.info(f"✓ Fallback model: {GEMINI_FALLBACK_MODEL}")
    
    # Check upload directory
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        if UPLOAD_DIR.exists() and os.access(UPLOAD_DIR, os.W_OK):
            app.logger.info(f"✓ Upload directory writable: {UPLOAD_DIR}")
        else:
            app.logger.warning(f"✗ Upload directory not writable: {UPLOAD_DIR}")
    except Exception as e:
        app.logger.error(f"✗ Failed to verify upload directory: {e}")
    
    # Check dependencies
    try:
        from google import genai
        app.logger.info("✓ google-genai package is available")
    except ImportError:
        app.logger.error("✗ google-genai package NOT available - install with: pip install google-genai")
    
    app.logger.info("="*60)



def get_analysis_prompt():
    return (
        "You are analyzing an uploaded medical image. Provide a detailed, structured medical-style description of what is visually present. "
        "Describe the likely visible findings, possible medical relevance, and any notable patterns, textures, shapes, landmarks, or abnormalities. "
        "If the image appears to show a wound, rash, lesion, scan, X-ray, ultrasound, MRI, or other clinical image, explain the visible features in a clear and clinically useful way. "
        "Mention general possible causes or conditions only in a non-diagnostic, informational manner, and suggest that a qualified medical professional should review the image for confirmation. "
        "Also include brief, practical guidance such as general precautions, monitoring suggestions, and when professional care should be sought. "
        "If appropriate, mention general over-the-counter medication categories that may be considered only as non-prescriptive informational guidance, while clearly stating that a clinician should confirm any treatment."
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

        if not _has_gemini_config():
            return render_template('index.html', response_text="Gemini API is not configured or the key is invalid. Please set GOOGLE_API_KEY to a real Gemini key in the environment or .env file.", image_url=image_url)

        try:
            response_text = gen_image(image_prompt, image)
        except Exception as exc:
            app.logger.exception("Gemini request failed")
            message = str(exc)
            lowered = message.lower()
            if "quota" in lowered or "429" in message or "rate limit" in lowered or "resource exhausted" in lowered or "exceeded" in lowered:
                return render_template('index.html', response_text="Gemini API quota or rate-limit exceeded. Your deployment may be hitting the account limit. Please wait a while, reduce upload frequency, or use a higher-quota key.")
            if "503" in lowered or "unavailable" in lowered or "high demand" in lowered:
                return render_template('index.html', response_text="The Gemini model is temporarily unavailable due to high demand. Please try again later or use a different key or model.")
            if "api key" in lowered or "permission" in lowered or "forbidden" in lowered or "unauthorized" in lowered:
                return render_template('index.html', response_text="Gemini API access failed. Please check your API key and permissions.")
            if "model" in lowered and "not found" in lowered:
                return render_template('index.html', response_text="The configured Gemini model is unavailable in your account. Please update GEMINI_MODEL to a supported model.")
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


# Log configuration on startup
log_startup_config()


if __name__ == '__main__':
    app.run(**get_server_config())


@app.errorhandler(500)
def handle_500_error(error):
    app.logger.exception("Unhandled exception - 500 error")
    message = "An unexpected error occurred. Please try again later or check your API key configuration."
    try:
        return render_template('index.html', response_text=message), 500
    except Exception as render_error:
        app.logger.exception("Failed to render error template")
        return (
            f"<html><body><h1>Internal Server Error</h1>"
            f"<p>An unexpected error occurred.</p>"
            f"<p>Error: {render_error}</p></body></html>",
            500
        )


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled exception")
    message = "An unexpected error occurred while processing your request."
    if app.debug:
        message = f"Internal server error: {error}"
    try:
        return render_template('index.html', response_text=message), 500
    except Exception as render_error:
        app.logger.exception("Failed to render error template in exception handler")
        return (
            "<html><body><h1>Error</h1>"
            f"<p>{message}</p></body></html>",
            500
        )