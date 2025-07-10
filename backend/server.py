from fastapi import FastAPI, APIRouter, HTTPException, File, UploadFile
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, date, timedelta
from decimal import Decimal
import pandas as pd
import io
from PyPDF2 import PdfReader
import re
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Expense Categories
EXPENSE_CATEGORIES = [
    {"id": "food", "name": "Yiyecek & İçecek", "color": "#FF6B6B", "icon": "🍽️"},
    {"id": "transport", "name": "Ulaşım", "color": "#4ECDC4", "icon": "🚗"},
    {"id": "entertainment", "name": "Eğlence", "color": "#45B7D1", "icon": "🎬"},
    {"id": "shopping", "name": "Alışveriş", "color": "#96CEB4", "icon": "🛍️"},
    {"id": "health", "name": "Sağlık", "color": "#FFEAA7", "icon": "🏥"},
    {"id": "education", "name": "Eğitim", "color": "#DDA0DD", "icon": "📚"},
    {"id": "bills", "name": "Faturalar", "color": "#FF7675", "icon": "💡"},
    {"id": "other", "name": "Diğer", "color": "#A0A0A0", "icon": "📦"}
]

# Define Models
class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: str
    description: Optional[str] = None
    date: Optional[str] = None  # Accept date as string from frontend

class Expense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    amount: float
    category: str
    description: Optional[str] = None
    date: str  # Store as string in MongoDB
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None

# Root endpoint
@api_router.get("/")
async def root():
    return {"message": "Expense Tracker API"}

# Get all expense categories
@api_router.get("/categories")
async def get_categories():
    return EXPENSE_CATEGORIES

# Create a new expense
@api_router.post("/expenses", response_model=Expense)
async def create_expense(expense_data: ExpenseCreate):
    # Validate category
    valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
    if expense_data.category not in valid_categories:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    expense_dict = expense_data.dict()
    
    # Set default date if not provided
    if not expense_dict.get('date'):
        expense_dict['date'] = date.today().isoformat()
        
    expense_obj = Expense(**expense_dict)
    
    # Convert to dict for MongoDB
    expense_doc = expense_obj.dict()
    expense_doc['created_at'] = expense_obj.created_at.isoformat()
    
    await db.expenses.insert_one(expense_doc)
    return expense_obj

# Get all expenses
@api_router.get("/expenses", response_model=List[Expense])
async def get_expenses():
    expenses = await db.expenses.find().sort("created_at", -1).to_list(1000)
    
    # Convert date strings back to datetime objects
    for expense in expenses:
        if isinstance(expense.get('created_at'), str):
            expense['created_at'] = datetime.fromisoformat(expense['created_at'])
    
    return [Expense(**expense) for expense in expenses]

# Get expense by ID
@api_router.get("/expenses/{expense_id}", response_model=Expense)
async def get_expense(expense_id: str):
    expense = await db.expenses.find_one({"id": expense_id})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    if isinstance(expense.get('created_at'), str):
        expense['created_at'] = datetime.fromisoformat(expense['created_at'])
    
    return Expense(**expense)

# Update expense
@api_router.put("/expenses/{expense_id}", response_model=Expense)
async def update_expense(expense_id: str, expense_data: ExpenseUpdate):
    expense = await db.expenses.find_one({"id": expense_id})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Update fields
    update_data = expense_data.dict(exclude_unset=True)
    if update_data:
        await db.expenses.update_one({"id": expense_id}, {"$set": update_data})
    
    # Get updated expense
    updated_expense = await db.expenses.find_one({"id": expense_id})
    if isinstance(updated_expense.get('created_at'), str):
        updated_expense['created_at'] = datetime.fromisoformat(updated_expense['created_at'])
    
    return Expense(**updated_expense)

# Delete expense
@api_router.delete("/expenses/{expense_id}")
async def delete_expense(expense_id: str):
    result = await db.expenses.delete_one({"id": expense_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    return {"message": "Expense deleted successfully"}

# Get expense statistics
@api_router.get("/expenses/stats/summary")
async def get_expense_stats():
    expenses = await db.expenses.find().to_list(1000)
    
    total_amount = sum(expense['amount'] for expense in expenses)
    expense_count = len(expenses)
    
    # Category breakdown
    category_stats = {}
    for expense in expenses:
        category = expense['category']
        if category not in category_stats:
            category_stats[category] = {'total': 0, 'count': 0}
        category_stats[category]['total'] += expense['amount']
        category_stats[category]['count'] += 1
    
    # Find category info
    for cat_id, stats in category_stats.items():
        category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == cat_id), None)
        if category_info:
            stats['name'] = category_info['name']
            stats['color'] = category_info['color']
            stats['icon'] = category_info['icon']
    
    return {
        "total_amount": total_amount,
        "expense_count": expense_count,
        "category_stats": category_stats
    }

