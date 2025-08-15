import requests
import json

def test_single_transaction(description, amount, expected_amount):
    """Test a single transaction to debug parsing"""
    print(f"\n🔍 Testing: {description} with amount '{amount}' (expecting {expected_amount})")
    
    csv_content = f"""description,amount,date
{description},{amount},2024-01-15"""
    
    url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com/api/upload/csv"
    files = {'file': ('debug_test.csv', csv_content, 'text/csv')}
    
    try:
        response = requests.post(url, files=files)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            imported = result.get('imported', 0)
            total_rows = result.get('total_rows', 0)
            errors = result.get('errors', [])
            
            print(f"Imported: {imported}/{total_rows}")
            if errors:
                print(f"Errors: {errors}")
            
            if imported == 1:
                print("✅ Successfully imported")
                
                # Get the imported expense to check the amount
                expenses_response = requests.get("https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com/api/expenses")
                if expenses_response.status_code == 200:
                    expenses = expenses_response.json()
                    # Find our test expense (should be the most recent)
                    for expense in expenses[:5]:  # Check first 5 expenses
                        if description.split()[0] in expense.get('title', '').upper():
                            actual_amount = expense.get('amount', 0)
                            print(f"Actual imported amount: ₺{actual_amount}")
                            if abs(actual_amount - expected_amount) < 0.01:
                                print("✅ Amount parsed correctly!")
                            else:
                                print(f"❌ Amount parsing error: expected ₺{expected_amount}, got ₺{actual_amount}")
                            break
            else:
                print("❌ Failed to import")
                
        else:
            print(f"❌ Request failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")

def main():
    print("🔍 DEBUGGING TURKISH NUMBER FORMAT PARSING")
    print("="*50)
    
    # Test cases that were failing
    test_cases = [
        ("METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46", "1.544,14", 1544.14),
        ("CARREFOUR ATASEHIR ISTANBUL TR KAZANILAN MAXIMIL:2,15", "1,544.14", 1544.14),
        ("SIMPLE MERCHANT ISTANBUL TR", "234,50", 234.50),
        ("ANOTHER MERCHANT ISTANBUL TR", "1,544", 1544.0),
        ("TEST MERCHANT ISTANBUL TR", "234", 234.0),
    ]
    
    for description, amount_str, expected_amount in test_cases:
        test_single_transaction(description, amount_str, expected_amount)
    
    print("\n" + "="*50)
    print("🔍 Debug testing complete")

if __name__ == "__main__":
    main()