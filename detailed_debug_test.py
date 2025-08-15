import requests
import json

def test_metro_case_detailed():
    """Test the METRO case with detailed debugging"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🚨 DETAILED DEBUG: METRO UMRANIYE TEKEL case")
    
    # Get initial expense count
    initial_response = requests.get(f"{api_url}/expenses")
    initial_count = len(initial_response.json()) if initial_response.status_code == 200 else 0
    print(f"Initial expense count: {initial_count}")
    
    # Test the critical case with proper CSV formatting
    csv_content = """description,amount,date
"METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46","1.544,14",2024-01-15"""
    
    files = {'file': ('metro_debug.csv', csv_content, 'text/csv')}
    
    print(f"CSV Content being sent:")
    print(csv_content)
    print()
    
    # Upload the CSV
    response = requests.post(f"{api_url}/upload/csv", files=files)
    print(f"Upload response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Upload result:")
        print(json.dumps(result, indent=2))
        
        # Get expenses after upload
        after_response = requests.get(f"{api_url}/expenses")
        after_count = len(after_response.json()) if after_response.status_code == 200 else 0
        print(f"After expense count: {after_count}")
        print(f"Net change: {after_count - initial_count}")
        
        if after_count > initial_count:
            print("✅ New expense(s) were added!")
            expenses = after_response.json()
            for expense in expenses[:3]:  # Show first 3
                print(f"  - {expense.get('title', 'N/A')}: ₺{expense.get('amount', 0)}")
        else:
            print("❌ No new expenses were added")
            
        # Check for errors
        if result.get('errors'):
            print(f"Errors reported:")
            for error in result['errors']:
                print(f"  - {error}")
    else:
        print(f"❌ Upload failed: {response.text}")

def test_simple_case():
    """Test a simple case without MAXIMIL/MAXIPUAN"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("\n🔍 CONTROL TEST: Simple case without reward patterns")
    
    # Get initial expense count
    initial_response = requests.get(f"{api_url}/expenses")
    initial_count = len(initial_response.json()) if initial_response.status_code == 200 else 0
    print(f"Initial expense count: {initial_count}")
    
    # Test a simple case
    csv_content = """description,amount,date
"METRO UMRANIYE TEKEL ISTANBUL TR","1.544,14",2024-01-15"""
    
    files = {'file': ('simple_debug.csv', csv_content, 'text/csv')}
    
    print(f"CSV Content being sent:")
    print(csv_content)
    print()
    
    # Upload the CSV
    response = requests.post(f"{api_url}/upload/csv", files=files)
    print(f"Upload response status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Upload result:")
        print(json.dumps(result, indent=2))
        
        # Get expenses after upload
        after_response = requests.get(f"{api_url}/expenses")
        after_count = len(after_response.json()) if after_response.status_code == 200 else 0
        print(f"After expense count: {after_count}")
        print(f"Net change: {after_count - initial_count}")
        
        if after_count > initial_count:
            print("✅ New expense(s) were added!")
            expenses = after_response.json()
            for expense in expenses[:3]:  # Show first 3
                print(f"  - {expense.get('title', 'N/A')}: ₺{expense.get('amount', 0)}")
        else:
            print("❌ No new expenses were added")

if __name__ == "__main__":
    test_metro_case_detailed()
    test_simple_case()