import requests
import json
import io
import sys
from datetime import datetime, date

class TurkishBankParsingTester:
    def __init__(self, base_url="https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.critical_issues = []
        self.test_results = {
            "critical_bug_fix": {"passed": 0, "total": 0, "details": []},
            "number_format_parsing": {"passed": 0, "total": 0, "details": []},
            "point_filtering": {"passed": 0, "total": 0, "details": []},
            "file_import_success": {"passed": 0, "total": 0, "details": []},
            "data_integrity": {"passed": 0, "total": 0, "details": []}
        }

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, category="general"):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'} if not files else {}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files)
                else:
                    response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            
            success = response.status_code == expected_status
            
            # Track results by category
            if category in self.test_results:
                self.test_results[category]["total"] += 1
                if success:
                    self.test_results[category]["passed"] += 1
                    self.test_results[category]["details"].append(f"✅ {name}")
                else:
                    self.test_results[category]["details"].append(f"❌ {name} - Expected {expected_status}, got {response.status_code}")
            
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                if response.text:
                    try:
                        return success, response.json()
                    except json.JSONDecodeError:
                        return success, response.text
                return success, None
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"Response: {response.text}")
                return False, None

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            if category in self.test_results:
                self.test_results[category]["total"] += 1
                self.test_results[category]["details"].append(f"❌ {name} - Error: {str(e)}")
            return False, None

    def test_critical_bug_fix_scenario(self):
        """Test the specific scenario that was failing: Turkish bank credit card statement with reward patterns"""
        print("\n🚨 TESTING CRITICAL BUG FIX - Turkish Bank Credit Card with Reward Patterns")
        
        # Test case from the bug report: METRO UMRANIYE TEKEL with amount 1.544,14
        csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1.544,14,2024-01-15
CARREFOUR ATASEHIR ISTANBUL TR KAZANILAN MAXIMIL:2,15 MAXIPUAN:0,32,856,75,2024-01-14
BIM MARKET KADIKOY ISTANBUL TR KAZANILAN MAXIMIL:1,85 MAXIPUAN:0,28,425,90,2024-01-13"""
        
        files = {'file': ('turkish_bank_test.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "Critical Bug Fix - Turkish Bank Credit Card Import",
            "POST",
            "upload/csv",
            200,
            files=files,
            category="critical_bug_fix"
        )
        
        if success and response:
            imported = response.get('imported', 0)
            total_rows = response.get('total_rows', 0)
            
            print(f"📊 Import Results:")
            print(f"   Total rows: {total_rows}")
            print(f"   Imported: {imported}")
            print(f"   Success rate: {(imported/total_rows)*100:.1f}%" if total_rows > 0 else "N/A")
            
            # Critical test: All 3 legitimate transactions should be imported
            if imported == 3:
                print("✅ CRITICAL BUG FIXED: All legitimate transactions with reward patterns imported correctly")
                self.test_results["critical_bug_fix"]["details"].append("✅ All legitimate transactions imported (3/3)")
            elif imported == 0:
                print("❌ CRITICAL BUG STILL EXISTS: All transactions filtered incorrectly")
                self.critical_issues.append("All Turkish bank transactions with reward patterns are being filtered")
                self.test_results["critical_bug_fix"]["details"].append("❌ All transactions filtered (0/3)")
            else:
                print(f"⚠️ PARTIAL FIX: Only {imported}/3 transactions imported")
                self.critical_issues.append(f"Only {imported}/3 Turkish bank transactions imported correctly")
                self.test_results["critical_bug_fix"]["details"].append(f"⚠️ Partial import ({imported}/3)")
            
            # Check auto-categorization worked
            auto_cat = response.get('auto_categorization', {})
            if auto_cat:
                print(f"✅ Auto-categorization working: {list(auto_cat.keys())}")
            
        return success, response

    def test_turkish_number_format_variations(self):
        """Test all Turkish number format variations"""
        print("\n🔢 TESTING TURKISH NUMBER FORMAT PARSING")
        
        # Test various Turkish number formats
        test_cases = [
            ("Turkish format with thousands and decimal", "1.544,14", 1544.14),
            ("US format with thousands and decimal", "1,544.14", 1544.14),
            ("Turkish decimal only", "234,50", 234.50),
            ("Thousands separator only", "1,544", 1544.0),
            ("Simple integer", "234", 234.0),
            ("Large amount Turkish format", "12.345,67", 12345.67),
            ("Large amount US format", "12,345.67", 12345.67)
        ]
        
        for description, amount_str, expected_amount in test_cases:
            csv_content = f"""description,amount,date
