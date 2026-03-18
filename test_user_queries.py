#!/usr/bin/env python3
"""
Test Real User Queries Against Running API
Tests different pipeline layers with actual messages
"""

import requests
import json
import asyncio
from datetime import datetime

API_BASE = "http://localhost:8000"
TEST_TOKEN = None  # Will be obtained from signup/login
TEST_USER = "testuser"
TEST_PASSWORD = "password123"

# Sample queries for different pipeline layers
TEST_QUERIES = {
    "Emergency": {
        "messages": [
            "I am having a heart attack",
            "chest pain and can't breathe",
            "I want to kill myself",
        ],
        "expected_tool": "Emergency Detector",
        "description": "Layer 1: Emergency Detection"
    },
    "Symptom": {
        "messages": [
            "I have fever, cough, and body pain",
            "I am feeling dizzy with nausea and vomiting",
            "headache and fatigue for 3 days",
        ],
        "expected_tool": "Symptom Predictor",
        "description": "Layer 3: Symptom Prediction"
    },
    "Medical Knowledge": {
        "messages": [
            "What is diabetes?",
            "Tell me about hypertension",
            "What causes migraine?",
        ],
        "expected_tool": "Medical KG",
        "description": "Layer 4: Knowledge Graph Lookup"
    },
    "General": {
        "messages": [
            "Hello, how can you help me?",
            "What is 2+2?",
            "Tell me about your features",
        ],
        "expected_tool": None,  # Any tool or no tool
        "description": "Layer 6: AI Agent Fallback"
    }
}

def test_health_check():
    """Check if API is running"""
    try:
        res = requests.get(f"{API_BASE}/api/health", timeout=5)
        if res.status_code == 200:
            data = res.json()
            print(f"✅ API Health Check PASSED")
            print(f"   Status: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"❌ API Health Check FAILED: {res.status_code}")
            return False
    except Exception as e:
        print(f"❌ API unreachable: {e}")
        return False

def authenticate():
    """Login or signup to get a valid token"""
    global TEST_TOKEN
    try:
        # Try login
        print("\n📝 Authenticating...")
        res = requests.post(
            f"{API_BASE}/api/login",
            json={
                "username": TEST_USER,
                "password": TEST_PASSWORD,
                "age": 30,
                "known_conditions": []
            },
            timeout=10
        )
        
        if res.status_code == 200:
            TEST_TOKEN = res.json().get("token")
            print(f"✅ Login successful - Token: {TEST_TOKEN[:20]}...")
            return True
        
        # If login fails, try signup
        print(f"⚠️  Login failed, attempting signup...")
        res = requests.post(
            f"{API_BASE}/api/signup",
            json={
                "username": TEST_USER,
                "password": TEST_PASSWORD
            },
            timeout=10
        )
        
        if res.status_code == 200:
            print(f"✅ Signup successful")
            # Try login again
            res = requests.post(
                f"{API_BASE}/api/login",
                json={
                    "username": TEST_USER,
                    "password": TEST_PASSWORD,
                    "age": 30,
                    "known_conditions": []
                },
                timeout=10
            )
            if res.status_code == 200:
                TEST_TOKEN = res.json().get("token")
                print(f"✅ Login successful - Token: {TEST_TOKEN[:20]}...")
                return True
        
        print(f"❌ Authentication failed")
        return False
        
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return False

def test_chat_query(message, expected_tool=None, layer_name=""):
    """Test a single chat query"""
    try:
        payload = {
            "message": message,
            "token": TEST_TOKEN,
            "model": "gemini-2.5-flash-lite",
            "session_id": None
        }
        
        res = requests.post(f"{API_BASE}/api/chat", json=payload, timeout=30)
        
        if res.status_code != 200:
            print(f"   ❌ Query failed: {res.status_code}")
            print(f"      Response: {res.text[:200]}")
            return False
        
        data = res.json()
        
        # Validate response structure
        required_fields = ["response", "session_id", "tools_used", "timestamp"]
        missing_fields = [f for f in required_fields if f not in data]
        
        if missing_fields:
            print(f"   ❌ Missing fields: {missing_fields}")
            return False
        
        # Check expected tool
        tools = data.get("tools_used", [])
        if expected_tool and expected_tool not in tools:
            status = f"⚠️  Expected tool '{expected_tool}' not in {tools}"
        else:
            status = f"✅ Tools used: {tools if tools else '[None]'}"
        
        print(f"   {status}")
        print(f"      Message: {message[:60]}...")
        print(f"      Response: {data.get('response', '')[:100]}...")
        print()
        
        return True
        
    except requests.exceptions.Timeout:
        print(f"   ❌ Request timeout")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    print("=" * 80)
    print("TESTING USER QUERIES AGAINST RUNNING API")
    print("=" * 80)
    print()
    
    # Check API health
    print("1. Health Check")
    print("-" * 80)
    if not test_health_check():
        print("\n⚠️  API is not running. Start it with: uvicorn app:app --reload")
        return
    print()
    
    # Authenticate
    print("\n2. Authentication")
    print("-" * 80)
    if not authenticate():
        print("\n⚠️  Could not authenticate. Check username/password.")
        return
    print()
    
    # Test each layer
    print("\n3. Pipeline Layer Tests")
    print("-" * 80)
    
    passed = 0
    failed = 0
    
    for layer, config in TEST_QUERIES.items():
        print(f"\n{config['description']} ({layer})")
        print("-" * 40)
        
        for msg in config['messages']:
            if test_chat_query(msg, config['expected_tool'], layer):
                passed += 1
            else:
                failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    total = passed + failed
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {failed}/{total}")
    print(f"Success Rate: {(passed/total*100):.1f}%" if total > 0 else "No tests run")
    print()
    
    # Recommendations
    if failed == 0 and passed > 0:
        print("🎉 All user queries validated successfully!")
    else:
        print("⚠️  Some queries failed. Check the API logs for details.")

if __name__ == "__main__":
    main()