# Get monthly expense statistics
@api_router.get("/expenses/stats/monthly")
async def get_monthly_stats():
    expenses = await db.expenses.find().to_list(1000)
    
    # Turkish month names
    turkish_months = {
        1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan",
        5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos",
        9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
    }
    
    monthly_stats = {}
    for expense in expenses:
        # Parse date string to extract year-month
        expense_date = expense['date']
        if isinstance(expense_date, str):
            try:
                parsed_date = datetime.fromisoformat(expense_date)
                month_key = parsed_date.strftime("%Y-%m")
                month_name = f"{turkish_months[parsed_date.month]} {parsed_date.year}"
            except:
                month_key = "Unknown"
                month_name = "Bilinmeyen"
        else:
            month_key = "Unknown"
            month_name = "Bilinmeyen"
        
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {
                'month': month_name,
                'total': 0,
                'count': 0,
                'categories': {}
            }
        
        monthly_stats[month_key]['total'] += expense['amount']
        monthly_stats[month_key]['count'] += 1
        
        # Category breakdown for each month
        category = expense['category']
        if category not in monthly_stats[month_key]['categories']:
            monthly_stats[month_key]['categories'][category] = 0
        monthly_stats[month_key]['categories'][category] += expense['amount']
    
    # Convert to list and sort by month
    monthly_list = []
    for month_key, stats in monthly_stats.items():
        if month_key != "Unknown":
            monthly_list.append({
                'month_key': month_key,
                'month': stats['month'],
                'total': stats['total'],
                'count': stats['count'],
                'categories': stats['categories']
            })
    
    # Sort by month_key
    monthly_list.sort(key=lambda x: x['month_key'])
    
    return monthly_list

# Get category trend data
@api_router.get("/expenses/stats/trends")
async def get_trend_stats():
    expenses = await db.expenses.find().to_list(1000)
    
    # Group by category and month
    trends = {}
    for expense in expenses:
        category = expense['category']
        expense_date = expense['date']
        
        if isinstance(expense_date, str):
            try:
                parsed_date = datetime.fromisoformat(expense_date)
                month_key = parsed_date.strftime("%Y-%m")
            except:
                month_key = "Unknown"
        else:
            month_key = "Unknown"
        
        if category not in trends:
            trends[category] = {}
        
        if month_key not in trends[category]:
            trends[category][month_key] = 0
        
        trends[category][month_key] += expense['amount']
    
    # Format for chart consumption
    formatted_trends = []
    for cat_id, monthly_data in trends.items():
        category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == cat_id), None)
        if category_info:
            formatted_trends.append({
                'category': category_info['name'],
                'category_id': cat_id,
                'color': category_info['color'],
                'data': [{'month': month, 'amount': amount} for month, amount in sorted(monthly_data.items())]
            })
    
    return formatted_trends

