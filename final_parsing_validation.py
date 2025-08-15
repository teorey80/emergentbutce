import requests
import json

def validate_parsing_accuracy():
    """Final validation of Turkish bank parsing accuracy"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🎯 FINAL VALIDATION OF TURKISH BANK PARSING ACCURACY")
    print("="*60)
    
    # Test cases that should work vs should be filtered
    should_import = [
        ("Simple amount", "METRO UMRANIYE TEKEL", "100.00"),
        ("Turkish decimal", "MIGROS ATASEHIR", "125,50"),
        ("Large amount", "CARREFOUR ISTANBUL", "1544,14"),
        ("Without rewards", "SHELL BENZIN", "450.75"),
    ]
    
    should_filter = [
        ("Small points", "MAXIMIL PUAN KAZANIMI", "3.09"),
        ("Tiny points", "MAXIPUAN BONUS", "0.46"),
        ("Very small", "WORLDPUAN KAZANIMI", "1.50"),
    ]
    
    should_import_but_failing = [
        ("US format with rewards", "METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46", "1544.14"),
        ("Turkish format with rewards", "MIGROS ATASEHIR ISTANBUL TR KAZANILAN MAXIMIL:1,25 MAXIPUAN:0,18", "125,50"),
        ("German format with rewards", "STARBUCKS KADIKOY ISTANBUL TR IPTAL EDILEN MAXIMIL:2,50", "1.544,14"),
    ]
    
    print("\n✅ TESTING CASES THAT SHOULD IMPORT:")
    import_success = 0
    for name, description, amount in should_import:
        csv_content = f"""description,amount,date
{description},{amount},25.02.2024"""
        
        files = {'file': (f'should_import_{name.replace(" ", "_")}.csv', csv_content, 'text/csv')}
        response = requests.post(f"{api_url}/upload/csv", files=files)
        
        if response.status_code == 200:
            result = response.json()
            if result['imported'] > 0:
                print(f"   ✅ {name}: IMPORTED ({amount})")
                import_success += 1
            else:
                print(f"   ❌ {name}: FILTERED ({amount})")
        else:
            print(f"   ❌ {name}: ERROR ({response.status_code})")
    
    print(f"\n   Import Success Rate: {import_success}/{len(should_import)} ({import_success/len(should_import)*100:.1f}%)")
    
    print("\n✅ TESTING CASES THAT SHOULD BE FILTERED:")
    filter_success = 0
    for name, description, amount in should_filter:
        csv_content = f"""description,amount,date
{description},{amount},25.02.2024"""
        
        files = {'file': (f'should_filter_{name.replace(" ", "_")}.csv', csv_content, 'text/csv')}
        response = requests.post(f"{api_url}/upload/csv", files=files)
        
        if response.status_code == 200:
            result = response.json()
            if result['imported'] == 0:
                print(f"   ✅ {name}: CORRECTLY FILTERED ({amount})")
                filter_success += 1
            else:
                print(f"   ❌ {name}: INCORRECTLY IMPORTED ({amount})")
        else:
            print(f"   ❌ {name}: ERROR ({response.status_code})")
    
    print(f"\n   Filter Success Rate: {filter_success}/{len(should_filter)} ({filter_success/len(should_filter)*100:.1f}%)")
    
    print("\n❌ TESTING CASES THAT SHOULD IMPORT BUT ARE CURRENTLY FAILING:")
    failing_cases = 0
    for name, description, amount in should_import_but_failing:
        csv_content = f"""description,amount,date
{description},{amount},25.02.2024"""
        
        files = {'file': (f'failing_{name.replace(" ", "_")}.csv', csv_content, 'text/csv')}
        response = requests.post(f"{api_url}/upload/csv", files=files)
        
        if response.status_code == 200:
            result = response.json()
            if result['imported'] > 0:
                print(f"   ✅ {name}: FIXED - NOW IMPORTING ({amount})")
            else:
                print(f"   ❌ {name}: STILL FAILING ({amount})")
                failing_cases += 1
        else:
            print(f"   ❌ {name}: ERROR ({response.status_code})")
    
    print(f"\n   Critical Issues: {failing_cases}/{len(should_import_but_failing)} cases still failing")
    
    # Overall assessment
    total_expected_working = len(should_import) + len(should_filter)
    total_working = import_success + filter_success
    overall_accuracy = (total_working / total_expected_working) * 100
    
    print(f"\n🎯 OVERALL PARSING ACCURACY:")
    print(f"   Working correctly: {total_working}/{total_expected_working} ({overall_accuracy:.1f}%)")
    print(f"   Critical failures: {failing_cases} major cases not working")
    
    if failing_cases > 0:
        print(f"\n⚠️ CRITICAL ISSUE IDENTIFIED:")
        print(f"   Turkish bank statements with reward patterns are being incorrectly filtered")
        print(f"   This affects real-world İş Bankası credit card statement imports")
        print(f"   Root cause: Amount parsing logic error in server.py line 676")
    
    return overall_accuracy, failing_cases

if __name__ == "__main__":
    accuracy, failures = validate_parsing_accuracy()
    if failures > 0:
        print(f"\n🚨 TESTING RESULT: CRITICAL ISSUES FOUND")
        exit(1)
    else:
        print(f"\n✅ TESTING RESULT: ALL SYSTEMS WORKING")
        exit(0)