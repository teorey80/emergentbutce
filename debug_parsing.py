import pandas as pd
import io
import re

def debug_turkish_parsing():
    """Debug the Turkish number parsing logic"""
    
    # Test the exact case
    csv_content = """description,amount,date
METRO UMRANIYE TEKEL ISTANBUL TR KAZANILAN MAXIMIL:3,09 MAXIPUAN:0,46,1.544,14,2024-01-15"""
    
    df = pd.read_csv(io.StringIO(csv_content))
    
    # Map columns
    column_mapping = {
        'title': 'description',
        'amount': 'amount',
        'date': 'date'
    }
    
    for index, row in df.iterrows():
        print(f"Processing row {index}:")
        
        # Extract title
        title = str(row[column_mapping['title']]).strip()
        print(f"  Original title: {title}")
        
        # Clean title
        title = re.sub(r'KAZANILAN\s+MAXIMIL[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'MAXIPUAN[:\s]*[\d,]+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s+[A-Z]{2}\s*$', '', title)
        title = re.sub(r'\s+', ' ', title).strip()
        title = re.sub(r'^[*\-\s]+|[*\-\s]+$', '', title)
        print(f"  Cleaned title: {title}")
        
        if len(title) < 3:
            print(f"  ❌ Title too short: {len(title)}")
            continue
        
        # Extract amount
        amount_val = row[column_mapping['amount']]
        print(f"  Original amount: {amount_val} (type: {type(amount_val)})")
        
        if pd.isna(amount_val):
            print(f"  ❌ Amount is NaN")
            continue
        
        amount_str = str(amount_val).strip()
        print(f"  Amount string: '{amount_str}'")
        
        # Check MAXIMIL/MAXIPUAN validation
        if 'MAXIMIL' in str(row[column_mapping['title']]).upper() or 'MAXIPUAN' in str(row[column_mapping['title']]).upper():
            print(f"  🎯 Contains MAXIMIL/MAXIPUAN - applying validation")
            test_amount_str = str(amount_val).replace('-', '').replace('+', '').strip()
            print(f"  Test amount string: '{test_amount_str}'")
            
            try:
                # Check if it's in the hardcoded list
                if test_amount_str in ['0,46', '3,09', '1,28', '0,15', '0,16']:
                    print(f"  ❌ In hardcoded small amounts list - FILTERED")
                    continue
                
                # Check the problematic condition
                if len(test_amount_str) <= 4 and '.' not in test_amount_str:
                    print(f"  Length <= 4 and no period: {len(test_amount_str) <= 4} and {('.' not in test_amount_str)}")
                    try:
                        simple_amount = float(test_amount_str.replace(',', '.'))
                        print(f"  Simple amount conversion: {simple_amount}")
                        if simple_amount < 10:
                            print(f"  ❌ Simple amount < 10 - FILTERED")
                            continue
                        else:
                            print(f"  ✅ Simple amount >= 10 - PASSED validation")
                    except Exception as e:
                        print(f"  ⚠️ Simple amount conversion failed: {e}")
                else:
                    print(f"  ✅ Length > 4 or has period - PASSED validation")
                    
            except Exception as e:
                print(f"  ⚠️ Validation exception: {e}")
        
        # Main parsing logic
        print(f"  🔧 Starting main parsing logic")
        
        # Remove currency symbols
        amount_str = re.sub(r'[₺TL]', '', amount_str)
        amount_str = amount_str.replace('-', '').replace('+', '').strip()
        print(f"  After currency removal: '{amount_str}'")
        
        # Handle Turkish number format variations
        if ',' in amount_str and '.' in amount_str:
            print(f"  Has both comma and period")
            if amount_str.rfind(',') > amount_str.rfind('.'):
                print(f"  Turkish format: 1.234,50")
                parts = amount_str.split(',')
                print(f"  Parts: {parts}")
                if len(parts) == 2 and len(parts[1]) == 2:
                    amount_str = parts[0].replace('.', '') + '.' + parts[1]
                    print(f"  Converted to: '{amount_str}'")
                else:
                    amount_str = amount_str.replace(',', '')
                    print(f"  Removed commas: '{amount_str}'")
            else:
                print(f"  US format: 1,234.50")
                amount_str = amount_str.replace(',', '')
                print(f"  Removed commas: '{amount_str}'")
        elif ',' in amount_str and '.' not in amount_str:
            print(f"  Only comma - Turkish decimal or thousands")
            parts = amount_str.split(',')
            if len(parts) == 2 and len(parts[1]) == 2:
                print(f"  Turkish decimal: {amount_str}")
                amount_str = amount_str.replace(',', '.')
                print(f"  Converted to: '{amount_str}'")
            else:
                print(f"  Thousands separator")
                amount_str = amount_str.replace(',', '')
                print(f"  Removed comma: '{amount_str}'")
        elif '.' in amount_str and ',' not in amount_str:
            print(f"  Only period")
            decimal_part = amount_str.split('.')[-1]
            if len(decimal_part) == 2:
                print(f"  Decimal format: '{amount_str}'")
            else:
                print(f"  Thousands separator")
                amount_str = amount_str.replace('.', '')
                print(f"  Removed period: '{amount_str}'")
        
        # Final parsing
        amount_str = re.sub(r'\s+', '', amount_str)
        print(f"  Final amount string: '{amount_str}'")
        
        amount_match = re.search(r'^(\d+\.?\d*)$', amount_str)
        if amount_match:
            try:
                amount = float(amount_match.group(1))
                print(f"  ✅ Successfully parsed amount: {amount}")
                
                if amount < 0.5:
                    print(f"  ❌ Amount too small (< 0.5): FILTERED")
                    continue
                elif amount > 100000:
                    print(f"  ❌ Amount too large (> 100k): FILTERED")
                    continue
                else:
                    print(f"  ✅ Amount in valid range: {amount}")
                    print(f"  🎉 TRANSACTION WOULD BE IMPORTED!")
                    
            except ValueError as e:
                print(f"  ❌ Float conversion failed: {e}")
                continue
        else:
            print(f"  ❌ Regex match failed for: '{amount_str}'")
            continue

if __name__ == "__main__":
    debug_turkish_parsing()