# Smart categorization system
SMART_CATEGORIES = {
    "food": [
        "migros", "bim", "a101", "şok", "carrefour", "metro", "real", "kipa", "lidl",
        "market", "bakkal", "manav", "kasap", "fırın", "pastane", "cafe", "restaurant",
        "restoran", "lokanta", "pizzeria", "döner", "kebap", "burger", "mcdonald",
        "burger king", "kfc", "dominos", "pizza hut", "starbucks", "kahve dünyası",
        "yemek", "food", "gıda", "et", "tavuk", "balık", "sebze", "meyve"
    ],
    "transport": [
        "benzin", "petrol", "shell", "bp", "total", "opet", "petlas", "oto",
        "taksi", "uber", "bitaksi", "otobüs", "metro", "dolmuş", "minibüs",
        "uçak", "pegasus", "turkish airlines", "onur air", "tren", "tcdd",
        "yakıt", "akaryakıt", "garaj", "otopark", "köprü", "geçiş", "hgs", "ogs"
    ],
    "shopping": [
        "zara", "h&m", "mango", "koton", "lc waikiki", "defacto", "colin's",
        "mavi", "beymen", "vakko", "boyner", "teknosa", "vatan", "media markt",
        "btech", "apple store", "samsung", "amazon", "trendyol", "hepsiburada",
        "gittigidiyor", "n11", "sahibinden", "dolap", "modanisa", "ayakkabı",
        "giyim", "kıyafet", "elektronik", "telefon", "bilgisayar", "laptop"
    ],
    "entertainment": [
        "sinema", "cinema", "cinemax", "cinemaximum", "akmerkez", "forum",
        "netflix", "spotify", "apple music", "youtube", "gaming", "playstation",
        "xbox", "steam", "google play", "app store", "tiyatro", "konser",
        "müze", "aquarium", "lunapark", "bowling", "bilardo", "karaoke",
        "eğlence", "oyun", "film", "müzik", "kitap", "dergi"
    ],
    "health": [
        "hastane", "hospital", "doktor", "doctor", "eczane", "pharmacy", "sağlık",
        "tıp", "medical", "diş", "dental", "göz", "eye", "kulak", "ear",
        "jinekolog", "üroloji", "kardiyoloji", "nöroloji", "psikiyatri",
        "fizik tedavi", "laboratuvar", "röntgen", "mri", "ameliyat", "ilaç",
        "vitamin", "medikal", "klinik", "sağlık ocağı"
    ],
    "education": [
        "okul", "school", "üniversite", "university", "kurs", "course", "eğitim",
        "education", "kitap", "book", "kırtasiye", "kalem", "defter", "çanta",
        "udemy", "coursera", "khan academy", "özel ders", "dershane", "etüt",
        "sınav", "test", "ödev", "proje", "akademi", "enstitü", "kolej"
    ],
    "bills": [
        "elektrik", "electric", "tedaş", "ayedaş", "bedaş", "su", "water", "aski",
        "doğalgaz", "gas", "igdaş", "internet", "ttnet", "turkcell", "vodafone",
        "türk telekom", "telefon", "phone", "fatura", "bill", "abonelik",
        "netflix", "spotify", "apple", "google", "microsoft", "amazon prime",
        "aidat", "apartman", "site", "yönetim", "kira", "rent"
    ]
}

def smart_categorize(title, description=""):
    """Automatically categorize expense based on title and description"""
    text = f"{title} {description}".lower()
    
    # Score each category
    category_scores = {}
    for category, keywords in SMART_CATEGORIES.items():
        score = 0
        for keyword in keywords:
            if keyword in text:
                # Give higher score for exact matches
                if keyword == text.strip():
                    score += 10
                # Give medium score for word matches
                elif f" {keyword} " in f" {text} ":
                    score += 5
                # Give lower score for partial matches
                elif keyword in text:
                    score += 1
        category_scores[category] = score
    
    # Return category with highest score, or 'other' if no match
    if max(category_scores.values()) > 0:
        return max(category_scores, key=category_scores.get)
    return "other"

