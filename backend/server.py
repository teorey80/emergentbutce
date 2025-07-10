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

# File upload endpoint for CSV
@api_router.post("/upload/csv")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    try:
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Expected columns: title, amount, category, description, date
        required_columns = ['title', 'amount', 'category']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {missing_columns}")
        
        # Validate categories
        valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
        invalid_categories = df[~df['category'].isin(valid_categories)]['category'].unique()
        
        if len(invalid_categories) > 0:
            raise HTTPException(status_code=400, detail=f"Invalid categories found: {invalid_categories.tolist()}")
        
        # Process and insert expenses
        expenses_added = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                expense_data = {
                    'title': str(row['title']),
                    'amount': float(row['amount']),
                    'category': str(row['category']),
                    'description': str(row.get('description', '')) if pd.notna(row.get('description')) else None,
                    'date': str(row.get('date', date.today().isoformat())) if pd.notna(row.get('date')) else date.today().isoformat()
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
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing CSV: {str(e)}")

# File upload endpoint for Excel
@api_router.post("/upload/excel")
async def upload_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="File must be an Excel file")
    
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        
        # Expected columns: title, amount, category, description, date
        required_columns = ['title', 'amount', 'category']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise HTTPException(status_code=400, detail=f"Missing required columns: {missing_columns}")
        
        # Validate categories
        valid_categories = [cat["id"] for cat in EXPENSE_CATEGORIES]
        invalid_categories = df[~df['category'].isin(valid_categories)]['category'].unique()
        
        if len(invalid_categories) > 0:
            raise HTTPException(status_code=400, detail=f"Invalid categories found: {invalid_categories.tolist()}")
        
        # Process and insert expenses
        expenses_added = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                expense_data = {
                    'title': str(row['title']),
                    'amount': float(row['amount']),
                    'category': str(row['category']),
                    'description': str(row.get('description', '')) if pd.notna(row.get('description')) else None,
                    'date': str(row.get('date', date.today().isoformat())) if pd.notna(row.get('date')) else date.today().isoformat()
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
            "errors": errors
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing Excel: {str(e)}")

# File upload endpoint for PDF
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
        
        # Simple expense extraction (this can be improved with more sophisticated parsing)
        # Look for patterns like "Amount: 123.45" or "Total: 123.45"
        amount_patterns = [
            r'(?:Amount|Total|Toplam|Tutar):\s*(\d+[.,]\d{2})',
            r'(\d+[.,]\d{2})\s*(?:TL|₺|EUR|USD)',
            r'(\d+[.,]\d{2})'
        ]
        
        extracted_amounts = []
        for pattern in amount_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    amount = float(match.replace(',', '.'))
                    if amount > 0:
                        extracted_amounts.append(amount)
                except ValueError:
                    continue
        
        # Extract potential titles (words before amounts)
        title_patterns = [
            r'([A-Za-zğüşıöçĞÜŞİÖÇ\s]+)\s*(?:Amount|Total|Toplam|Tutar):\s*\d+[.,]\d{2}',
            r'([A-Za-zğüşıöçĞÜŞİÖÇ\s]+)\s*\d+[.,]\d{2}\s*(?:TL|₺)'
        ]
        
        extracted_titles = []
        for pattern in title_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                title = match.strip()
                if len(title) > 3 and len(title) < 50:
                    extracted_titles.append(title)
        
        # Return extracted data for user to review
        return {
            "message": "PDF processed successfully",
            "filename": file.filename,
            "extracted_text": text[:1000],  # First 1000 characters
            "potential_amounts": extracted_amounts[:10],  # First 10 amounts
            "potential_titles": extracted_titles[:10],  # First 10 titles
            "suggestion": "Review the extracted data and manually add expenses as needed"
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