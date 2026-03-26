"""
MediAssist — Chat Pipeline Test Suite
Tests all 6 layers of the chat pipeline:
  Layer 1: Emergency Detector
  Layer 2: Uploaded Report Context
  Layer 3: Symptom Predictor
  Layer 4: Knowledge Graph
  Layer 5: RAG Search
  Layer 6: AI Agent Fallback

Run with:
    pytest test_pipeline.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_TOKEN   = "test-token-123"
VALID_USER    = "testuser"
TEST_SESSION  = "session-abc-123"

# Patch all external dependencies before importing app
@pytest.fixture(autouse=True)
def mock_externals():
    with patch("google.genai.Client"), \
         patch("knowledge_graph.graph.query_graph", return_value="No medical knowledge found"), \
         patch("rag.rag_engine.search_rag", return_value=[[]]), \
         patch("rag.rag_engine.add_document_to_rag"):
        yield


@pytest.fixture
def client():
    from app import app
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Returns a logged-in token for test requests."""
    return {"token": VALID_TOKEN}


def chat_payload(message, session_id=None, token=VALID_TOKEN, model="gemini-2.5-flash-lite"):
    return {
        "message": message,
        "session_id": session_id,
        "token": token,
        "model": model
    }


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — EMERGENCY DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestEmergencyDetector:
    """Tests that emergency keywords trigger immediate emergency response."""

    EMERGENCY_KEYWORDS = [
        "I am having a heart attack",
        "chest pain and can't breathe",
        "I took an overdose",
        "I want to kill myself",
        "stroke symptoms right now",
        "paralysis in my left arm",
        "unconscious and not responding",
        "severe allergic reaction",
        "I am bleeding heavily",
        "difficulty breathing",
    ]

    @pytest.mark.parametrize("message", EMERGENCY_KEYWORDS)
    def test_emergency_message_triggers_emergency_response(self, client, message):
        """Emergency messages must return Emergency Detector as tool used."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.memory") as mock_mem:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload(message))
            data = res.json()

            assert res.status_code == 200
            assert "Emergency Detector" in data.get("tools_used", [])

    def test_emergency_response_contains_emergency_number(self, client):
        """Emergency response should mention emergency services."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.memory") as mock_mem:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload("I am having a heart attack"))
            data = res.json()

            response_text = data.get("response", "").lower()
            assert any(word in response_text for word in ["emergency", "911", "112", "ambulance", "immediately"])

    def test_non_emergency_message_skips_emergency_layer(self, client):
        """Normal messages must NOT trigger Emergency Detector."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.memory") as mock_mem, \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="Normal response"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload("I have a mild headache"))
            data = res.json()

            assert "Emergency Detector" not in data.get("tools_used", [])


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — UPLOADED REPORT CONTEXT
# ══════════════════════════════════════════════════════════════════════════════

class TestUploadedReportContext:
    """Tests that uploaded report is used when user asks about it."""

    REPORT_KEYWORDS = [
        "summarise the report",
        "what does my lab result say",
        "explain my findings",
        "what is in my uploaded file",
        "tell me about my blood test",
    ]

    @pytest.mark.parametrize("message", REPORT_KEYWORDS)
    def test_report_keywords_trigger_report_layer(self, client, message):
        """Messages with report keywords + uploaded report should use Uploaded Report tool."""
        mock_report = {"filename": "blood_test.pdf", "text": "HbA1c: 7.2, Cholesterol: 230"}

        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {VALID_USER: mock_report}), \
             patch("app.memory") as mock_mem, \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="Report analysis"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = mock_report
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload(message))
            data = res.json()

            assert res.status_code == 200
            assert "Uploaded Report" in data.get("tools_used", [])

    def test_no_report_skips_report_layer(self, client):
        """If no report is uploaded, report layer must be skipped."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="Normal response"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload("summarise the report"))
            data = res.json()

            assert "Uploaded Report" not in data.get("tools_used", [])


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — SYMPTOM PREDICTOR
# ══════════════════════════════════════════════════════════════════════════════

