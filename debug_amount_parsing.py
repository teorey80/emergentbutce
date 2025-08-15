import requests
import json

def test_amount_parsing_debug():
    """Debug the specific amount parsing issue"""
    base_url = "https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"
    api_url = f"{base_url}/api"
    
    print("🔍 DEBUGGING AMOUNT PARSING WITH MAXIMIL PATTERNS...")
    
    # Test different amount formats with MAXIMIL patterns
    test_cases = [
        ("1544.14", "METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46"),
        ("1544,14", "METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46"),
        ("1.544,14", "METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46"),
        ("1,544.14", "METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46"),
        ("125.50", "MIGROS ATASEHIR ISTANBUL TR KAZANILAN MAXIMIL:1,25 MAXIPUAN:0,18"),
        ("3.09", "MAXIMIL PUAN KAZANIMI"),  # This should be filtered
        ("0.46", "MAXIPUAN BONUS KAZANIMI"),  # This should be filtered
    ]
    
    for amount, description in test_cases:
        print(f"\n🧪 Testing: Amount='{amount}', Description='{description[:50]}...'")
        
        csv_content = f"""description,amount,date
{description},{amount},25.02.2024"""
        
        files = {'file': (f'test_{amount.replace(".", "_").replace(",", "_")}.csv', csv_content, 'text/csv')}
        response = requests.post(f"{api_url}/upload/csv", files=files)
        
        if response.status_code == 200:
            result = response.json()
            imported = result['imported']
            total = result['total_rows']
            
            if imported > 0:
                print(f"✅ SUCCESS: {imported}/{total} imported")
                if 'auto_categorization' in result and result['auto_categorization']:
                    categories = list(result['auto_categorization'].keys())
                    print(f"   Categories: {categories}")
            else:
                print(f"❌ FILTERED: {imported}/{total} imported (likely filtered as points)")
                if result.get('errors'):
                    print(f"   Errors: {result['errors']}")
        else:
            print(f"❌ FAILED: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")

if __name__ == "__main__":
    test_amount_parsing_debug()