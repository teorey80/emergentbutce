import requests
import json
import io

def test_critical_metro_case():
    """Test the exact critical case from the review request"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🚨 TESTING CRITICAL CASE: METRO UMRANIYE TEKEL with 1.544,14")
    print("Expected: Should import as ₺1544.14 expense (NOT be filtered as points)")
    
    # The exact failing case from the review request
    csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1.544,14,2024-01-15"""
    
    files = {'file': ('critical_metro_test.csv', csv_content, 'text/csv')}
    
    try:
        # Upload the CSV
        response = requests.post(f"{api_url}/upload/csv", files=files)
        print(f"Upload Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"📊 Results:")
            print(f"   Total rows: {result.get('total_rows', 0)}")
            print(f"   Imported: {result.get('imported', 0)}")
            print(f"   Errors: {len(result.get('errors', []))}")
            
            if result.get('errors'):
                print(f"   Error details: {result['errors']}")
            
            if result.get('imported', 0) == 1:
                print("✅ SUCCESS: Transaction was imported!")
                
                # Get recent expenses to verify the amount
                expenses_response = requests.get(f"{api_url}/expenses")
                if expenses_response.status_code == 200:
                    expenses = expenses_response.json()
                    
                    # Find the METRO transaction
                    metro_expense = None
                    for expense in expenses:
                        if 'METRO' in expense.get('title', '').upper():
                            metro_expense = expense
                            break
                    
                    if metro_expense:
                        amount = metro_expense.get('amount', 0)
                        title = metro_expense.get('title', '')
                        print(f"✅ Found METRO transaction:")
                        print(f"   Title: {title}")
                        print(f"   Amount: ₺{amount}")
                        
                        # Check if amount is correct (1544.14)
                        if abs(amount - 1544.14) < 0.01:
                            print("✅ CRITICAL SUCCESS: Amount ₺1544.14 parsed correctly!")
                            return True
                        else:
                            print(f"❌ CRITICAL FAILURE: Expected ₺1544.14, got ₺{amount}")
                            return False
                    else:
                        print("❌ CRITICAL FAILURE: METRO transaction not found")
                        return False
                else:
                    print("❌ Could not retrieve expenses to verify")
                    return False
            else:
                print("❌ CRITICAL FAILURE: Transaction was filtered (not imported)")
                print("   This means the validation logic is still incorrectly filtering legitimate transactions")
                return False
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False

def test_points_filtering():
    """Test that small amounts are still correctly filtered"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("\n🎯 TESTING POINTS FILTERING: Small amounts should be filtered")
    
    # Test small amounts that should be filtered
    csv_content = """description,amount,date
KAZANILAN MAXIMIL:3,09,3,09,2024-01-15
MAXIPUAN REWARD,0,46,2024-01-15"""
    
    files = {'file': ('points_test.csv', csv_content, 'text/csv')}
    
    try:
        response = requests.post(f"{api_url}/upload/csv", files=files)
        
        if response.status_code == 200:
            result = response.json()
            imported = result.get('imported', 0)
            
            print(f"📊 Points filtering test:")
            print(f"   Total rows: {result.get('total_rows', 0)}")
            print(f"   Imported: {imported}")
            
            if imported == 0:
                print("✅ SUCCESS: Small amounts correctly filtered as points")
                return True
            else:
                print(f"❌ FAILURE: {imported} small amounts were imported (should be 0)")
                return False
        else:
            print(f"❌ Upload failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        return False

def test_number_formats():
    """Test various Turkish number formats"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("\n🔢 TESTING TURKISH NUMBER FORMATS")
    
    test_cases = [
        ("1.544,14", 1544.14, "Turkish thousands+decimal"),
        ("1,544.14", 1544.14, "US thousands+decimal"),
        ("234,50", 234.50, "Turkish decimal only"),
        ("1,544", 1544.0, "Thousands only")
    ]
    
    results = []
    
    for amount_str, expected, description in test_cases:
        print(f"\n   Testing {description}: {amount_str}")
        
        csv_content = f"""description,amount,date
TEST TRANSACTION,{amount_str},2024-01-15"""
        
        files = {'file': (f'format_test_{amount_str.replace(".", "_").replace(",", "_")}.csv', csv_content, 'text/csv')}
        
        try:
            response = requests.post(f"{api_url}/upload/csv", files=files)
            
            if response.status_code == 200:
                result = response.json()
                imported = result.get('imported', 0)
                
                if imported == 1:
                    # Get the imported expense to check amount
                    expenses_response = requests.get(f"{api_url}/expenses")
                    if expenses_response.status_code == 200:
                        expenses = expenses_response.json()
                        if expenses:
                            actual_amount = expenses[0].get('amount', 0)
                            if abs(actual_amount - expected) < 0.01:
                                print(f"   ✅ SUCCESS: {amount_str} → ₺{actual_amount}")
                                results.append(True)
                            else:
                                print(f"   ❌ FAILURE: {amount_str} → ₺{actual_amount} (expected ₺{expected})")
                                results.append(False)
                        else:
                            print(f"   ❌ FAILURE: No expenses found")
                            results.append(False)
                    else:
                        print(f"   ❌ FAILURE: Could not retrieve expenses")
                        results.append(False)
                else:
                    print(f"   ❌ FAILURE: {amount_str} not imported")
                    results.append(False)
            else:
                print(f"   ❌ FAILURE: Upload failed ({response.status_code})")
                results.append(False)
                
        except Exception as e:
            print(f"   ❌ FAILURE: Error {str(e)}")
            results.append(False)
    
    success_rate = sum(results) / len(results) * 100 if results else 0
    print(f"\n📊 Number format parsing success rate: {success_rate:.1f}% ({sum(results)}/{len(results)})")
    
    return success_rate >= 75  # At least 75% should work

def main():
    print("="*80)
    print("🚨 FOCUSED CRITICAL TEST: Turkish Bank Statement Parsing Fix")
    print("="*80)
    
    # Test the critical case
    critical_success = test_critical_metro_case()
    
    # Test points filtering
    points_success = test_points_filtering()
    
    # Test number formats
    formats_success = test_number_formats()
    
    print("\n" + "="*80)
    print("📊 FINAL RESULTS")
    print("="*80)
    
    print(f"Critical Case (METRO 1.544,14): {'✅ PASS' if critical_success else '❌ FAIL'}")
    print(f"Points Filtering: {'✅ PASS' if points_success else '❌ FAIL'}")
    print(f"Number Format Parsing: {'✅ PASS' if formats_success else '❌ FAIL'}")
    
    overall_success = critical_success and points_success and formats_success
    
    print(f"\nOVERALL VERDICT: {'✅ FIX SUCCESSFUL' if overall_success else '❌ FIX INCOMPLETE'}")
    
    if not overall_success:
        print("\n🚨 ISSUES FOUND:")
        if not critical_success:
            print("   - Critical METRO transaction case still failing")
        if not points_success:
            print("   - Points filtering not working correctly")
        if not formats_success:
            print("   - Turkish number format parsing has issues")
    
    print("="*80)
    
    return 0 if overall_success else 1

if __name__ == "__main__":
    exit(main())