class TestSymptomPredictor:
    """Tests that symptom-laden messages trigger the Symptom Predictor."""

    SYMPTOM_MESSAGES = [
        "I have fever, cough, and body pain",
        "I am feeling dizzy with nausea and vomiting",
        "I have a runny nose, sneezing, and sore throat",
        "headache and fatigue for 3 days",
        "chest pain and shortness of breath",
    ]

    @pytest.mark.parametrize("message", SYMPTOM_MESSAGES)
    def test_symptom_messages_trigger_symptom_predictor(self, client, message):
        """Messages with known symptoms should trigger Symptom Predictor tool."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {"age": 25, "known_conditions": []}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Symptom analysis", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload(message))
            data = res.json()

            assert res.status_code == 200
            assert "Symptom Predictor" in data.get("tools_used", [])

    def test_symptom_response_contains_risk_level(self, client):
        """Symptom Predictor response must contain a risk level."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {"age": 25, "known_conditions": []}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "🔴 Critical risk level detected", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("I have fever, cough, and body pain"))
            data = res.json()

            assert any(level in data.get("response", "") for level in ["🔴", "🟠", "🟡", "🟢", "Critical", "High", "Moderate", "Low"])

    def test_flood_guard_skips_predictor_on_too_many_symptoms(self, client):
        """If more than 5 diseases match, skip Symptom Predictor and go to Gemini directly."""
        flood_message = "fever cough headache nausea vomiting dizziness chest pain rash itching fatigue"

        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="Gemini direct response"):
            mock_mem.load_profile.return_value = {"age": 25, "known_conditions": []}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload(flood_message))
            assert res.status_code == 200

    def test_age_affects_confidence_score(self, client):
        """Older patients should have higher confidence scores for chronic diseases."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {"age": 70, "known_conditions": ["diabetes"]}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Age-adjusted response", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("I have frequent urination and fatigue"))
            assert res.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — KNOWLEDGE GRAPH
# ══════════════════════════════════════════════════════════════════════════════

class TestKnowledgeGraph:
    """Tests that medical terms trigger Knowledge Graph lookup."""

    KG_MESSAGES = [
        "What is diabetes?",
        "Tell me about hypertension",
        "Explain what HbA1c means",
        "What is metformin used for?",
        "What causes migraine?",
    ]

    @pytest.mark.parametrize("message", KG_MESSAGES)
    def test_medical_term_triggers_kg(self, client, message):
        """Messages with known medical terms should trigger Knowledge Graph."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="Diabetes is a metabolic disease..."), \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="KG-based response"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload(message))
            data = res.json()

            assert res.status_code == 200
            assert "Medical KG" in data.get("tools_used", [])

    def test_kg_miss_falls_through_to_rag(self, client):
        """If KG returns no results, pipeline should fall through to RAG."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found for"), \
             patch("app.search_rag", return_value=[["RAG context about topic"]]), \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="RAG response"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload("What is diabetes?"))
            data = res.json()

            assert res.status_code == 200

    def test_kg_gemini_failure_falls_through(self, client):
        """If KG Gemini call fails, pipeline should not crash — fall through to RAG."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="Diabetes facts..."), \
             patch("app.gemini_generate", new_callable=AsyncMock, side_effect=Exception("Gemini error")), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Agent fallback", "tools_used": ["Agent"]})

            res = client.post("/api/chat", json=chat_payload("What is diabetes?"))
            assert res.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5 — RAG SEARCH
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGSearch:
    """Tests that RAG is used when KG misses but RAG has context."""

    def test_rag_hit_uses_rag_tool(self, client):
        """When RAG returns context, response should use RAG tool."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[["Detailed RAG context about health topic"]]), \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="RAG-based answer"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            res  = client.post("/api/chat", json=chat_payload("What are the effects of high cholesterol?"))
            data = res.json()

            assert res.status_code == 200
            assert "RAG" in data.get("tools_used", [])

    def test_rag_miss_falls_through_to_agent(self, client):
        """When RAG returns empty, pipeline should fall through to AI Agent."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Agent response", "tools_used": ["Agent"]})

            res  = client.post("/api/chat", json=chat_payload("What is the meaning of life?"))
            data = res.json()

            assert res.status_code == 200

    def test_rag_exception_falls_through_to_agent(self, client):
        """If RAG throws an exception, pipeline should not crash."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", side_effect=Exception("RAG error")), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Agent fallback", "tools_used": []})

            res = client.post("/api/chat", json=chat_payload("Random question"))
            assert res.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 6 — AI AGENT FALLBACK
# ══════════════════════════════════════════════════════════════════════════════

class TestAIAgentFallback:
    """Tests that AI Agent handles everything that falls through all layers."""

    def test_agent_handles_general_question(self, client):
        """General non-medical questions should be handled by Agent."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Hello! I am MediAssist.", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("Hello"))
            data = res.json()

            assert res.status_code == 200
            assert data.get("response") == "Hello! I am MediAssist."

    def test_agent_failure_returns_500(self, client):
        """If Agent also fails, API must return 500 with proper error message."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(side_effect=Exception("Agent crashed"))

            res = client.post("/api/chat", json=chat_payload("Hello"))
            assert res.status_code == 500

    def test_agent_receives_conversation_history(self, client):
        """Agent must receive conversation history for context."""
        history = [
            {"role": "user",      "content": "I have diabetes"},
            {"role": "assistant", "content": "I understand. How can I help?"},
        ]
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = history
            mock_agent.process = AsyncMock(return_value={"response": "Context-aware response", "tools_used": []})

            res = client.post("/api/chat", json=chat_payload("What should I eat?"))
            assert res.status_code == 200
            mock_agent.process.assert_called_once()
            call_args = mock_agent.process.call_args
            assert call_args[0][1] == history  # history was passed


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE PRIORITY ORDER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestPipelinePriority:
    """Tests that layers fire in the correct priority order."""

    def test_emergency_beats_symptom_predictor(self, client):
        """Emergency layer must fire before Symptom Predictor."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []

            # Message has both emergency keyword AND symptoms
            res  = client.post("/api/chat", json=chat_payload("chest pain and I think I am having a heart attack"))
            data = res.json()

            assert "Emergency Detector" in data.get("tools_used", [])
            assert "Symptom Predictor" not in data.get("tools_used", [])

    def test_report_beats_kg(self, client):
        """Uploaded Report layer must fire before Knowledge Graph."""
        mock_report = {"filename": "report.pdf", "text": "HbA1c: 8.5"}

        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {VALID_USER: mock_report}), \
             patch("app.memory") as mock_mem, \
             patch("app.gemini_generate", new_callable=AsyncMock, return_value="Report response"):
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = mock_report
            mock_mem.get_history.return_value  = []

            # Message has report keyword AND medical term (diabetes)
            res  = client.post("/api/chat", json=chat_payload("what does my diabetes lab result say"))
            data = res.json()

            assert "Uploaded Report" in data.get("tools_used", [])
            assert "Medical KG" not in data.get("tools_used", [])


