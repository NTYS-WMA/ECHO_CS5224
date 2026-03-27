"""
Tests for the AI Generation Service — refactored template-based architecture.

Covers:
- Template management (TemplateManager)
- Template rendering (TemplateRenderer)
- API route validation (template routes + generation routes)
- Request model validation
"""

import json
import os
import tempfile

import pytest
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from ..models.templates import (
    TemplateRegisterRequest,
    TemplateUpdateRequest,
    TemplateVariableSchema,
)
from ..services.template_manager import TemplateManager
from ..services.template_renderer import (
    TemplateRenderer,
    TemplateRenderError,
)


# ================================================================== #
# Fixtures
# ================================================================== #


@pytest.fixture
def templates_dir():
    """Create a temporary directory with a test template."""
    with tempfile.TemporaryDirectory() as tmpdir:
        template = {
            "template_id": "tpl_test",
            "name": "Test Template",
            "description": "A test template.",
            "version": "1.0.0",
            "owner": "test-service",
            "category": "test",
            "system_prompt": "You are a test assistant.",
            "user_prompt_template": "Process the following: {{input_text}}\nFormat: {{output_format}}",
            "variables": {
                "input_text": {
                    "type": "string",
                    "required": True,
                    "description": "The input text.",
                },
                "output_format": {
                    "type": "string",
                    "required": False,
                    "default": "plain",
                    "description": "Output format.",
                },
            },
            "defaults": {"temperature": 0.5, "max_tokens": 256},
            "tags": ["test"],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        with open(os.path.join(tmpdir, "test_template.json"), "w") as f:
            json.dump(template, f)
        yield tmpdir


@pytest.fixture
def manager(templates_dir):
    """Create a TemplateManager loaded with the test template."""
    mgr = TemplateManager(templates_dir=templates_dir)
    mgr.load_templates()
    return mgr


@pytest.fixture
def renderer(manager):
    """Create a TemplateRenderer with the test manager."""
    return TemplateRenderer(template_manager=manager)


@pytest.fixture
def real_manager():
    """Create a TemplateManager loaded with the real preset templates."""
    real_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompt_templates",
    )
    mgr = TemplateManager(templates_dir=real_dir)
    mgr.load_templates()
    return mgr


# ================================================================== #
# TemplateManager Tests
# ================================================================== #


class TestTemplateManager:
    """Tests for TemplateManager CRUD operations."""

    def test_load_templates(self, manager):
        """Should load templates from the directory."""
        assert manager.get_template("tpl_test") is not None

    def test_get_template_found(self, manager):
        """Should return a template by ID."""
        tpl = manager.get_template("tpl_test")
        assert tpl.name == "Test Template"
        assert tpl.category == "test"

    def test_get_template_not_found(self, manager):
        """Should return None for a non-existent template."""
        assert manager.get_template("tpl_nonexistent") is None

    def test_list_templates(self, manager):
        """Should list all templates."""
        items = manager.list_templates()
        assert len(items) == 1
        assert items[0].template_id == "tpl_test"

    def test_list_templates_filter_category(self, manager):
        """Should filter by category."""
        items = manager.list_templates(category="test")
        assert len(items) == 1
        items = manager.list_templates(category="nonexistent")
        assert len(items) == 0

    def test_list_templates_filter_owner(self, manager):
        """Should filter by owner."""
        items = manager.list_templates(owner="test-service")
        assert len(items) == 1
        items = manager.list_templates(owner="other-service")
        assert len(items) == 0

    def test_register_template(self, manager):
        """Should register a new template and assign an ID."""
        req = TemplateRegisterRequest(
            name="New Template",
            owner="caller-service",
            category="custom",
            system_prompt="System prompt.",
            user_prompt_template="Do: {{task}}",
            variables={
                "task": TemplateVariableSchema(
                    type="string", required=True, description="The task."
                )
            },
        )
        tpl = manager.register_template(req)
        assert tpl.template_id.startswith("tpl_")
        assert tpl.name == "New Template"
        assert tpl.version == "1.0.0"
        assert "task" in tpl.variables

        # Should be retrievable
        assert manager.get_template(tpl.template_id) is not None

    def test_register_duplicate_name_owner(self, manager):
        """Should reject duplicate name+owner combinations."""
        req = TemplateRegisterRequest(
            name="Test Template",
            owner="test-service",
            category="test",
            system_prompt="Duplicate.",
            user_prompt_template="{{x}}",
        )
        with pytest.raises(ValueError, match="already exists"):
            manager.register_template(req)

    def test_update_template(self, manager):
        """Should update a template and bump version."""
        req = TemplateUpdateRequest(description="Updated description.")
        updated = manager.update_template("tpl_test", req)
        assert updated.description == "Updated description."
        assert updated.version == "1.0.1"

    def test_update_template_not_found(self, manager):
        """Should raise KeyError for non-existent template."""
        req = TemplateUpdateRequest(description="Nope.")
        with pytest.raises(KeyError, match="not found"):
            manager.update_template("tpl_nonexistent", req)

    def test_load_real_preset_templates(self, real_manager):
        """Should load all 6 preset templates from the real directory."""
        items = real_manager.list_templates()
        assert len(items) >= 6
        ids = {item.template_id for item in items}
        assert "tpl_chat_completion" in ids
        assert "tpl_memory_compaction" in ids
        assert "tpl_proactive_outreach" in ids
        assert "tpl_safety_filter" in ids
        assert "tpl_sentiment_analysis" in ids
        assert "tpl_topic_extraction" in ids


