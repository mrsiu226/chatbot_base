#!/usr/bin/env python3
"""
Script để test tất cả models có hoạt động không
"""

from model import models

def test_model(model_name):
    """Test một model cụ thể"""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print('='*60)
    
    try:
        model = models[model_name]
        result = model.invoke("Hello! What's 2+2?")
        
        if hasattr(result, 'content'):
            response = result.content
        else:
            response = str(result)
        
        # Check if it's an error message
        if "error" in response.lower() or "timeout" in response.lower():
            print(f"❌ FAILED: {response[:100]}")
            return False
        else:
            print(f"✅ SUCCESS")
            print(f"Response: {response[:100]}...")
            return True
            
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False

def main():
    print("="*60)
    print("MODEL TESTING SUITE")
    print("="*60)
    print(f"\nAvailable models: {list(models.keys())}")
    
    results = {}
    for model_name in models.keys():
        success = test_model(model_name)
        results[model_name] = "✅ PASS" if success else "❌ FAIL"
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for model_name, status in results.items():
        print(f"{model_name:30} {status}")
    
    # Count
    passed = sum(1 for v in results.values() if "PASS" in v)
    total = len(results)
    print(f"\nTotal: {passed}/{total} models passed")

if __name__ == "__main__":
    main()