# Enhanced file upload endpoint for CSV
@api_router.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        contents = await file.read()
        # Try different encodings
        try:
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(io.StringIO(contents.decode('iso-8859-9')))  # Turkish encoding
            except UnicodeDecodeError:
                df = pd.read_csv(io.StringIO(contents.decode('windows-1254')))  # Windows Turkish
        
        # Check if it's a bank statement format
        # Common CSV formats: date, description, amount OR transaction_date, merchant, amount
        possible_columns = {
            'title': ['description', 'merchant', 'title', 'açıklama', 'işlem açıklaması', 'merchant_name'],
            'amount': ['amount', 'tutar', 'miktar', 'toplam', 'total', 'transaction_amount'],
            'date': ['date', 'tarih', 'transaction_date', 'işlem tarihi', 'transaction_time'],
            'category': ['category', 'kategori', 'type', 'tip'],
            'description': ['description', 'açıklama', 'detay', 'details', 'memo']
        }
        
        # Map columns automatically
        column_mapping = {}
        for standard_col, possible_names in possible_columns.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    column_mapping[standard_col] = col
                    break
        
        # Ensure we have at least title and amount
        if 'title' not in column_mapping or 'amount' not in column_mapping:
            # If no mapping found, assume first few columns are title, amount, etc.
            if len(df.columns) >= 2:
                column_mapping['title'] = df.columns[0]
                column_mapping['amount'] = df.columns[1]
                if len(df.columns) >= 3:
                    column_mapping['date'] = df.columns[2]
            else:
                raise HTTPException(status_code=400, detail="Could not identify title and amount columns")
        
        # Process and insert expenses
        expenses_added = 0
        errors = []
        categories_assigned = {}
        
        for index, row in df.iterrows():
            try:
                # Extract title
                title = str(row[column_mapping['title']]).strip()
                if pd.isna(row[column_mapping['title']]) or not title:
                    continue
                
                # Extract amount (handle negative values for expenses)
                amount_val = row[column_mapping['amount']]
                if pd.isna(amount_val):
                    continue
                
                # Handle different amount formats
                amount_str = str(amount_val).strip()
                
                # Remove currency symbols and extra text
                amount_str = re.sub(r'[₺TL\-]', '', amount_str)  # Remove ₺, TL, and - symbols
                
                # Handle Turkish decimal format (comma as decimal separator)
                if ',' in amount_str and '.' not in amount_str:
                    # Turkish format: 234,50
                    amount_str = amount_str.replace(',', '.')
                elif ',' in amount_str and '.' in amount_str:
                    # Mixed format: 1.234,50 (thousands separator)
                    parts = amount_str.split(',')
                    if len(parts) == 2 and len(parts[1]) == 2:  # Decimal part
                        amount_str = parts[0].replace('.', '') + '.' + parts[1]
                    else:
                        amount_str = amount_str.replace(',', '')
                
                # Remove any remaining spaces
                amount_str = amount_str.replace(' ', '').strip()
                
                # Extract only numeric values with decimal
                amount_match = re.search(r'(\d+\.?\d*)', amount_str)
                if amount_match:
                    try:
                        amount = float(amount_match.group(1))
                    except ValueError:
                        continue
                else:
                    continue
                
                if amount <= 0:
                    continue
                
                # Extract description
                description = ""
                if 'description' in column_mapping and pd.notna(row[column_mapping['description']]):
                    description = str(row[column_mapping['description']]).strip()
                
                # Extract date
                expense_date = date.today().isoformat()
                if 'date' in column_mapping and pd.notna(row[column_mapping['date']]):
                    try:
                        parsed_date = pd.to_datetime(row[column_mapping['date']])
                        expense_date = parsed_date.date().isoformat()
                    except:
                        pass
                
                # Smart categorization
                if 'category' in column_mapping and pd.notna(row[column_mapping['category']]):
                    # Use provided category if valid
                    provided_category = str(row[column_mapping['category']]).lower()
                    valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
                    category = provided_category if provided_category in valid_categories else smart_categorize(title, description)
                else:
                    # Auto-categorize
                    category = smart_categorize(title, description)
                
                # Track categorization
                if category not in categories_assigned:
                    categories_assigned[category] = []
                categories_assigned[category].append(title)
                
                expense_data = {
                    'title': title,
                    'amount': amount,
                    'category': category,
                    'description': description if description else None,
                    'date': expense_date
                }
                
                expense_obj = Expense(**expense_data)
                expense_doc = expense_obj.dict()
                expense_doc['created_at'] = expense_obj.created_at.isoformat()
                
                await db.expenses.insert_one(expense_doc)
                expenses_added += 1
                
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        return {
            "message": f"Successfully imported {expenses_added} expenses",
            "total_rows": len(df),
            "imported": expenses_added,
            "errors": errors,
            "auto_categorization": categories_assigned,
            "detected_columns": column_mapping
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

# Enhanced file upload endpoint for Excel
@api_router.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file")
    
    try:
        contents = await file.read()
        # Try to read Excel file
        try:
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')
        except:
            df = pd.read_excel(io.BytesIO(contents))
        
        # Apply same logic as CSV
        possible_columns = {
            'title': ['description', 'merchant', 'title', 'açıklama', 'işlem açıklaması', 'merchant_name'],
            'amount': ['amount', 'tutar', 'miktar', 'toplam', 'total', 'transaction_amount'],
            'date': ['date', 'tarih', 'transaction_date', 'işlem tarihi', 'transaction_time'],
            'category': ['category', 'kategori', 'type', 'tip'],
            'description': ['description', 'açıklama', 'detay', 'details', 'memo']
        }
        
        # Map columns automatically
        column_mapping = {}
        for standard_col, possible_names in possible_columns.items():
            for col in df.columns:
                if col.lower() in [name.lower() for name in possible_names]:
                    column_mapping[standard_col] = col
                    break
        
        # Ensure we have at least title and amount
        if 'title' not in column_mapping or 'amount' not in column_mapping:
            if len(df.columns) >= 2:
                column_mapping['title'] = df.columns[0]
                column_mapping['amount'] = df.columns[1]
                if len(df.columns) >= 3:
                    column_mapping['date'] = df.columns[2]
            else:
                raise HTTPException(status_code=400, detail="Could not identify title and amount columns")
        
        # Process and insert expenses
        expenses_added = 0
        errors = []
        categories_assigned = {}
        
        for index, row in df.iterrows():
            try:
                # Extract title
                title = str(row[column_mapping['title']]).strip()
                if pd.isna(row[column_mapping['title']]) or not title:
                    continue
                
                # Extract amount (handle negative values for expenses)
                amount_val = row[column_mapping['amount']]
                if pd.isna(amount_val):
                    continue
                    
                # Handle different amount formats
                amount_str = str(amount_val).strip()
                print(f"Processing Excel amount: '{amount_str}'")  # Debug log
                
                # Remove currency symbols and extra text
                amount_str = re.sub(r'[₺TL\-]', '', amount_str)  # Remove ₺, TL, and - symbols
                
                # Handle Turkish decimal format (comma as decimal separator)
                if ',' in amount_str and '.' not in amount_str:
                    # Turkish format: 234,50
                    amount_str = amount_str.replace(',', '.')
                elif ',' in amount_str and '.' in amount_str:
                    # Mixed format: 1.234,50 (thousands separator)
                    parts = amount_str.split(',')
                    if len(parts) == 2 and len(parts[1]) == 2:  # Decimal part
                        amount_str = parts[0].replace('.', '') + '.' + parts[1]
                    else:
                        amount_str = amount_str.replace(',', '')
                
                # Remove any remaining spaces
                amount_str = amount_str.replace(' ', '').strip()
                
                # Extract only numeric values with decimal
                amount_match = re.search(r'(\d+\.?\d*)', amount_str)
                if amount_match:
                    try:
                        amount = float(amount_match.group(1))
                        print(f"Parsed Excel amount: {amount}")  # Debug log
                    except ValueError:
                        print(f"Failed to parse Excel amount: {amount_str}")
                        continue
                else:
                    print(f"No numeric value found in Excel: {amount_str}")
                    continue
                
                if amount <= 0:
                    continue
                
                # Extract description
                description = ""
                if 'description' in column_mapping and pd.notna(row[column_mapping['description']]):
                    description = str(row[column_mapping['description']]).strip()
                
                # Extract date
                expense_date = date.today().isoformat()
                if 'date' in column_mapping and pd.notna(row[column_mapping['date']]):
                    try:
                        parsed_date = pd.to_datetime(row[column_mapping['date']])
                        expense_date = parsed_date.date().isoformat()
                    except:
                        pass
                
                # Smart categorization
                if 'category' in column_mapping and pd.notna(row[column_mapping['category']]):
                    provided_category = str(row[column_mapping['category']]).lower()
                    valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
                    category = provided_category if provided_category in valid_categories else smart_categorize(title, description)
                else:
                    category = smart_categorize(title, description)
                
                # Track categorization
                if category not in categories_assigned:
                    categories_assigned[category] = []
                categories_assigned[category].append(title)
                
                expense_data = {
                    'title': title,
                    'amount': amount,
                    'category': category,
                    'description': description if description else None,
                    'date': expense_date
                }
                
                expense_obj = Expense(**expense_data)
                expense_doc = expense_obj.dict()
                expense_doc['created_at'] = expense_obj.created_at.isoformat()
                
                await db.expenses.insert_one(expense_doc)
                expenses_added += 1
                
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        return {
            "message": f"Successfully imported {expenses_added} expenses",
            "total_rows": len(df),
            "imported": expenses_added,
            "errors": errors,
            "auto_categorization": categories_assigned,
            "detected_columns": column_mapping
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel: {str(e)}")

# Enhanced PDF processing with smart extraction
@api_router.post("/upload/pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    try:
        contents = await file.read()
        pdf_reader = PdfReader(io.BytesIO(contents))
        
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        
        # Enhanced expense extraction for Turkish bank statements
        extracted_expenses = []
        
        # Split text into lines for better processing
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Look for patterns with amount and merchant
            # Pattern: Date Merchant Amount
            amount_pattern = r'(\d+[.,]\d{2})\s*(?:TL|₺|EUR|USD)?'
            
            amounts = re.findall(amount_pattern, line)
            if amounts:
                for amount_str in amounts:
                    try:
                        amount = float(amount_str.replace(',', '.'))
                        if amount > 0:
                            # Extract potential merchant name (text before amount)
                            before_amount = line.split(amount_str)[0].strip()
                            
                            # Clean up merchant name
                            merchant = re.sub(r'^\d+/\d+/\d+', '', before_amount).strip()  # Remove dates
                            merchant = re.sub(r'^\d+\.\d+\.\d+', '', merchant).strip()
                            merchant = re.sub(r'[*]+', '', merchant).strip()  # Remove asterisks
                            
                            if len(merchant) > 3 and len(merchant) < 100:
                                # Smart categorization
                                category = smart_categorize(merchant)
                                
                                extracted_expenses.append({
                                    'title': merchant,
                                    'amount': amount,
                                    'category': category,
                                    'description': f"PDF'den çıkarılan: {file.filename}",
                                    'date': date.today().isoformat()
                                })
                    except ValueError:
                        continue
        
        # If auto-add is requested, add expenses
        expenses_added = 0
        if extracted_expenses:
            categories_assigned = {}
            for expense_data in extracted_expenses[:20]:  # Limit to 20 expenses
                try:
                    expense_obj = Expense(**expense_data)
                    expense_doc = expense_obj.dict()
                    expense_doc['created_at'] = expense_obj.created_at.isoformat()
                    
                    await db.expenses.insert_one(expense_doc)
                    expenses_added += 1
                    
                    # Track categorization
                    category = expense_data['category']
                    if category not in categories_assigned:
                        categories_assigned[category] = []
                    categories_assigned[category].append(expense_data['title'])
                    
                except Exception as e:
                    continue
        
        return {
            "message": f"PDF processed successfully. {expenses_added} expenses added automatically.",
            "filename": file.filename,
            "extracted_expenses": len(extracted_expenses),
            "auto_added": expenses_added,
            "auto_categorization": categories_assigned if expenses_added > 0 else {},
            "sample_extractions": extracted_expenses[:5] if extracted_expenses else []
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")

# Include the router in the main app
app.include_router(api_router)

# Get filtered expenses with advanced search
@api_router.get("/expenses/search", response_model=List[Expense])
async def search_expenses(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = 100
):
    # Build query
    query = {}
    
    # Text search in title and description
    if search:
        search_regex = {"$regex": search, "$options": "i"}
        query["$or"] = [
            {"title": search_regex},
            {"description": search_regex}
        ]
    
    # Category filter
    if category and category != "all":
        query["category"] = category
    
    # Amount range filter
    if min_amount is not None or max_amount is not None:
        amount_filter = {}
        if min_amount is not None:
            amount_filter["$gte"] = min_amount
        if max_amount is not None:
            amount_filter["$lte"] = max_amount
        query["amount"] = amount_filter
    
    # Date range filter
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["date"] = date_filter
    
    # Execute query
    expenses = await db.expenses.find(query).sort("created_at", -1).limit(limit).to_list(limit)
    
    # Convert date strings back to datetime objects
    for expense in expenses:
        if isinstance(expense.get('created_at'), str):
            expense['created_at'] = datetime.fromisoformat(expense['created_at'])
    
    return [Expense(**expense) for expense in expenses]

# Get expense summary by filters
@api_router.get("/expenses/summary")
async def get_expense_summary(
    category: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    # Build query
    query = {}
    
    if category and category != "all":
        query["category"] = category
    
    if start_date or end_date:
        date_filter = {}
        if start_date:
            date_filter["$gte"] = start_date
        if end_date:
            date_filter["$lte"] = end_date
        query["date"] = date_filter
    
    # Get expenses
    expenses = await db.expenses.find(query).to_list(1000)
    
    # Calculate summary
    total_amount = sum(expense['amount'] for expense in expenses)
    total_count = len(expenses)
    
    # Average per day
    if start_date and end_date:
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            days = (end - start).days + 1
            avg_per_day = total_amount / days if days > 0 else 0
        except:
            avg_per_day = 0
    else:
        avg_per_day = 0
    
    # Category breakdown for filtered data
    category_breakdown = {}
    for expense in expenses:
        cat = expense['category']
        if cat not in category_breakdown:
            category_breakdown[cat] = {'total': 0, 'count': 0}
        category_breakdown[cat]['total'] += expense['amount']
        category_breakdown[cat]['count'] += 1
    
    # Add category info
    for cat_id, stats in category_breakdown.items():
        category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == cat_id), None)
        if category_info:
            stats['name'] = category_info['name']
            stats['color'] = category_info['color']
            stats['icon'] = category_info['icon']
    
    return {
        "total_amount": total_amount,
        "total_count": total_count,
        "average_per_day": avg_per_day,
        "category_breakdown": category_breakdown,
        "date_range": {
            "start_date": start_date,
            "end_date": end_date
        }
    }

# Smart expense limit tracking
@api_router.post("/expenses/limits")
async def set_expense_limit(limit_data: dict):
    """Set monthly expense limits by category"""
    # Store in database for future use
    await db.expense_limits.insert_one({
        "id": str(uuid.uuid4()),
        "limits": limit_data,
        "created_at": datetime.utcnow().isoformat()
    })
    return {"message": "Expense limits set successfully", "limits": limit_data}

@api_router.get("/expenses/limits/check")
async def check_expense_limits():
    """Check if current month expenses exceed limits"""
    # Get current month
    now = datetime.utcnow()
    month_start = now.replace(day=1).date().isoformat()
    month_end = now.replace(day=31).date().isoformat() if now.month != 12 else now.replace(month=12, day=31).date().isoformat()
    
    # Get current month expenses
    current_month_expenses = await db.expenses.find({
        "date": {"$gte": month_start, "$lte": month_end}
    }).to_list(1000)
    
    # Calculate current spending by category
    current_spending = {}
    for expense in current_month_expenses:
        category = expense['category']
        if category not in current_spending:
            current_spending[category] = 0
        current_spending[category] += expense['amount']
    
    # Get latest limits
    latest_limits = await db.expense_limits.find().sort("created_at", -1).limit(1).to_list(1)
    
    warnings = []
    if latest_limits:
        limits = latest_limits[0]['limits']
        for category, limit in limits.items():
            current = current_spending.get(category, 0)
            if current > limit:
                category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == category), None)
                warnings.append({
                    "category": category,
                    "category_name": category_info['name'] if category_info else category,
                    "icon": category_info['icon'] if category_info else '⚠️',
                    "current": current,
                    "limit": limit,
                    "exceeded_by": current - limit,
                    "percentage": (current / limit) * 100
                })
            elif current > limit * 0.8:  # 80% warning
                category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == category), None)
                warnings.append({
                    "category": category,
                    "category_name": category_info['name'] if category_info else category,
                    "icon": category_info['icon'] if category_info else '⚠️',
                    "current": current,
                    "limit": limit,
                    "warning_type": "approaching_limit",
                    "percentage": (current / limit) * 100
                })
    
    return {
        "current_spending": current_spending,
        "warnings": warnings,
        "month": f"{now.strftime('%B %Y')}",
        "total_spent": sum(current_spending.values())
    }