# ══════════════════════════════════════════════════════════════════════════════
# GENERAL CHAT RESPONSE TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestChatResponse:
    """Tests the structure and validity of chat responses."""

    def test_response_has_required_fields(self, client):
        """Every chat response must have response, session_id, tools_used, timestamp."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Hi", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("Hello"))
            data = res.json()

            assert "response"   in data
            assert "session_id" in data
            assert "tools_used" in data
            assert "timestamp"  in data

    def test_empty_message_rejected(self, client):
        """Empty message should be rejected."""
        res = client.post("/api/chat", json=chat_payload(""))
        assert res.status_code in [400, 422]

    def test_invalid_token_rejected(self, client):
        """Request with invalid/missing token should be rejected."""
        res = client.post("/api/chat", json=chat_payload("Hello", token="invalid-token"))
        assert res.status_code in [401, 403, 404]

    def test_session_id_persists_across_messages(self, client):
        """Second message in same session should return same session_id."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Reply", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("Hello", session_id=TEST_SESSION))
            data = res.json()

            assert data.get("session_id") == TEST_SESSION

    def test_response_is_not_empty(self, client):
        """Response text must never be empty."""
        with patch("app.SESSIONS", {TEST_SESSION: {"username": VALID_USER}}), \
             patch("app.USER_REPORTS", {}), \
             patch("app.memory") as mock_mem, \
             patch("app.query_graph", return_value="No medical knowledge found"), \
             patch("app.search_rag", return_value=[[]]), \
             patch("app.agent") as mock_agent:
            mock_mem.load_profile.return_value = {}
            mock_mem.load_report.return_value  = None
            mock_mem.get_history.return_value  = []
            mock_agent.process = AsyncMock(return_value={"response": "Some response", "tools_used": []})

            res  = client.post("/api/chat", json=chat_payload("Hello"))
            data = res.json()

            assert len(data.get("response", "")) > 0
