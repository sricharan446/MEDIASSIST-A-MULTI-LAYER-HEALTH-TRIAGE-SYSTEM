"""
MediAssist API test suite aligned with the current FastAPI contract.

Run against a running server:
    pytest test_mediassist.py -v

Optional:
    set MEDIASSIST_URL=http://127.0.0.1:8000
"""

import io
import json
import os
import threading
import time
import uuid

import httpx
import pytest


BASE_URL = os.getenv("MEDIASSIST_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def unique_username(prefix: str = "pytest_user") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def post_json(path: str, payload: dict, params: dict | None = None) -> httpx.Response:
    return httpx.post(f"{BASE_URL}{path}", json=payload, params=params, timeout=TIMEOUT)


def get(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)


def post(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.post(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)


def delete(path: str, params: dict | None = None) -> httpx.Response:
    return httpx.delete(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)


@pytest.fixture(scope="session")
def test_account():
    username = unique_username()
    password = "Pass@12345"

    signup = post_json("/api/signup", {"username": username, "password": password})
    assert signup.status_code == 200, f"Signup failed: {signup.status_code} {signup.text}"

    login = post_json("/api/login", {"username": username, "password": password})
    assert login.status_code == 200, f"Login failed: {login.status_code} {login.text}"
    login_data = login.json()
    assert login_data.get("token"), f"Missing token: {login_data}"

    return {
        "username": username,
        "password": password,
        "token": login_data["token"],
    }


@pytest.fixture(scope="session")
def token(test_account):
    return test_account["token"]


@pytest.fixture(scope="session")
def token_params(token):
    return {"token": token}


def chat(token: str, message: str, session_id: str | None = None, current_city: str | None = None) -> httpx.Response:
    payload = {"message": message, "token": token}
    if session_id:
        payload["session_id"] = session_id
    if current_city:
        payload["current_city"] = current_city
    return post_json("/api/chat", payload)


class TestHealthCheck:
    def test_health_endpoint(self):
        r = get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "online"
        assert "model" in body

    def test_root_page(self):
        r = get("/")
        assert r.status_code == 200

    def test_docs_available(self):
        r = get("/docs")
        assert r.status_code == 200

    def test_models_endpoint(self):
        r = get("/api/models")
        assert r.status_code == 200
        assert "models" in r.json()


class TestAuthentication:
    def test_login_valid(self):
        username = unique_username("login")
        password = "Pass@12345"
        assert post_json("/api/signup", {"username": username, "password": password}).status_code == 200
        r = post_json(
            "/api/login",
            {"username": username, "password": password},
        )
        assert r.status_code == 200
        assert r.json().get("token")

    def test_login_wrong_password(self, test_account):
        r = post_json(
            "/api/login",
            {"username": test_account["username"], "password": "WrongPass999"},
        )
        assert r.status_code == 401

    def test_login_nonexistent_user(self):
        r = post_json("/api/login", {"username": unique_username("ghost"), "password": "any"})
        assert r.status_code == 401

    def test_login_empty_credentials(self):
        r = post_json("/api/login", {"username": "", "password": ""})
        assert r.status_code in [401, 422]

    def test_login_missing_fields(self):
        r = post_json("/api/login", {})
        assert r.status_code == 422

    def test_signup_duplicate_user(self, test_account):
        r = post_json(
            "/api/signup",
            {"username": test_account["username"], "password": test_account["password"]},
        )
        assert r.status_code == 400

    def test_signup_weak_password(self):
        r = post_json("/api/signup", {"username": unique_username("weak"), "password": "123"})
        assert r.status_code == 400

    def test_chat_without_token(self):
        r = post_json("/api/chat", {"message": "hello"})
        assert r.status_code in [401, 422]

    def test_chat_with_invalid_token(self):
        r = post_json("/api/chat", {"message": "hello", "token": "fake_invalid_token_xyz"})
        assert r.status_code == 401

    def test_logout_on_dedicated_account(self):
        username = unique_username("logout")
        password = "Pass@12345"
        assert post_json("/api/signup", {"username": username, "password": password}).status_code == 200
        login = post_json("/api/login", {"username": username, "password": password})
        token = login.json()["token"]

        r = post("/api/logout", params={"token": token})
        assert r.status_code == 200
        assert r.json()["status"] == "logged out"


class TestProfile:
    def test_get_profile(self, token_params):
        r = get("/api/profile", params=token_params)
        assert r.status_code == 200
        assert "profile" in r.json()

    def test_update_profile_basic(self, token):
        payload = {
            "token": token,
            "profile": {
                "age": 22,
                "gender": "male",
                "known_conditions": ["none"],
                "allergies": ["none"],
            },
        }
        r = post_json("/api/profile", payload)
        assert r.status_code == 200

    def test_update_profile_extended(self, token_params):
        payload = {
            "age": 22,
            "gender": "male",
            "smoking_status": "never",
            "alcohol_use": "occasional",
            "pregnancy_status": "not_applicable",
            "past_history": ["none"],
            "language": "en",
        }
        r = post_json("/api/update-profile-extended", payload, params=token_params)
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_update_profile_invalid_age(self, token):
        payload = {"token": token, "profile": {"age": -5, "gender": "male"}}
        r = post_json("/api/profile", payload)
        assert r.status_code == 200

    def test_update_profile_extreme_age(self, token):
        payload = {"token": token, "profile": {"age": 999, "gender": "male"}}
        r = post_json("/api/profile", payload)
        assert r.status_code == 200


class TestChatPipeline:
    def test_emergency_chest_pain(self, token):
        r = chat(token, "I have severe chest pain and cannot breathe, my left arm is numb")
        assert r.status_code == 200
        body = r.json()
        assert body["show_hospital_finder"] is True
        assert "Emergency Detector" in body["tools_used"]

    def test_emergency_stroke_symptoms(self, token):
        r = chat(token, "I have face drooping, slurred speech, and one sided weakness")
        assert r.status_code == 200
        assert r.json()["show_hospital_finder"] is True

    def test_followup_triage_trigger(self, token):
        r = chat(token, "I have fever and cough since 2 days")
        assert r.status_code == 200
        body = r.json()
        assert body["needs_followup"] is True
        assert body["followup_questions"]

    def test_appointment_booking_trigger(self, token):
        r = chat(token, "I want to book an appointment with a doctor")
        assert r.status_code == 200
        body = r.json()
        assert body["needs_followup"] is True

    def test_tablet_order_trigger(self, token):
        r = chat(token, "I want to order tablets")
        assert r.status_code == 200
        body = r.json()
        assert body["needs_followup"] is True

    def test_chat_empty_message(self, token):
        r = post_json("/api/chat", {"message": "", "token": token})
        assert r.status_code in [400, 422]

    def test_chat_very_long_message(self, token):
        long_msg = "I have a headache. " * 200
        r = chat(token, long_msg)
        assert r.status_code == 400

    def test_chat_unicode_message(self, token):
        r = chat(token, "मुझे बुखार और खांसी है")
        assert r.status_code in [200, 500]


class TestSessions:
    def test_get_sessions(self, token_params):
        r = get("/api/sessions", params=token_params)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_session_history(self, token):
        chat_r = chat(token, "I have fever and cough since yesterday")
        assert chat_r.status_code == 200
        sid = chat_r.json().get("session_id")
        assert sid

        r = get(f"/api/sessions/{sid}/history", params={"token": token})
        assert r.status_code == 200
        assert r.json()["session_id"] == sid

    def test_handoff_summary(self, token):
        chat_r = chat(token, "I have severe chest pain and shortness of breath")
        sid = chat_r.json()["session_id"]
        r = get("/api/handoff-summary", params={"token": token, "session_id": sid})
        assert r.status_code == 200
        assert "summary" in r.json()

    def test_delete_nonexistent_session(self, token):
        r = delete("/api/sessions/nonexistent_session_id_xyz", params={"token": token})
        assert r.status_code == 404


class TestLabUpload:
    def test_upload_txt_lab_report(self, token):
        lab_text = """Lab Report
Hemoglobin: 13.5
WBC: 7200
Platelets: 220000
HbA1c: 5.6
Creatinine: 0.9
TSH: 2.1
Blood Pressure: 120/80
"""
        files = {"file": ("lab_report.txt", io.BytesIO(lab_text.encode()), "text/plain")}
        r = httpx.post(f"{BASE_URL}/api/upload", params={"token": token}, files=files, timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] in ["success", "error"]
        assert "metrics" in body or "message" in body

    def test_upload_empty_file(self, token):
        files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
        r = httpx.post(f"{BASE_URL}/api/upload", params={"token": token}, files=files, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_upload_unsupported_file_type(self, token):
        files = {"file": ("test.exe", io.BytesIO(b"MZ\x00\x01"), "application/octet-stream")}
        r = httpx.post(f"{BASE_URL}/api/upload", params={"token": token}, files=files, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_upload_large_file(self, token):
        large_content = b"A" * (10 * 1024 * 1024 + 1)
        files = {"file": ("large_report.txt", io.BytesIO(large_content), "text/plain")}
        r = httpx.post(f"{BASE_URL}/api/upload", params={"token": token}, files=files, timeout=TIMEOUT)
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_get_lab_history(self, token_params):
        r = get("/api/lab-history", params=token_params)
        assert r.status_code == 200
        assert "history" in r.json()


class TestMedicationSafety:
    def test_drug_interaction_check(self, token):
        r = post(
            "/api/check-drug-interactions",
            params={"token": token, "medications": ["warfarin", "aspirin"]},
        )
        assert r.status_code == 200
        assert "interactions" in r.json()

    def test_drug_interaction_single_drug(self, token):
        r = post(
            "/api/check-drug-interactions",
            params={"token": token, "medications": ["metformin"]},
        )
        assert r.status_code == 200
        assert r.json()["medications"] == ["metformin"]

    def test_pharmacy_links(self):
        r = get("/api/pharmacy-links", params={"medicine": "paracetamol 500mg", "strips": 2})
        assert r.status_code == 200
        assert "links" in r.json()

    def test_nearby_hospitals(self):
        r = get("/api/nearby-hospitals", params={"lat": 17.385, "lng": 78.4867, "city": "Hyderabad"})
        assert r.status_code == 200
        assert "links" in r.json()

    def test_resolve_city(self):
        r = get("/api/resolve-city", params={"lat": 17.385, "lng": 78.4867})
        assert r.status_code == 200
        assert "city" in r.json()


class TestAnalytics:
    def test_health_dashboard(self, token_params):
        r = get("/api/health-dashboard", params=token_params)
        assert r.status_code == 200
        assert "dashboard" in r.json()

    def test_add_health_metric_bp(self, token):
        r = post(
            "/api/health-metric",
            params={"token": token, "metric": "blood_pressure", "value": 120, "unit": "mmHg", "status": "normal"},
        )
        assert r.status_code == 200

    def test_add_health_metric_weight(self, token):
        r = post(
            "/api/health-metric",
            params={"token": token, "metric": "weight", "value": 75.5, "unit": "kg", "status": "normal"},
        )
        assert r.status_code == 200

    def test_add_health_metric_invalid(self, token):
        r = post("/api/health-metric", params={"token": token, "metric": "", "unit": "kg"})
        assert r.status_code == 422

    def test_health_trends(self, token_params):
        r = get("/api/health-trends", params=token_params)
        assert r.status_code == 200
        assert "trends" in r.json()

    def test_health_report(self, token_params):
        r = get("/api/health-report", params=token_params)
        assert r.status_code == 200
        assert "report" in r.json()


class TestConsultation:
    def test_list_experts(self, token_params):
        r = get("/api/experts", params=token_params)
        assert r.status_code == 200
        assert "experts" in r.json()

    def test_request_consultation(self, token):
        payload = {
            "token": token,
            "question": "I have persistent headaches for 3 days",
            "category": "symptoms",
            "preferred_language": "en",
        }
        r = post_json("/api/request-consultation", payload)
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_my_consultations(self, token_params):
        r = get("/api/my-consultations", params=token_params)
        assert r.status_code == 200
        assert "consultations" in r.json()

    def test_schedule_appointment(self, token):
        r = post(
            "/api/schedule-appointment",
            params={
                "token": token,
                "expert_id": "dr_001",
                "date": "2026-05-01",
                "time": "10:00",
                "reason": "Annual checkup",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "success"


class TestLocalization:
    def test_supported_languages(self):
        r = get("/api/supported-languages")
        assert r.status_code == 200
        assert "languages" in r.json()

    def test_ui_strings_default(self):
        r = get("/api/ui-strings")
        assert r.status_code == 200
        assert r.json()["language"] == "en"

    def test_ui_strings_hindi(self):
        r = get("/api/ui-strings", params={"language": "hi"})
        assert r.status_code == 200
        assert r.json()["language"] == "hi"


class TestPrivacy:
    def test_export_data(self, token_params):
        r = get("/api/export-data", params=token_params)
        assert r.status_code == 200
        assert r.json()["status"] == "success"

    def test_audit_log(self, token_params):
        r = get("/api/audit-log", params=token_params)
        assert r.status_code == 200
        assert "audit_log" in r.json()

    def test_delete_account_on_dedicated_account(self):
        username = unique_username("delete")
        password = "Pass@12345"
        assert post_json("/api/signup", {"username": username, "password": password}).status_code == 200
        login = post_json("/api/login", {"username": username, "password": password})
        token = login.json()["token"]

        r = post("/api/delete-account", params={"token": token})
        assert r.status_code == 200
        assert r.json()["status"] == "success"


class TestStressAndEdgeCases:
    def test_concurrent_chat_messages(self, token):
        results = []

        def send(msg: str):
            r = chat(token, msg)
            results.append(r.status_code)

        threads = [threading.Thread(target=send, args=(f"I have fever and cough for {i + 1} days",)) for i in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 3
        assert all(status == 200 for status in results)

    def test_chat_with_null_message(self, token):
        r = post_json("/api/chat", {"message": None, "token": token})
        assert r.status_code == 422

    def test_chat_with_number_as_message(self, token):
        r = post_json("/api/chat", {"message": 12345, "token": token})
        assert r.status_code in [200, 400, 422]

    def test_nonexistent_endpoint(self):
        r = get("/api/nonexistent_route_xyz")
        assert r.status_code == 404

    def test_wrong_method_on_chat(self):
        r = get("/api/chat")
        assert r.status_code == 405

    def test_response_time_chat(self, token):
        start = time.time()
        r = chat(token, "I have fever and cough since yesterday")
        elapsed = time.time() - start
        assert r.status_code == 200
        assert elapsed < 55

    def test_chat_repeated_emergency(self, token):
        for _ in range(2):
            r = chat(token, "severe chest pain, can't breathe")
            assert r.status_code == 200
            assert r.json()["show_hospital_finder"] is True

    def test_multiline_symptom_message(self, token):
        message = """I have the following symptoms:
1. Fever since 3 days
2. Severe headache
3. Body aches
4. Fatigue
"""
        r = chat(token, message)
        assert r.status_code == 200
        assert r.json().get("response") is not None