# Expense predictions based on historical data
@api_router.get("/expenses/predictions")
async def get_expense_predictions():
    """Predict next month expenses based on historical data"""
    # Get last 3 months of data
    now = datetime.utcnow()
    three_months_ago = (now.replace(day=1) - timedelta(days=90)).date().isoformat()
    
    expenses = await db.expenses.find({
        "date": {"$gte": three_months_ago}
    }).to_list(1000)
    
    # Group by month and category
    monthly_data = {}
    for expense in expenses:
        try:
            expense_date = datetime.fromisoformat(expense['date'])
            month_key = expense_date.strftime("%Y-%m")
            category = expense['category']
            
            if month_key not in monthly_data:
                monthly_data[month_key] = {}
            if category not in monthly_data[month_key]:
                monthly_data[month_key][category] = 0
            
            monthly_data[month_key][category] += expense['amount']
        except:
            continue
    
    # Calculate averages for predictions
    predictions = {}
    for category_id, category_info in [(cat['id'], cat) for cat in EXPENSE_CATEGORIES]:
        category_totals = []
        for month_data in monthly_data.values():
            category_totals.append(month_data.get(category_id, 0))
        
        if category_totals:
            avg_amount = sum(category_totals) / len(category_totals)
            # Add 10% growth factor
            predicted_amount = avg_amount * 1.1
            
            predictions[category_id] = {
                "category_name": category_info['name'],
                "icon": category_info['icon'],
                "predicted_amount": round(predicted_amount, 2),
                "historical_average": round(avg_amount, 2),
                "confidence": min(len(category_totals) * 33.33, 100)  # Higher confidence with more data
            }
    
    return {
        "predictions": predictions,
        "prediction_month": (now.replace(day=1) + timedelta(days=32)).strftime("%B %Y"),
        "based_on_months": len(monthly_data)
    }

