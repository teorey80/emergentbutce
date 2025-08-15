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
    
    projected_current_month = (current_month_total / days_in_current_month) * days_in_last_month if days_in_current_month > 0 else 0
    
    if last_month_total > 0 and projected_current_month > last_month_total * 1.2:
        insights.append({
            "type": "warning",
            "title": "Yüksek Harcama Uyarısı",
            "message": f"Bu ay geçen aya göre %{((projected_current_month/last_month_total-1)*100):.0f} daha fazla harcama yapma eğilimindesiniz.",
            "icon": "⚠️",
            "priority": "high"
        })
    elif last_month_total > 0 and projected_current_month < last_month_total * 0.8:
        insights.append({
            "type": "success",
            "title": "Tasarruf Başarısı",
            "message": f"Bu ay geçen aya göre %{((1-projected_current_month/last_month_total)*100):.0f} daha az harcama yapıyorsunuz. Tebrikler!",
            "icon": "🎉",
            "priority": "medium"
        })
    
    # Category analysis
    current_categories = {}
    for expense in current_month_expenses:
        cat = expense['category']
        current_categories[cat] = current_categories.get(cat, 0) + expense['amount']
    
    # Find highest spending categories
    if current_categories:
        top_category = max(current_categories.items(), key=lambda x: x[1])
        category_info = next((cat for cat in EXPENSE_CATEGORIES if cat['id'] == top_category[0]), None)
        if category_info:
            insights.append({
                "type": "info",
                "title": "En Çok Harcama",
                "message": f"Bu ay en çok {category_info['name']} kategorisinde ₺{top_category[1]:.2f} harcadınız.",
                "icon": category_info['icon'],
                "priority": "low"
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

# Get filtered expenses with advanced search  
@api_router.get("/expenses/filter")
async def filter_expenses(
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
    
    # Execute query and convert to list
    expenses_cursor = db.expenses.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    expenses = await expenses_cursor.to_list(limit)
    
    # Convert date strings back to datetime objects
    result_expenses = []
    for expense in expenses:
        try:
            if isinstance(expense.get('created_at'), str):
                expense['created_at'] = datetime.fromisoformat(expense['created_at'])
            result_expenses.append(Expense(**expense))
        except Exception as e:
            # Skip invalid records
            continue
    
    return result_expenses

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
                
                # Clean title - remove amounts, dates, and bonus/miles text
                # Remove common patterns that indicate amounts or bonuses
                title = re.sub(r'\d+[.,]\d{2}.*', '', title)  # Remove amounts at end
                title = re.sub(r'.*mil.*', '', title, flags=re.IGNORECASE)  # Remove miles
                title = re.sub(r'.*bonus.*', '', title, flags=re.IGNORECASE)  # Remove bonus
                title = re.sub(r'.*puan.*', '', title, flags=re.IGNORECASE)  # Remove points
                
                # Advanced Turkish bank statement cleaning for credit cards
                # Remove KAZANILAN MAXIMIL and MAXIPUAN sections (İş Bankası format)
                title = re.sub(r'KAZANILAN\s+MAXIMIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'MAXIPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'IPTAL\s+EDILEN\s+MAXIMIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'IPTAL\s+EDILEN\s+MAXIPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                
                # Remove other common Turkish bank reward program patterns
                title = re.sub(r'WORLDPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'BONUS[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'MIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                
                # Remove installment information in Turkish format
                title = re.sub(r'\(\d+/\d+\s*TK\)', '', title)  # (1/3 TK) format
                title = re.sub(r'\d+/\d+\s*TK', '', title)  # 1/3 TK format
                title = re.sub(r'\d+/\d+.*', '', title)  # Remove installment info
                title = re.sub(r'\(\d+/\d+.*\)', '', title)  # Remove installment in parentheses
                
                # Remove dates and extra text
                title = re.sub(r'^\d+[./]\d+[./]\d+', '', title)  # Remove dates at start
                title = re.sub(r'\d+\s*USD', '', title)  # Remove USD amounts
                title = re.sub(r'[\d,]+\s*TL', '', title)  # Remove TL amounts in description
                
                # Clean up location codes (TR, DE, GB etc)
                title = re.sub(r'\s+[A-Z]{2}\s*$', '', title)  # Remove country codes at end
                
                # Clean extra spaces and characters
                title = re.sub(r'\s+', ' ', title).strip()  # Clean extra spaces
                title = re.sub(r'^[*\-\s]+|[*\-\s]+$', '', title)  # Remove leading/trailing special chars
                
                # Skip if title becomes too short or empty
                if len(title) < 3:
                    continue
                
                # Enhanced amount extraction for Turkish bank statements
                amount_val = row[column_mapping['amount']]
                if pd.isna(amount_val):
                    continue
                
                # Handle different amount formats - Turkish bank specific
                amount_str = str(amount_val).strip()
                
                # Skip if the amount looks like a points/bonus value from description leak
                if 'MAXIMIL' in str(row[column_mapping['title']]).upper() or 'MAXIPUAN' in str(row[column_mapping['title']]).upper():
                    # If description contains points info, be more careful with amount validation
                    # Use simplified validation - just check if it's a very small number
                    test_amount_str = str(amount_val).replace('-', '').replace('+', '').strip()
                    
                    # Try simple validation first - convert common Turkish patterns
                    try:
                        # Simple pattern matching for obviously small amounts
                        if test_amount_str in ['0,46', '3,09', '1,28', '0,15', '0,16']:
                            continue  # Skip obvious point values
                        # Only check simple decimal formats for small amounts
                        elif len(test_amount_str) <= 4 and '.' not in test_amount_str and ',' in test_amount_str:
                            # Simple Turkish decimal format like "3,09"
                            try:
                                simple_amount = float(test_amount_str.replace(',', '.'))
                                if simple_amount < 10:
                                    continue  # Skip small amounts that are likely points
                            except:
                                pass  # If parsing fails, let main logic handle it
                    except:
                        pass  # If validation fails, let the main parsing handle it
                    
                    # For larger/complex numbers with reward patterns, let main parsing decide
                
                # Remove currency symbols and negative signs for processing
                amount_str = re.sub(r'[₺TL]', '', amount_str)  # Remove currency symbols
                is_negative = '-' in amount_str or '+' not in amount_str  # Most expenses are negative/without +
                amount_str = amount_str.replace('-', '').replace('+', '').strip()
                
                # Handle Turkish number format variations
                if ',' in amount_str and '.' in amount_str:
                    # Format like: 1.234,50 OR 1,234.50
                    if amount_str.rfind(',') > amount_str.rfind('.'):
                        # Format: 1.234,50 (German/Turkish style)
                        parts = amount_str.split(',')
                        if len(parts) == 2 and len(parts[1]) == 2:  # Has decimal part
                            amount_str = parts[0].replace('.', '') + '.' + parts[1]
                        else:
                            amount_str = amount_str.replace(',', '')
                    else:
                        # Format: 1,234.50 (US style)
                        amount_str = amount_str.replace(',', '')
                elif ',' in amount_str and '.' not in amount_str:
                    # Format: 234,50 (Turkish decimal style)
                    if len(amount_str.split(',')[1]) == 2:  # Has decimal part
                        amount_str = amount_str.replace(',', '.')
                    else:
                        amount_str = amount_str.replace(',', '')  # Thousands separator
                elif '.' in amount_str and ',' not in amount_str:
                    # Could be decimal (234.50) or thousands (1.234)
                    decimal_part = amount_str.split('.')[-1]
                    if len(decimal_part) == 2:
                        pass  # Keep as is - it's decimal
                    else:
                        amount_str = amount_str.replace('.', '')  # It's thousands separator
                
                # Clean any remaining spaces and extract numeric value
                amount_str = re.sub(r'\s+', '', amount_str)
                amount_match = re.search(r'^(\d+\.?\d*)$', amount_str)
                
                if amount_match:
                    try:
                        amount = float(amount_match.group(1))
                        # Ensure reasonable amount range for expenses
                        if amount < 0.5:  # Less than 50 kuruş, likely a points value
                            continue
                        if amount > 100000:  # More than 100k TL, might be a balance or error
                            if amount > 1000000:  # More than 1M, definitely skip
                                continue
                    except ValueError:
                        continue
                else:
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
        # Try to read Excel file with different engines
        try:
            # First try with openpyxl (for .xlsx files)
            df = pd.read_excel(io.BytesIO(contents), engine='openpyxl')
        except Exception as e1:
            try:
                # Then try with xlrd (for .xls files)
                df = pd.read_excel(io.BytesIO(contents), engine='xlrd')
            except Exception as e2:
                try:
                    # Finally try with default engine
                    df = pd.read_excel(io.BytesIO(contents))
                except Exception as e3:
                    raise HTTPException(status_code=400, detail=f"Could not read Excel file. Tried openpyxl: {str(e1)}, xlrd: {str(e2)}, default: {str(e3)}")
        
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
                
                # Clean title - remove amounts, dates, and bonus/miles text
                # Remove common patterns that indicate amounts or bonuses
                title = re.sub(r'\d+[.,]\d{2}.*', '', title)  # Remove amounts at end
                title = re.sub(r'.*mil.*', '', title, flags=re.IGNORECASE)  # Remove miles
                title = re.sub(r'.*bonus.*', '', title, flags=re.IGNORECASE)  # Remove bonus
                title = re.sub(r'.*puan.*', '', title, flags=re.IGNORECASE)  # Remove points
                
                # Advanced Turkish bank statement cleaning for credit cards
                # Remove KAZANILAN MAXIMIL and MAXIPUAN sections (İş Bankası format)
                title = re.sub(r'KAZANILAN\s+MAXIMIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'MAXIPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'IPTAL\s+EDILEN\s+MAXIMIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'IPTAL\s+EDILEN\s+MAXIPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                
                # Remove other common Turkish bank reward program patterns
                title = re.sub(r'WORLDPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'BONUS[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                title = re.sub(r'MIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
                
                # Remove installment information in Turkish format
                title = re.sub(r'\(\d+/\d+\s*TK\)', '', title)  # (1/3 TK) format
                title = re.sub(r'\d+/\d+\s*TK', '', title)  # 1/3 TK format
                title = re.sub(r'\d+/\d+.*', '', title)  # Remove installment info
                title = re.sub(r'\(\d+/\d+.*\)', '', title)  # Remove installment in parentheses
                
                # Remove dates and extra text
                title = re.sub(r'^\d+[./]\d+[./]\d+', '', title)  # Remove dates at start
                title = re.sub(r'\d+\s*USD', '', title)  # Remove USD amounts
                title = re.sub(r'[\d,]+\s*TL', '', title)  # Remove TL amounts in description
                
                # Clean up location codes (TR, DE, GB etc)
                title = re.sub(r'\s+[A-Z]{2}\s*$', '', title)  # Remove country codes at end
                
                # Clean extra spaces and characters
                title = re.sub(r'\s+', ' ', title).strip()  # Clean extra spaces
                title = re.sub(r'^[*\-\s]+|[*\-\s]+$', '', title)  # Remove leading/trailing special chars
                
                # Skip if title becomes too short or empty
                if len(title) < 3:
                    continue
                
                # Enhanced amount extraction for Turkish bank statements
                amount_val = row[column_mapping['amount']]
                if pd.isna(amount_val):
                    continue
                    
                # Handle different amount formats - Turkish bank specific
                amount_str = str(amount_val).strip()
                
                # Skip if the amount looks like a points/bonus value from description leak
                if 'MAXIMIL' in str(row[column_mapping['title']]).upper() or 'MAXIPUAN' in str(row[column_mapping['title']]).upper():
                    # If description contains points info, be more careful with amount validation
                    # Use simplified validation - just check if it's a very small number
                    test_amount_str = str(amount_val).replace('-', '').replace('+', '').strip()
                    
                    # Try simple validation first - convert common Turkish patterns
                    try:
                        # Simple pattern matching for obviously small amounts
                        if test_amount_str in ['0,46', '3,09', '1,28', '0,15', '0,16'] or \
                           (len(test_amount_str) <= 4 and float(test_amount_str.replace(',', '.')) < 10):
                            continue  # Skip obvious point values
                    except:
                        pass  # If validation fails, let the main parsing handle it
                    
                    # For larger/complex numbers with reward patterns, let main parsing decide
                
                # Remove currency symbols and negative signs for processing
                amount_str = re.sub(r'[₺TL]', '', amount_str)  # Remove currency symbols
                is_negative = '-' in amount_str or '+' not in amount_str  # Most expenses are negative/without +
                amount_str = amount_str.replace('-', '').replace('+', '').strip()
                
                # Handle Turkish number format variations
                if ',' in amount_str and '.' in amount_str:
                    # Format like: 1.234,50 OR 1,234.50
                    if amount_str.rfind(',') > amount_str.rfind('.'):
                        # Format: 1.234,50 (German/Turkish style)
                        parts = amount_str.split(',')
                        if len(parts) == 2 and len(parts[1]) == 2:  # Has decimal part
                            amount_str = parts[0].replace('.', '') + '.' + parts[1]
                        else:
                            amount_str = amount_str.replace(',', '')
                    else:
                        # Format: 1,234.50 (US style)
                        amount_str = amount_str.replace(',', '')
                elif ',' in amount_str and '.' not in amount_str:
                    # Format: 234,50 (Turkish decimal style)
                    if len(amount_str.split(',')[1]) == 2:  # Has decimal part
                        amount_str = amount_str.replace(',', '.')
                    else:
                        amount_str = amount_str.replace(',', '')  # Thousands separator
                elif '.' in amount_str and ',' not in amount_str:
                    # Could be decimal (234.50) or thousands (1.234)
                    decimal_part = amount_str.split('.')[-1]
                    if len(decimal_part) == 2:
                        pass  # Keep as is - it's decimal
                    else:
                        amount_str = amount_str.replace('.', '')  # It's thousands separator
                
                # Clean any remaining spaces and extract numeric value
                amount_str = re.sub(r'\s+', '', amount_str)
                amount_match = re.search(r'^(\d+\.?\d*)$', amount_str)
                
                if amount_match:
                    try:
                        amount = float(amount_match.group(1))
                        # Ensure reasonable amount range for expenses
                        if amount < 0.5:  # Less than 50 kuruş, likely a points value
                            continue
                        if amount > 100000:  # More than 100k TL, might be a balance or error
                            if amount > 1000000:  # More than 1M, definitely skip
                                continue
                    except ValueError:
                        continue
                else:
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
        
        # Enhanced expense extraction specifically for Turkish bank credit card statements
        extracted_expenses = []
        
        # Split text into lines for better processing
        lines = text.split('\n')
        
        # Look for table-like structures typical in Turkish bank statements
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Skip header and footer lines
            if any(skip_word in line.upper() for skip_word in ['ISLEM TARIHI', 'ACIKLAMA', 'TUTAR', 'HESAP OZETI', 'SON ODEME']):
                continue
            
            # Look for lines that match Turkish credit card statement pattern:
            # DATE | DESCRIPTION (with KAZANILAN MAXIMIL:X.XX MAXIPUAN:X.XX) | AMOUNT
            
            # Pattern for Turkish bank credit card lines
            # Example: "25.02.2025 METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46 1,544.14-"
            turkish_line_pattern = r'(\d{1,2}[./]\d{1,2}[./]\d{4})\s+(.*?)\s+([\d,.-]+)\s*$'
            match = re.match(turkish_line_pattern, line)
            
            if match:
                date_str, description, amount_str = match.groups()
                
                # Clean the description - remove points and rewards info
                clean_description = description
                
                # Apply the same cleaning logic as CSV/Excel
                # Remove KAZANILAN MAXIMIL and MAXIPUAN sections
                clean_description = re.sub(r'KAZANILAN\s+MAXIMIL[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                clean_description = re.sub(r'MAXIPUAN[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                clean_description = re.sub(r'IPTAL\s+EDILEN\s+MAXIMIL[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                clean_description = re.sub(r'IPTAL\s+EDILEN\s+MAXIPUAN[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                
                # Remove other reward patterns
                clean_description = re.sub(r'WORLDPUAN[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                clean_description = re.sub(r'BONUS[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                clean_description = re.sub(r'MIL[:\s]*[\d,]+', '', clean_description, flags=re.IGNORECASE)
                
                # Remove installment info
                clean_description = re.sub(r'\(\d+/\d+\s*TK\)', '', clean_description)
                clean_description = re.sub(r'\d+/\d+\s*TK', '', clean_description)
                
                # Remove location codes and extra text
                clean_description = re.sub(r'\s+[A-Z]{2}\s*$', '', clean_description)
                clean_description = re.sub(r'[\d,]+\s*TL', '', clean_description)
                
                # Clean up
                clean_description = re.sub(r'\s+', ' ', clean_description).strip()
                clean_description = re.sub(r'^[*\-\s]+|[*\-\s]+$', '', clean_description)
                
                # Skip if description becomes too short
                if len(clean_description) < 3:
                    continue
                
                # Parse amount - handle Turkish format
                try:
                    # Remove currency and negative signs
                    amount_clean = amount_str.replace('-', '').replace('+', '').replace('TL', '').replace('₺', '').strip()
                    
                    # Handle Turkish decimal format (1.544,14 or 1,544.14)
                    if ',' in amount_clean and '.' in amount_clean:
                        if amount_clean.rfind(',') > amount_clean.rfind('.'):
                            # Format: 1.544,14
                            parts = amount_clean.split(',')
                            if len(parts) == 2 and len(parts[1]) == 2:
                                amount_clean = parts[0].replace('.', '') + '.' + parts[1]
                        else:
                            # Format: 1,544.14
                            amount_clean = amount_clean.replace(',', '')
                    elif ',' in amount_clean:
                        # Only comma - could be decimal (234,50) or thousands (1,544)
                        parts = amount_clean.split(',')
                        if len(parts) == 2 and len(parts[1]) == 2:
                            amount_clean = amount_clean.replace(',', '.')  # Decimal
                        else:
                            amount_clean = amount_clean.replace(',', '')  # Thousands
                    
                    amount = float(amount_clean)
                    
                    # Skip very small amounts (likely points) or unrealistic amounts
                    if amount < 1.0 or amount > 100000:
                        continue
                    
                    # Parse date
                    try:
                        expense_date = datetime.strptime(date_str.replace('.', '/'), '%d/%m/%Y').date().isoformat()
                    except:
                        expense_date = date.today().isoformat()
                    
                    # Smart categorization
                    category = smart_categorize(clean_description)
                    
                    extracted_expenses.append({
                        'title': clean_description,
                        'amount': amount,
                        'category': category,
                        'description': f"PDF'den çıkarılan: {file.filename}",
                        'date': expense_date
                    })
                    
                except (ValueError, IndexError):
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

# Simple filter test endpoint
@api_router.get("/test/filter")
async def test_filter_expenses(min_amount: Optional[float] = None, max_amount: Optional[float] = None):
    # Build simple query
    query = {}
    
    if min_amount is not None or max_amount is not None:
        amount_filter = {}
        if min_amount is not None:
            amount_filter["$gte"] = min_amount
        if max_amount is not None:
            amount_filter["$lte"] = max_amount
        query["amount"] = amount_filter
    
    print(f"Test Query: {query}")
    
    # Execute query
    expenses = await db.expenses.find(query).limit(10).to_list(10)
    
    print(f"Test Found: {len(expenses)} expenses")
    
    return {
        "query": query,
        "count": len(expenses),
        "sample": expenses[:3] if expenses else []
    }

# Update expense category
@api_router.put("/expenses/{expense_id}/category")
async def update_expense_category(expense_id: str, category_data: dict):
    """Update only the category of an expense"""
    new_category = category_data.get('category')
    
    # Validate category
    valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
    if new_category not in valid_categories:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Update expense
    result = await db.expenses.update_one(
        {"id": expense_id}, 
        {"$set": {"category": new_category}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    # Get updated expense
    updated_expense = await db.expenses.find_one({"id": expense_id})
    if isinstance(updated_expense.get('created_at'), str):
        updated_expense['created_at'] = datetime.fromisoformat(updated_expense['created_at'])
    
    return Expense(**updated_expense)

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

# Include the router in the main app (MUST be after all endpoint definitions)
app.include_router(api_router)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()