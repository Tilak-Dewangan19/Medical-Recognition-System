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
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "fake-key")
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
    assert "OPENROUTER_API_KEY" in body


def test_has_openrouter_config_rejects_placeholder_keys(monkeypatch):
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "sk-or-v1-37b...33e")
    assert app_module._has_openrouter_config() is False


def test_upload_uses_openrouter_when_configured(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "fake-key")
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


def test_openrouter_errors_surface_clear_message(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "fake-key")
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


def test_gen_image_uses_openrouter_when_configured(monkeypatch):
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(app_module, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

    def fake_call_openrouter(prompt, image):
        return "openrouter response"

    monkeypatch.setattr(app_module, "_call_openrouter", fake_call_openrouter)

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert result == "openrouter response"


def test_server_config_defaults_to_deployment_safe_values(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    config = app_module.get_server_config()

    assert config["host"] == "0.0.0.0"
    assert config["port"] == 5000
    assert config["debug"] is False


def test_analysis_prompt_requests_general_visual_description():
    prompt = app_module.get_analysis_prompt()

    assert "non-diagnostic" in prompt.lower()
    assert "visual description" in prompt.lower()
    assert "medical professional" in prompt.lower()
    assert "review the image" in prompt.lower()
