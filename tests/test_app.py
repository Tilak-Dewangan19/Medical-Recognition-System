import io
from pathlib import Path
import sys
import types
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


def test_call_gemini_retries_on_quota_error(monkeypatch):
    calls = []

    class FakeModels:
        def generate_content(self, model, contents):
            calls.append(model)
            if len(calls) == 1:
                raise RuntimeError("429 Resource exhausted: quota exceeded")
            return SimpleNamespace(text="fallback description")

    fake_client = SimpleNamespace(models=FakeModels())
    fake_types_module = types.ModuleType("google.genai.types")
    fake_types_module.Part = SimpleNamespace(
        from_bytes=lambda data, mime_type: object(),
        from_text=lambda text: object(),
    )
    fake_genai_module = types.ModuleType("google.genai")
    fake_genai_module.types = fake_types_module
    fake_genai_module.__path__ = []
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai_module)
    monkeypatch.setitem(sys.modules, "google.genai.types", fake_types_module)
    monkeypatch.setattr(app_module, "_get_gemini_client", lambda: fake_client)
    monkeypatch.setattr(app_module, "GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(app_module, "GEMINI_FALLBACK_MODEL", "gemini-2.0-flash")

    response = app_module._call_gemini("prompt", Image.new("RGB", (4, 4), color="blue"))

    assert response == "fallback description"
    assert calls == ["gemini-2.5-flash", "gemini-2.0-flash"]


def test_call_openrouter_returns_text(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=60):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"].startswith("Bearer ")
        return SimpleNamespace(json=lambda: {"choices": [{"message": {"content": "openrouter description"}}]})

    monkeypatch.setattr(app_module.requests, "post", fake_post)
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "fake-openrouter-key")
    monkeypatch.setattr(app_module, "OPENROUTER_MODEL", "openai/gpt-4o-mini")

    response = app_module._call_openrouter("prompt", Image.new("RGB", (4, 4), color="blue"))

    assert response == "openrouter description"


def test_upload_shows_configuration_message_when_api_key_is_missing(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_API_KEY", raising=False)
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


def test_has_gemini_config_rejects_placeholder_keys(monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "...")
    assert app_module._has_gemini_config() is False


def test_has_gemini_config_accepts_runtime_environment_alias(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "runtime-key")
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "")
    assert app_module._has_gemini_config() is True


def test_has_openrouter_config_accepts_runtime_environment(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "runtime-openrouter-key")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "")
    assert app_module._has_openrouter_config() is True


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


def test_upload_works_when_only_openrouter_is_configured(monkeypatch):
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(app_module, "gen_image", lambda prompt, image: "OpenRouter medical description")

    img_bytes = io.BytesIO()
    Image.new("RGB", (32, 32), color="purple").save(img_bytes, format="PNG")
    img_bytes.seek(0)

    response = client.post(
        "/",
        data={"file": (img_bytes, "test.png")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "OpenRouter medical description" in body


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


def test_gen_image_prefers_openrouter_when_configured(monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "gemini-key")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "openrouter-key")
    monkeypatch.setattr(app_module, "GEMINI_MODEL", "gemini-2.5-flash")

    def fake_call_openrouter(prompt, image):
        return "openrouter response"

    def fake_call_gemini(prompt, image):
        raise RuntimeError("gemini should not be used")

    monkeypatch.setattr(app_module, "_call_openrouter", fake_call_openrouter)
    monkeypatch.setattr(app_module, "_call_gemini", fake_call_gemini)

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert result == "openrouter response"


def test_gen_image_uses_gemini_when_configured(monkeypatch):
    monkeypatch.setattr(app_module, "GOOGLE_API_KEY", "gemini-key")
    monkeypatch.setattr(app_module, "OPENROUTER_API_KEY", "")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(app_module, "_get_runtime_setting", lambda name, default="": "")
    monkeypatch.setattr(app_module, "GEMINI_MODEL", "gemini-2.5-flash")

    def fake_call_gemini(prompt, image):
        return "gemini response"

    monkeypatch.setattr(app_module, "_call_gemini", fake_call_gemini)

    image = Image.new("RGB", (8, 8), color="blue")

    result = app_module.gen_image("describe this image", image)

    assert "Gemini API is currently rate-limited" in result


def test_server_config_defaults_to_deployment_safe_values(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    config = app_module.get_server_config()

    assert config["host"] == "0.0.0.0"
    assert config["port"] == 5000
    assert config["debug"] is False


def test_analysis_prompt_requests_general_visual_description():
    prompt = app_module.get_analysis_prompt()

    assert "medically relevant description" in prompt.lower()
    assert "visible findings" in prompt.lower()
    assert "precautions" in prompt.lower()
    assert "professional medical care" in prompt.lower()