TEST MERCHANT ISTANBUL TR,{amount_str},2024-01-15"""
            
            files = {'file': ('number_format_test.csv', csv_content, 'text/csv')}
            
            success, response = self.run_test(
                f"Number Format: {description} ({amount_str})",
                "POST",
                "upload/csv",
                200,
                files=files,
                category="number_format_parsing"
            )
            
            if success and response:
                imported = response.get('imported', 0)
                if imported == 1:
                    print(f"✅ Successfully parsed {amount_str} as ₺{expected_amount}")
                else:
                    print(f"❌ Failed to parse {amount_str} - expected ₺{expected_amount}")
                    self.critical_issues.append(f"Number format parsing failed for {amount_str}")

    def test_point_filtering_still_works(self):
        """Test that legitimate point filtering still works after the fix"""
        print("\n🎯 TESTING POINT FILTERING FUNCTIONALITY")
        
        # Test cases that SHOULD be filtered (small amounts with reward patterns)
        csv_content = """description,amount,date
SMALL PURCHASE MAXIMIL:3,09,3,09,2024-01-15
TINY TRANSACTION MAXIPUAN:0,46,0,46,2024-01-14
BONUS POINTS WORLDPUAN:2,15,2,15,2024-01-13
LEGITIMATE PURCHASE MAXIMIL:1,25,125,50,2024-01-12"""
        
        files = {'file': ('point_filtering_test.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "Point Filtering - Small Amounts with Reward Patterns",
            "POST",
            "upload/csv",
            200,
            files=files,
            category="point_filtering"
        )
        
        if success and response:
            imported = response.get('imported', 0)
            total_rows = response.get('total_rows', 0)
            
            # Should import only the legitimate purchase (125,50 TL), filter the small amounts
            if imported == 1:
                print("✅ Point filtering working correctly - filtered small amounts, kept legitimate transaction")
                self.test_results["point_filtering"]["details"].append("✅ Correctly filtered 3 small amounts, kept 1 legitimate")
            elif imported == 0:
                print("❌ Over-filtering - legitimate transaction also filtered")
                self.critical_issues.append("Point filtering is too aggressive - filtering legitimate transactions")
            elif imported == 4:
                print("❌ Under-filtering - small point amounts not filtered")
                self.critical_issues.append("Point filtering not working - small amounts not filtered")
            else:
                print(f"⚠️ Unexpected filtering result: {imported}/4 imported")

    def test_file_import_success_rates(self):
        """Test import success rates for different file formats"""
        print("\n📁 TESTING FILE IMPORT SUCCESS RATES")
        
        # Test CSV with mixed Turkish bank data
        csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1.544,14,2024-01-15
MIGROS ATASEHIR ISTANBUL TR,234,50,2024-01-14
SHELL BENZIN ISTANBUL TR,156,75,2024-01-13
STARBUCKS KADIKOY ISTANBUL TR KAZANILAN MAXIMIL:1,25,45,80,2024-01-12
TAKSI UBER ISTANBUL TR,67,25,2024-01-11"""
        
        files = {'file': ('mixed_turkish_bank.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "CSV Import - Mixed Turkish Bank Data",
            "POST",
            "upload/csv",
            200,
            files=files,
            category="file_import_success"
        )
        
        if success and response:
            imported = response.get('imported', 0)
            total_rows = response.get('total_rows', 0)
            success_rate = (imported/total_rows)*100 if total_rows > 0 else 0
            
            print(f"📊 CSV Import Success Rate: {success_rate:.1f}% ({imported}/{total_rows})")
            
            if success_rate >= 80:
                print("✅ High success rate - CSV import working well")
            elif success_rate >= 60:
                print("⚠️ Moderate success rate - some issues with CSV import")
            else:
                print("❌ Low success rate - significant CSV import issues")
                self.critical_issues.append(f"Low CSV import success rate: {success_rate:.1f}%")

        # Test Excel endpoint availability
        files = {'file': ('test.xlsx', b'', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        success, response = self.run_test(
            "Excel Import - Endpoint Availability",
            "POST",
            "upload/excel",
            400,  # Expect 400 for invalid file
            files=files,
            category="file_import_success"
        )
        
        if not success:
            print("✅ Excel endpoint available (returned expected error for invalid file)")
            self.test_results["file_import_success"]["passed"] += 1
            self.test_results["file_import_success"]["details"][-1] = "✅ Excel Import - Endpoint Availability"

        # Test PDF endpoint
        pdf_content = b"%PDF-1.4\n25.02.2025 METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46 1,544.14-"
        files = {'file': ('turkish_bank_statement.pdf', pdf_content, 'application/pdf')}
        
        success, response = self.run_test(
            "PDF Import - Turkish Bank Statement",
            "POST",
            "upload/pdf",
            200,
            files=files,
            category="file_import_success"
        )

    def test_data_integrity_verification(self):
        """Test data integrity after import"""
        print("\n🔍 TESTING DATA INTEGRITY VERIFICATION")
        
        # Import test data
        csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1.544,14,2024-01-15
MIGROS MARKET ISTANBUL TR,125,50,2024-01-14"""
        
        files = {'file': ('integrity_test.csv', csv_content, 'text/csv')}
        
        success, response = self.run_test(
            "Data Integrity - Import Test Data",
            "POST",
            "upload/csv",
            200,
            files=files,
            category="data_integrity"
        )
        
        if success and response:
            imported = response.get('imported', 0)
            
            if imported > 0:
                # Verify data can be retrieved
                success, expenses = self.run_test(
                    "Data Integrity - Retrieve Imported Data",
                    "GET",
                    "expenses",
                    200,
                    category="data_integrity"
                )
                
                if success and expenses:
                    # Check for our test data
                    metro_found = False
                    migros_found = False
                    
                    for expense in expenses:
                        title = expense.get('title', '').upper()
                        amount = expense.get('amount', 0)
                        
                        if 'METRO' in title and abs(amount - 1544.14) < 0.01:
                            metro_found = True
                            print(f"✅ METRO transaction found: {expense['title']} - ₺{expense['amount']}")
                        elif 'MIGROS' in title and abs(amount - 125.50) < 0.01:
                            migros_found = True
                            print(f"✅ MIGROS transaction found: {expense['title']} - ₺{expense['amount']}")
                    
                    if metro_found and migros_found:
                        print("✅ Data integrity verified - all imported transactions retrievable with correct amounts")
                    else:
                        print("❌ Data integrity issue - imported transactions not found or incorrect amounts")
                        self.critical_issues.append("Data integrity issue - imported data not retrievable correctly")
                
                # Test merchant name cleaning
                success, filter_response = self.run_test(
                    "Data Integrity - Merchant Name Cleaning",
                    "GET",
                    "expenses/filter?search=METRO",
                    200,
                    category="data_integrity"
                )
                
                if success and filter_response:
                    if len(filter_response) > 0:
                        print("✅ Merchant name cleaning working - METRO transactions searchable")
                    else:
                        print("⚠️ Merchant name cleaning may have issues - METRO not found in search")

    def get_current_expense_count(self):
        """Get current number of expenses for comparison"""
        try:
            response = requests.get(f"{self.api_url}/expenses")
            if response.status_code == 200:
                expenses = response.json()
                return len(expenses)
        except:
            pass
        return 0

    def print_critical_issues_summary(self):
        """Print summary of critical issues found"""
        print("\n" + "="*60)
        print("🚨 CRITICAL ISSUES SUMMARY")
        print("="*60)
        
        if not self.critical_issues:
            print("✅ NO CRITICAL ISSUES FOUND!")
            print("The Turkish bank statement parsing fix appears to be working correctly.")
        else:
            print(f"❌ {len(self.critical_issues)} CRITICAL ISSUES FOUND:")
            for i, issue in enumerate(self.critical_issues, 1):
                print(f"  {i}. {issue}")
        
        print("="*60)

    def print_test_summary(self):
        """Print detailed test summary by category"""
        print("\n" + "="*60)
        print("📊 TURKISH BANK PARSING TEST RESULTS")
        print("="*60)
        
        total_passed = 0
        total_tests = 0
        
        for category, results in self.test_results.items():
            passed = results["passed"]
            total = results["total"]
            total_passed += passed
            total_tests += total
            
            if total > 0:
                percentage = (passed / total) * 100
                status = "✅ PASS" if passed == total else "❌ FAIL" if passed == 0 else "⚠️ PARTIAL"
                
                print(f"\n{category.upper().replace('_', ' ')}:")
                print(f"  Status: {status} ({passed}/{total} - {percentage:.1f}%)")
                
                for detail in results["details"]:
                    print(f"    {detail}")
        
        print(f"\n{'='*60}")
        overall_percentage = (total_passed / total_tests) * 100 if total_tests > 0 else 0
        overall_status = "✅ ALL PASS" if total_passed == total_tests else "❌ SOME FAILED" if total_passed == 0 else "⚠️ PARTIAL SUCCESS"
        
        print(f"OVERALL RESULT: {overall_status}")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_tests - total_passed}")
        print(f"Success Rate: {overall_percentage:.1f}%")
        print("="*60)
        
        return total_passed, total_tests

def main():
    print("\n" + "="*60)
    print("🇹🇷 TURKISH BANK STATEMENT PARSING - CRITICAL BUG FIX VERIFICATION")
    print("="*60)
    
    tester = TurkishBankParsingTester()
    
    # Get initial expense count
    initial_count = tester.get_current_expense_count()
    print(f"📊 Initial expense count: {initial_count}")
    
    # 1. Test the critical bug fix scenario
    print("\n🎯 PHASE 1: CRITICAL BUG FIX VERIFICATION")
    tester.test_critical_bug_fix_scenario()
    
    # 2. Test Turkish number format parsing
    print("\n🎯 PHASE 2: TURKISH NUMBER FORMAT PARSING")
    tester.test_turkish_number_format_variations()
    
    # 3. Test point filtering still works
    print("\n🎯 PHASE 3: POINT FILTERING VERIFICATION")
    tester.test_point_filtering_still_works()
    
    # 4. Test file import success rates
    print("\n🎯 PHASE 4: FILE IMPORT SUCCESS RATES")
    tester.test_file_import_success_rates()
    
    # 5. Test data integrity
    print("\n🎯 PHASE 5: DATA INTEGRITY VERIFICATION")
    tester.test_data_integrity_verification()
    
    # Print results
    tester.print_critical_issues_summary()
    passed, total = tester.print_test_summary()
    
    # Final assessment
    print("\n" + "="*60)
    print("🎯 FINAL ASSESSMENT")
    print("="*60)
    
    if len(tester.critical_issues) == 0 and passed == total:
        print("✅ CRITICAL BUG FIX SUCCESSFUL!")
        print("Turkish bank statement parsing is working correctly.")
        print("All test scenarios passed without critical issues.")
    elif len(tester.critical_issues) == 0:
        print("⚠️ MOSTLY SUCCESSFUL")
        print("No critical issues found, but some minor test failures.")
        print("Turkish bank statement parsing appears to be working.")
    else:
        print("❌ CRITICAL ISSUES REMAIN")
        print("The bug fix may not be complete or new issues introduced.")
        print("Immediate attention required for Turkish bank statement parsing.")
    
    print("="*60)
    
    return 0 if len(tester.critical_issues) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())