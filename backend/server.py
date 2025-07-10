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
from datetime import datetime, date
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
                amount_str = str(row[column_mapping['amount']]).replace(',', '.').replace(' ', '')
                # Remove currency symbols
                amount_str = ''.join(char for char in amount_str if char.isdigit() or char in '.-')
                amount = abs(float(amount_str))  # Take absolute value for expenses
                
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
                    
                if isinstance(amount_val, str):
                    amount_str = amount_val.replace(',', '.').replace(' ', '')
                    amount_str = ''.join(char for char in amount_str if char.isdigit() or char in '.-')
                    amount = abs(float(amount_str))
                else:
                    amount = abs(float(amount_val))
                
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