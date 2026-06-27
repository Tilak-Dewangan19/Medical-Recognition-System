import io
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as app_module


def test_response_is_accepted_when_yes_is_present():
    assert app_module.is_medical_context_response("Yes") is True
    assert app_module.is_medical_context_response("yes") is True
    assert app_module.is_medical_context_response("The image is medical") is True


def test_response_is_rejected_when_no_is_present():
    assert app_module.is_medical_context_response("No") is False
    assert app_module.is_medical_context_response("not medical") is False


def test_dicom_extensions_are_supported():
    assert ".dcm" in app_module.ALLOWED_EXTENSIONS
    assert ".dicom" in app_module.ALLOWED_EXTENSIONS


def test_upload_returns_generated_result_even_when_validation_says_no(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "gen_image", lambda prompt, image: "A medical description")
    monkeypatch.setattr(app_module, "validate", lambda prompt: "No")

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "A medical description" in response.get_data(as_text=True)


def test_upload_shows_configuration_message_when_api_key_is_missing(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "API_KEY", "")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "")

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="blue").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "GOOGLE_API_KEY" in body


def test_upload_uses_gemini_when_api_key_exists(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "vis_model", object())
    monkeypatch.setattr(app_module, "gen_image", lambda prompt, image: "A medical description")

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="green").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "A medical description" in body


def test_gemini_errors_surface_clear_message(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "vis_model", object())
    monkeypatch.setattr(app_module, "gen_image", lambda prompt, image: (_ for _ in ()).throw(RuntimeError("quota exceeded")))

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "quota exceeded" in body.lower() or "quota" in body.lower()


def test_gen_image_retries_with_fallback_model_when_quota_is_exceeded(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs["model"])
            if kwargs["model"] == "gemini-2.5-flash":
                raise RuntimeError("429 quota exceeded")
            return SimpleNamespace(text="fallback response")

    fake_client = SimpleNamespace(models=FakeModels())
    fake_part = SimpleNamespace(from_bytes=lambda data, mime_type: {"data": data, "mime_type": mime_type})

    monkeypatch.setattr(app_module, "API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "vis_model", None)
    monkeypatch.setattr(app_module, "gemini_client", fake_client)
    monkeypatch.setattr(app_module, "genai_types", SimpleNamespace(Part=fake_part))
    monkeypatch.setattr(app_module, "MODEL_NAME", "gemini-2.5-flash")
    monkeypatch.setattr(app_module, "FALLBACK_MODEL", "gemini-2.5-pro")

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert result == "fallback response"
    assert calls == ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_gen_image_uses_openrouter_when_gemini_fails(monkeypatch):
    monkeypatch.setattr(app_module, "API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(app_module, "OPENROUTER_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setattr(app_module, "vis_model", None)
    monkeypatch.setattr(app_module, "gemini_client", None)
    monkeypatch.setattr(app_module, "genai_types", None)
    monkeypatch.setattr(app_module, "MODEL_NAME", "gemini-2.5-flash")
    monkeypatch.setattr(app_module, "FALLBACK_MODEL", None)

    def fake_call_openrouter(prompt, image):
        return "openrouter fallback response"

    monkeypatch.setattr(app_module, "_call_openrouter", fake_call_openrouter)

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert result == "openrouter fallback response"