# ================================================================== #
# TemplateRenderer Tests
# ================================================================== #


class TestTemplateRenderer:
    """Tests for TemplateRenderer rendering logic."""

    def test_render_with_all_variables(self, renderer):
        """Should render template with all variables provided."""
        messages, defaults = renderer.render(
            template_id="tpl_test",
            variables={"input_text": "Hello world", "output_format": "JSON"},
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a test assistant."
        assert "Hello world" in messages[1]["content"]
        assert "JSON" in messages[1]["content"]
        assert defaults.temperature == 0.5
        assert defaults.max_tokens == 256

    def test_render_with_default_variable(self, renderer):
        """Should apply default value for optional variable."""
        messages, defaults = renderer.render(
            template_id="tpl_test",
            variables={"input_text": "Test input"},
        )
        assert "plain" in messages[1]["content"]

    def test_render_missing_required_variable(self, renderer):
        """Should raise error when required variable is missing."""
        with pytest.raises(TemplateRenderError, match="Missing required"):
            renderer.render(template_id="tpl_test", variables={})

    def test_render_template_not_found(self, renderer):
        """Should raise error for non-existent template."""
        with pytest.raises(TemplateRenderError, match="not found"):
            renderer.render(template_id="tpl_nonexistent", variables={})

    def test_render_with_messages_no_system(self, renderer):
        """Should prepend system prompt when messages have no system message."""
        messages, defaults = renderer.render_with_messages(
            template_id="tpl_test",
            messages=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
        )
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a test assistant."
        assert len(messages) == 3

    def test_render_with_messages_merge_system(self, renderer):
        """Should merge system prompts when messages already have one."""
        messages, defaults = renderer.render_with_messages(
            template_id="tpl_test",
            messages=[
                {"role": "system", "content": "Custom system prompt."},
                {"role": "user", "content": "Hello"},
            ],
        )
        assert messages[0]["role"] == "system"
        assert "You are a test assistant." in messages[0]["content"]
        assert "Custom system prompt." in messages[0]["content"]
        assert len(messages) == 2

    def test_render_with_system_prompt_override(self, renderer):
        """Should use system_prompt_override when provided."""
        messages, defaults = renderer.render(
            template_id="tpl_test",
            variables={"input_text": "Test"},
            system_prompt_override="Override system prompt.",
        )
        assert messages[0]["content"] == "Override system prompt."


# ================================================================== #
# API Route Tests (using FastAPI TestClient)
# ================================================================== #


@pytest.fixture
def client(real_manager):
    """Create a test client with mocked dependencies."""
    from ..app import create_app
    from ..services.generation_service import GenerationService

    app = create_app()

    # Override dependency injection
    mock_service = MagicMock(spec=GenerationService)

    from ..routes.generation_routes import get_generation_service
    from ..routes.template_routes import get_template_manager

    app.dependency_overrides[get_generation_service] = lambda: mock_service
    app.dependency_overrides[get_template_manager] = lambda: real_manager

    return TestClient(app)


class TestTemplateRoutes:
    """Tests for template management API routes."""

    def test_list_templates(self, client):
        """GET /api/v1/templates should return all templates."""
        response = client.get("/api/v1/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 6
        assert len(data["templates"]) >= 6

    def test_list_templates_filter_category(self, client):
        """GET /api/v1/templates?category=analysis should filter."""
        response = client.get("/api/v1/templates?category=analysis")
        assert response.status_code == 200
        data = response.json()
        assert all(t["category"] == "analysis" for t in data["templates"])

    def test_get_template(self, client):
        """GET /api/v1/templates/{id} should return the template."""
        response = client.get("/api/v1/templates/tpl_chat_completion")
        assert response.status_code == 200
        data = response.json()
        assert data["template_id"] == "tpl_chat_completion"
        assert "user_prompt" in data["variables"]

    def test_get_template_not_found(self, client):
        """GET /api/v1/templates/{id} should return 404 for unknown ID."""
        response = client.get("/api/v1/templates/tpl_nonexistent")
        assert response.status_code == 404

    def test_register_template(self, client):
        """POST /api/v1/templates should register a new template."""
        import uuid
        unique_name = f"API Test Template {uuid.uuid4().hex[:8]}"
        payload = {
            "name": unique_name,
            "owner": "api-test",
            "category": "test",
            "system_prompt": "Test system prompt.",
            "user_prompt_template": "Do: {{task}}",
            "variables": {
                "task": {
                    "type": "string",
                    "required": True,
                    "description": "Task to do.",
                }
            },
        }
        response = client.post("/api/v1/templates", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["template_id"].startswith("tpl_")
        assert data["name"] == unique_name
        assert "task" in data["variables"]

    def test_update_template(self, client):
        """PUT /api/v1/templates/{id} should update the template."""
        payload = {"description": "Updated via API test."}
        response = client.put(
            "/api/v1/templates/tpl_chat_completion", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated via API test."

    def test_update_template_not_found(self, client):
        """PUT /api/v1/templates/{id} should return 404 for unknown ID."""
        payload = {"description": "Nope."}
        response = client.put("/api/v1/templates/tpl_nonexistent", json=payload)
        assert response.status_code == 404


class TestHealthRoutes:
    """Test health check endpoints."""

    def setup_method(self):
        from ..app import create_app

        self.app = create_app()
        self.client = TestClient(self.app)

    def test_health_check(self):
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_readiness_check(self):
        response = self.client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestGenerationRouteValidation:
    """Tests for generation API route request validation."""

    def setup_method(self):
        from ..app import create_app
        from ..services.generation_service import GenerationService

        self.app = create_app()
        mock_service = MagicMock(spec=GenerationService)

        from ..routes.generation_routes import get_generation_service

        self.app.dependency_overrides[get_generation_service] = lambda: mock_service
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    def test_execute_missing_template_id(self):
        """POST /execute should require template_id."""
        payload = {"user_id": "usr_1"}
        response = self.client.post("/api/v1/generation/execute", json=payload)
        assert response.status_code == 422

    def test_execute_missing_user_id(self):
        """POST /execute should require user_id."""
        payload = {"template_id": "tpl_chat_completion"}
        response = self.client.post("/api/v1/generation/execute", json=payload)
        assert response.status_code == 422



class TestEmbeddingRouteValidation:
    """Tests for embedding API route request validation."""

    def setup_method(self):
        from ..app import create_app
        from ..services.generation_service import GenerationService

        self.app = create_app()
        mock_service = MagicMock(spec=GenerationService)

        from ..routes.generation_routes import get_generation_service

        self.app.dependency_overrides[get_generation_service] = lambda: mock_service
        self.client = TestClient(self.app)

    def teardown_method(self):
        self.app.dependency_overrides.clear()

    def test_embedding_missing_user_id(self):
        """POST /embeddings should require user_id."""
        payload = {"input": "some text"}
        response = self.client.post("/api/v1/generation/embeddings", json=payload)
        assert response.status_code == 422

    def test_embedding_missing_input(self):
        """POST /embeddings should require input."""
        payload = {"user_id": "usr_1"}
        response = self.client.post("/api/v1/generation/embeddings", json=payload)
        assert response.status_code == 422

    def test_embedding_empty_input(self):
        """POST /embeddings should reject empty input string."""
        payload = {"user_id": "usr_1", "input": ""}
        response = self.client.post("/api/v1/generation/embeddings", json=payload)
        assert response.status_code == 422

    def test_embedding_valid_request(self):
        """POST /embeddings should accept a valid request."""
        from unittest.mock import AsyncMock
        from ..models.responses import EmbeddingResponse, UsageInfo

        mock_response = EmbeddingResponse(
            response_id="gen-test",
            embedding=[0.1, 0.2, 0.3],
            dimension=3,
            model="amazon.titan-embed-text-v2:0",
            usage=UsageInfo(input_tokens=5, output_tokens=0),
        )

        from ..routes.generation_routes import get_generation_service

        mock_service = self.app.dependency_overrides[get_generation_service]()
        mock_service.embed = AsyncMock(return_value=mock_response)

        self.app.dependency_overrides[get_generation_service] = lambda: mock_service

        payload = {
            "user_id": "usr_1",
            "input": "Hello world",
            "correlation_id": "evt-emb-001",
        }
        response = self.client.post("/api/v1/generation/embeddings", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "embedding" in data
        assert data["dimension"] == 3
        assert data["model"] == "amazon.titan-embed-text-v2:0"


class TestEmbeddingRequestModel:
    """Tests for EmbeddingRequest Pydantic model validation."""

    def test_embedding_request_valid(self):
        """Should accept a valid EmbeddingRequest."""
        from ..models.requests import EmbeddingRequest

        req = EmbeddingRequest(
            user_id="usr_1",
            input="Hello world",
        )
        assert req.user_id == "usr_1"
        assert req.input == "Hello world"
        assert req.correlation_id is None

    def test_embedding_request_with_correlation_id(self):
        """Should accept EmbeddingRequest with correlation_id."""
        from ..models.requests import EmbeddingRequest

        req = EmbeddingRequest(
            user_id="usr_1",
            input="Hello",
            correlation_id="evt-emb-001",
        )
        assert req.correlation_id == "evt-emb-001"


class TestRequestModels:
    """Tests for Pydantic request model validation."""

    def test_template_generation_request_valid(self):
        """Should accept a valid TemplateGenerationRequest."""
        from ..models.requests import TemplateGenerationRequest

        req = TemplateGenerationRequest(
            user_id="usr_1",
            template_id="tpl_chat_completion",
            variables={"user_prompt": "Hello"},
        )
        assert req.user_id == "usr_1"
        assert req.template_id == "tpl_chat_completion"

    def test_template_generation_request_with_messages(self):
        """Should accept TemplateGenerationRequest with messages."""
        from ..models.requests import MessageItem, TemplateGenerationRequest

        req = TemplateGenerationRequest(
            user_id="usr_1",
            template_id="tpl_chat_completion",
            messages=[MessageItem(role="user", content="Hello")],
        )
        assert len(req.messages) == 1

    def test_template_register_request_valid(self):
        """Should accept a valid TemplateRegisterRequest."""
        req = TemplateRegisterRequest(
            name="Test",
            owner="test",
            system_prompt="Sys",
            user_prompt_template="{{x}}",
        )
        assert req.name == "Test"
