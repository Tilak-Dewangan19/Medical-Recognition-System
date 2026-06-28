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
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "fake-key")
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
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "")

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


def test_has_gemini_config_rejects_placeholder_keys(monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "...")
    assert app_module._has_gemini_config() is False


def test_has_gemini_config_accepts_runtime_environment_alias(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "runtime-key")
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "")
    assert app_module._has_gemini_config() is True


def test_upload_uses_gemini_when_configured(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "fake-key")
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
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "fake-key")
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


def test_gemini_high_demand_is_reported_clearly(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "fake-key")
    monkeypatch.setattr(app_module, "gen_image", lambda prompt, image: (_ for _ in ()).throw(RuntimeError("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand.'}}")))

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="yellow").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "temporarily unavailable" in body.lower()
    assert "high demand" in body.lower() or "try again later" in body.lower()


def test_call_gemini_falls_back_to_other_models(monkeypatch):
    class FakeModels:
        def __init__(self):
            self.calls = []

        def generate_content(self, *, model, contents):
            self.calls.append(model)
            if model == "gemini-2.5-flash":
                raise RuntimeError("model not found")
            return SimpleNamespace(text="fallback response")

    class FakeClient:
        def __init__(self):
            self.models = FakeModels()

    monkeypatch.setattr(app_module, "_get_gemini_client", lambda: FakeClient())
    monkeypatch.setattr(app_module, "GEMINI_MODEL", "gemini-2.5-flash")

    result = app_module._call_gemini("describe", Image.new("RGB", (8, 8), color="blue"))

    assert result == "fallback response"


def test_gen_image_uses_gemini_when_configured(monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "gemini-key")
    monkeypatch.setattr(app_module, "GEMINI_MODEL", "gemini-2.5-flash")

    def fake_call_gemini(prompt, image):
        return "gemini response"

    monkeypatch.setattr(app_module, "_call_gemini", fake_call_gemini)

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert result == "gemini response"


def test_server_config_defaults_to_deployment_safe_values(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    config = app_module.get_server_config()

    assert config["host"] == "0.0.0.0"
    assert config["port"] == 5000
    assert config["debug"] is False


def test_analysis_prompt_requests_general_visual_description():
    prompt = app_module.get_analysis_prompt()

    assert "medical-style description" in prompt.lower()
    assert "visible findings" in prompt.lower()
    assert "precautions" in prompt.lower()
    assert "professional care" in prompt.lower()
