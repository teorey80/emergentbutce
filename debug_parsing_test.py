import requests
import json

def test_specific_parsing():
    """Debug specific parsing issues"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🔍 DEBUGGING TURKISH BANK PARSING ISSUES...")
    
    # Test 1: Simple case that should definitely work
    print("\n1. Testing simple case...")
    csv_content = """description,amount,date
SIMPLE MERCHANT,100.00,25.02.2024"""
    
    files = {'file': ('simple_test.csv', csv_content, 'text/csv')}
    response = requests.post(f"{api_url}/upload/csv", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Simple test: {result['imported']} imported from {result['total_rows']} rows")
        print(f"   Detected columns: {result.get('detected_columns', 'N/A')}")
        if result['imported'] == 0:
            print(f"   Errors: {result.get('errors', [])}")
    else:
        print(f"❌ Simple test failed: {response.status_code}")
        print(f"   Response: {response.text}")
    
    # Test 2: Turkish bank format with large amount
    print("\n2. Testing Turkish bank format with large amount...")
    csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR,1544.14,25.02.2024"""
    
    files = {'file': ('turkish_large.csv', csv_content, 'text/csv')}
    response = requests.post(f"{api_url}/upload/csv", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Turkish large amount: {result['imported']} imported from {result['total_rows']} rows")
        if result['imported'] == 0:
            print(f"   Errors: {result.get('errors', [])}")
    else:
        print(f"❌ Turkish large amount failed: {response.status_code}")
    
    # Test 3: Check if the issue is with the negative sign
    print("\n3. Testing with negative sign...")
    csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR,1544.14-,25.02.2024"""
    
    files = {'file': ('turkish_negative.csv', csv_content, 'text/csv')}
    response = requests.post(f"{api_url}/upload/csv", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Turkish negative amount: {result['imported']} imported from {result['total_rows']} rows")
        if result['imported'] == 0:
            print(f"   Errors: {result.get('errors', [])}")
    else:
        print(f"❌ Turkish negative amount failed: {response.status_code}")
    
    # Test 4: Check if the issue is with the reward patterns
    print("\n4. Testing with reward patterns...")
    csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1544.14,25.02.2024"""
    
    files = {'file': ('turkish_rewards.csv', csv_content, 'text/csv')}
    response = requests.post(f"{api_url}/upload/csv", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Turkish with rewards: {result['imported']} imported from {result['total_rows']} rows")
        if result['imported'] == 0:
            print(f"   Errors: {result.get('errors', [])}")
    else:
        print(f"❌ Turkish with rewards failed: {response.status_code}")
    
    # Test 5: Check current expenses to see what's in the database
    print("\n5. Checking current expenses in database...")
    response = requests.get(f"{api_url}/expenses")
    if response.status_code == 200:
        expenses = response.json()
        print(f"✅ Current expenses in database: {len(expenses)}")
        
        # Show recent expenses
        recent_expenses = expenses[:5]  # First 5 (most recent)
        for i, expense in enumerate(recent_expenses):
            print(f"   {i+1}. {expense['title']} - ₺{expense['amount']} ({expense['category']})")
    else:
        print(f"❌ Failed to get expenses: {response.status_code}")

if __name__ == "__main__":
    test_specific_parsing()