"""
Test script for JWT Authentication API
This script tests the JWT-based authentication for the chatbot API
"""
import requests
import json
import time

# API Configuration
BASE_URL = "http://localhost:5000"
LOGIN_ENDPOINT = f"{BASE_URL}/api/login"
CHAT_ENDPOINT = f"{BASE_URL}/v1/chat"

# Test credentials (make sure these exist in your database)
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

def test_login():
    """Test login endpoint and get JWT token"""
    print("🔐 Testing login endpoint...")
    
    login_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    try:
        response = requests.post(LOGIN_ENDPOINT, json=login_data)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print("✅ Login successful!")
                print(f"   Token type: {data.get('token_type')}")
                print(f"   User ID: {data.get('user', {}).get('id')}")
                print(f"   Email: {data.get('user', {}).get('email')}")
                return data.get("access_token")
            else:
                print("❌ Login failed:", data.get("error"))
                return None
        else:
            print(f"❌ Login failed with status {response.status_code}")
            print("Response:", response.text)
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during login: {e}")
        return None

def test_chat_with_token(token):
    """Test chat endpoint with JWT token"""
    print("\n💬 Testing chat endpoint with JWT token...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    chat_data = {
        "message": "Hello, this is a test message for JWT authentication",
        "model": "gemini-flash-lite"
    }
    
    try:
        response = requests.post(
            CHAT_ENDPOINT, 
            json=chat_data, 
            headers=headers,
            stream=True,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Chat API responding with stream...")
            print("📄 Response content:")
            
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data: '):
                        data = decoded_line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            print("\n✅ Stream completed successfully!")
                            break
                        else:
                            try:
                                content = json.loads(data)
                                if 'content' in content:
                                    print(content['content'], end='', flush=True)
                                elif 'error' in content:
                                    print(f"\n❌ Error in stream: {content['error']}")
                                    break
                            except json.JSONDecodeError:
                                print(f"\n⚠️  Invalid JSON in stream: {data}")
            return True
            
        else:
            print(f"❌ Chat API failed with status {response.status_code}")
            print("Response:", response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during chat: {e}")
        return False

def test_chat_without_token():
    """Test chat endpoint without token (should fail)"""
    print("\n🚫 Testing chat endpoint without token (should fail)...")
    
    chat_data = {
        "message": "This should fail",
        "model": "gemini-flash-lite"
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=chat_data)
        
        if response.status_code == 401:
            error_data = response.json()
            print("✅ Correctly rejected request without token")
            print(f"   Error: {error_data.get('error')}")
            return True
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print("Response:", response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

def test_chat_with_invalid_token():
    """Test chat endpoint with invalid token (should fail)"""
    print("\n🚫 Testing chat endpoint with invalid token (should fail)...")
    
    headers = {
        "Authorization": "Bearer invalid.token.here",
        "Content-Type": "application/json"
    }
    
    chat_data = {
        "message": "This should fail",
        "model": "gemini-flash-lite"
    }
    
    try:
        response = requests.post(CHAT_ENDPOINT, json=chat_data, headers=headers)
        
        if response.status_code == 401:
            error_data = response.json()
            print("✅ Correctly rejected invalid token")
            print(f"   Error: {error_data.get('error')}")
            return True
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print("Response:", response.text)
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting JWT Authentication API Tests")
    print("=" * 50)
    
    # Test 1: Login to get token
    token = test_login()
    if not token:
        print("\n❌ Cannot proceed without valid token")
        return False
    
    # Test 2: Chat with valid token
    chat_success = test_chat_with_token(token)
    
    # Test 3: Chat without token (should fail)
    no_token_test = test_chat_without_token()
    
    # Test 4: Chat with invalid token (should fail)
    invalid_token_test = test_chat_with_invalid_token()
    
    print("\n" + "=" * 50)
    print("📊 Test Summary:")
    print(f"   Login: {'✅ PASS' if token else '❌ FAIL'}")
    print(f"   Chat with token: {'✅ PASS' if chat_success else '❌ FAIL'}")
    print(f"   Chat without token: {'✅ PASS' if no_token_test else '❌ FAIL'}")
    print(f"   Chat with invalid token: {'✅ PASS' if invalid_token_test else '❌ FAIL'}")
    
    all_passed = all([token, chat_success, no_token_test, invalid_token_test])
    print(f"\n🎯 Overall result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
    
    return all_passed

if __name__ == "__main__":
    print("⚠️  Before running this test:")
    print(f"   1. Make sure the server is running on {BASE_URL}")
    print(f"   2. Create a test user with email: {TEST_EMAIL}")
    print(f"   3. Set password: {TEST_PASSWORD}")
    print(f"   4. Install PyJWT: pip install PyJWT")
    print()
    
    input("Press Enter to continue...")
    main()