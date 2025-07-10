from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date
from decimal import Decimal

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
    date: Optional[date] = None
    
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data):
        if 'date' not in data or data['date'] is None:
            data['date'] = date.today()
        super().__init__(**data)

class Expense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    amount: float
    category: str
    description: Optional[str] = None
    date: date
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        arbitrary_types_allowed = True

class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    description: Optional[str] = None
    date: Optional[date] = None
    
    class Config:
        arbitrary_types_allowed = True

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
    expense_obj = Expense(**expense_dict)
    
    # Convert date to string for MongoDB
    expense_doc = expense_obj.dict()
    expense_doc['date'] = expense_obj.date.isoformat()
    expense_doc['created_at'] = expense_obj.created_at.isoformat()
    
    await db.expenses.insert_one(expense_doc)
    return expense_obj

# Get all expenses
@api_router.get("/expenses", response_model=List[Expense])
async def get_expenses():
    expenses = await db.expenses.find().sort("created_at", -1).to_list(1000)
    
    # Convert date strings back to date objects
    for expense in expenses:
        expense['date'] = datetime.fromisoformat(expense['date']).date()
        expense['created_at'] = datetime.fromisoformat(expense['created_at'])
    
    return [Expense(**expense) for expense in expenses]

# Get expense by ID
@api_router.get("/expenses/{expense_id}", response_model=Expense)
async def get_expense(expense_id: str):
    expense = await db.expenses.find_one({"id": expense_id})
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    
    expense['date'] = datetime.fromisoformat(expense['date']).date()
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
        if 'date' in update_data:
            update_data['date'] = update_data['date'].isoformat()
        await db.expenses.update_one({"id": expense_id}, {"$set": update_data})
    
    # Get updated expense
    updated_expense = await db.expenses.find_one({"id": expense_id})
    updated_expense['date'] = datetime.fromisoformat(updated_expense['date']).date()
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