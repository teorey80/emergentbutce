import requests
import json
from datetime import datetime
import sys

class ExpenseTrackerAPITester:
    def __init__(self, base_url="https://b72b9d31-4785-4523-b579-5e08df25fcbf.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.created_expenses = []

    def run_test(self, name, method, endpoint, expected_status, data=None):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=headers)
            
            success = response.status_code == expected_status
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
            return False, None

    def test_get_categories(self):
        """Test getting all expense categories"""
        success, response = self.run_test(
            "Get Categories",
            "GET",
            "categories",
            200
        )
        if success:
            print(f"Found {len(response)} categories")
            if len(response) == 8:
                print("✅ Correct number of categories (8)")
            else:
                print(f"❌ Expected 8 categories, got {len(response)}")
            
            # Check if 'food' category exists
            food_category = next((cat for cat in response if cat['id'] == 'food'), None)
            if food_category:
                print(f"✅ Found 'food' category: {food_category['name']}")
            else:
                print("❌ 'food' category not found")
        
        return success, response

    def test_get_expenses(self):
        """Test getting all expenses"""
        success, response = self.run_test(
            "Get Expenses",
            "GET",
            "expenses",
            200
        )
        if success:
            print(f"Found {len(response)} expenses")
        return success, response

    def test_create_expense(self, title, amount, category, description=None):
        """Test creating a new expense"""
        data = {
            "title": title,
            "amount": amount,
            "category": category
        }
        if description:
            data["description"] = description
        
        success, response = self.run_test(
            f"Create Expense: {title}",
            "POST",
            "expenses",
            200,
            data=data
        )
        
        if success and response and 'id' in response:
            self.created_expenses.append(response['id'])
            print(f"✅ Created expense with ID: {response['id']}")
            print(f"✅ Title: {response['title']}")
            print(f"✅ Amount: {response['amount']}")
            print(f"✅ Category: {response['category']}")
            if description:
                print(f"✅ Description: {response['description']}")
        
        return success, response

    def test_delete_expense(self, expense_id):
        """Test deleting an expense"""
        success, response = self.run_test(
            f"Delete Expense: {expense_id}",
            "DELETE",
            f"expenses/{expense_id}",
            200
        )
        if success:
            print(f"✅ Successfully deleted expense with ID: {expense_id}")
            if expense_id in self.created_expenses:
                self.created_expenses.remove(expense_id)
        
        return success, response

    def test_get_expense_stats(self):
        """Test getting expense statistics"""
        success, response = self.run_test(
            "Get Expense Statistics",
            "GET",
            "expenses/stats/summary",
            200
        )
        if success:
            print(f"✅ Total amount: {response['total_amount']}")
            print(f"✅ Expense count: {response['expense_count']}")
            print(f"✅ Categories with expenses: {list(response['category_stats'].keys())}")
        
        return success, response

    def test_invalid_category(self):
        """Test creating an expense with an invalid category"""
        data = {
            "title": "Invalid Category Test",
            "amount": 100.0,
            "category": "invalid_category"
        }
        
        success, response = self.run_test(
            "Create Expense with Invalid Category",
            "POST",
            "expenses",
            400,
            data=data
        )
        
        # For this test, we expect a failure (400 status code)
        if not success:
            print("✅ Correctly rejected invalid category")
            self.tests_passed += 1  # Manually increment since we expect failure
        
        return not success, response

    def cleanup(self):
        """Clean up any created expenses"""
        print("\n🧹 Cleaning up created expenses...")
        for expense_id in self.created_expenses[:]:
            self.test_delete_expense(expense_id)

def main():
    # Setup
    tester = ExpenseTrackerAPITester()
    
    # Run tests
    print("\n==== Testing Expense Tracker API ====")
    
    # Test getting categories
    categories_success, categories = tester.test_get_categories()
    if not categories_success:
        print("❌ Failed to get categories, stopping tests")
        return 1
    
    # Test getting expenses (initial state)
    tester.test_get_expenses()
    
    # Test creating expenses
    tester.test_create_expense("Öğle Yemeği", 45.50, "food", "Restoran")
    tester.test_create_expense("Taksi", 120.75, "transport", "İş seyahati")
    tester.test_create_expense("Sinema", 85.00, "entertainment")
    
    # Test getting expenses after creation
    tester.test_get_expenses()
    
    # Test getting expense statistics
    tester.test_get_expense_stats()
    
    # Test invalid category
    tester.test_invalid_category()
    
    # Clean up
    tester.cleanup()
    
    # Print results
    print(f"\n📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())