# Smart insights and recommendations
@api_router.get("/expenses/insights")
async def get_smart_insights():
    """Generate smart insights about spending patterns"""
    # Get last month's data
    now = datetime.utcnow()
    last_month = (now.replace(day=1) - timedelta(days=1))
    last_month_start = last_month.replace(day=1).date().isoformat()
    last_month_end = last_month.date().isoformat()
    
    # Get current month's data
    current_month_start = now.replace(day=1).date().isoformat()
    current_month_end = now.date().isoformat()
    
    # Fetch data
    last_month_expenses = await db.expenses.find({
        "date": {"$gte": last_month_start, "$lte": last_month_end}
    }).to_list(1000)
    
    current_month_expenses = await db.expenses.find({
        "date": {"$gte": current_month_start, "$lte": current_month_end}
    }).to_list(1000)
    
    insights = []
    
    # Calculate totals
    last_month_total = sum(exp['amount'] for exp in last_month_expenses)
    current_month_total = sum(exp['amount'] for exp in current_month_expenses)
    
    # Progress comparison
    days_in_current_month = now.day
    days_in_last_month = (last_month.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    days_in_last_month = days_in_last_month.day
    
    projected_current_month = (current_month_total / days_in_current_month) * days_in_last_month
    
    if projected_current_month > last_month_total * 1.2:
        insights.append({
            "type": "warning",
            "title": "⚠️ Yüksek Harcama Trendi",
            "message": f"Bu ay geçen aya göre %{((projected_current_month - last_month_total) / last_month_total * 100):.0f} daha fazla harcama yapabilirsiniz.",
            "suggestion": "Harcamalarınızı gözden geçirin ve gereksiz harcamaları azaltın."
        })
    elif projected_current_month < last_month_total * 0.8:
        insights.append({
            "type": "success",
            "title": "✅ Harika İlerleme",
            "message": f"Bu ay geçen aya göre %{((last_month_total - projected_current_month) / last_month_total * 100):.0f} daha az harcama yapıyorsunuz.",
            "suggestion": "Bu tasarruf trendini sürdürün!"
        })
    
    # Category analysis
    current_categories = {}
    for exp in current_month_expenses:
        cat = exp['category']
        current_categories[cat] = current_categories.get(cat, 0) + exp['amount']
    
    last_categories = {}
    for exp in last_month_expenses:
        cat = exp['category']
        last_categories[cat] = last_categories.get(cat, 0) + exp['amount']
    
    # Find biggest spending category
    if current_categories:
        biggest_category = max(current_categories, key=current_categories.get)
        category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == biggest_category), None)
        if category_info:
            insights.append({
                "type": "info",
                "title": f"{category_info['icon']} En Çok Harcama: {category_info['name']}",
                "message": f"Bu ay en çok {category_info['name']} kategorisinde {formatCurrency(current_categories[biggest_category])} harcadınız.",
                "suggestion": f"{category_info['name']} harcamalarınızı optimize etmeyi düşünün."
            })
    
    # Unusual spending pattern
    for category, current_amount in current_categories.items():
        last_amount = last_categories.get(category, 0)
        if last_amount > 0 and current_amount > last_amount * 2:
            category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == category), None)
            if category_info:
                insights.append({
                    "type": "warning",
                    "title": f"📈 {category_info['name']} Harcamalarında Artış",
                    "message": f"Bu kategoride geçen aya göre %{((current_amount - last_amount) / last_amount * 100):.0f} artış var.",
                    "suggestion": f"{category_info['name']} harcamalarınızı kontrol edin."
                })
    
    return {
        "insights": insights,
        "summary": {
            "last_month_total": last_month_total,
            "current_month_total": current_month_total,
            "projected_total": projected_current_month,
            "trend": "increasing" if projected_current_month > last_month_total else "decreasing"
        }
    }

def formatCurrency(amount):
    return f"₺{amount:,.2f}"

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()