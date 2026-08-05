import pandas as pd
import re

# Path to your new Excel file
excel_path = "Restaurant Menu Price Recipe 2026sheet.xlsx"

all_recipes = []

print("Scanning Excel sheets and grouping by Buffet type...")

# Read all sheet names
xl = pd.ExcelFile(excel_path)

for sheet_name in xl.sheet_names:
    display_name = None
    
    # Convert to lowercase for easier matching
    s_name_lower = sheet_name.lower()

    # --- AUTOMATIC BUFFET NAMING LOGIC (Fixed logic) ---
    
    # 1. Asian Buffet
    if "asian" in s_name_lower:
        display_name = "Asian Buffet"

    # 2. Chef's Choice (Must check BEFORE generic 'choice' or 'dinner' words)
    elif "chef" in s_name_lower:
        if "dinner" in s_name_lower:
            display_name = "Chef's Choice Buffet (Dinner)"
        else:
            display_name = "Chef's Choice Buffet (Lunch)"

    # 3. Indian Buffet (Must check before generic 'buffet' or 'dinner')
    elif "indian" in s_name_lower:
        if "dinner" in s_name_lower:
            display_name = "Indian Buffet (Dinner)"
        else:
            display_name = "Indian Buffet (Lunch)"

    # 4. Middle Eastern Buffet
    elif "middle east" in s_name_lower:
        if "dinner" in s_name_lower:
            display_name = "Middle Eastern Buffet (Dinner)"
        else:
            display_name = "Middle Eastern Buffet (Lunch)"

    # 5. Ethiopian Buffet / Friday Dinner
    elif "ethiopia" in s_name_lower:
        if "friday" in s_name_lower or "dinner" in s_name_lower:
            display_name = "Friday Dinner Menu"
        else:
            display_name = "Zen Ethiopia Buffet (Lunch)"

    # 6. Saturday Buffet
    elif "saturday" in s_name_lower:
        if "dinner" in s_name_lower:
            display_name = "Saturday Buffet (Dinner)"
        else:
            display_name = "Saturday Buffet (Lunch)"


    # --- PROCESS THE SHEET IF A BUFFET NAME WAS FOUND ---
    if display_name:
        print(f"✅ Found: {display_name} (from sheet '{sheet_name}')")
        
        # Read the sheet
        df = pd.read_excel(excel_path, sheet_name=sheet_name, header=None)
        
        # Loop through every row to find dishes and ingredients
        current_dish = None
        for index, row in df.iterrows():
            # Find dish names in Column B (index 1)
            raw_dish = str(row[1]) if pd.notna(row[1]) else ""
            
            if raw_dish and "Total" not in raw_dish and "Per Person" not in raw_dish and "Grand" not in raw_dish and raw_dish != "nan" and raw_dish != "Ingredients" and "Amount" not in raw_dish:
                current_dish = raw_dish.strip()

            # Find ingredients in the subsequent columns
            if current_dish:
                # Loop through the ingredient columns (C, E, G, etc.)
                for i in range(2, len(row) - 1, 2):
                    raw_ing = str(row[i]) if pd.notna(row[i]) else ""
                    raw_qty = str(row[i+1]) if pd.notna(row[i+1]) else ""
                    
                    # Skip cost columns
                    if "=" in raw_ing or "Amount" in raw_ing:
                        continue
                        
                    # Regex to match "Onion-500g" or "Chicken 150g"
                    match = re.search(r'([A-Za-z\s]+)[\-\s]+([\d\.]+)\s*(g|kg|ml|l|pc|pcs|piece)', raw_ing, re.IGNORECASE)
                    
                    if match:
                        ingredient = match.group(1).strip().capitalize()
                        quantity = float(match.group(2))
                        unit = match.group(3).lower().replace('pcs', 'pc').replace('piece', 'pc')
                        
                        if not unit and raw_qty:
                            if 'kg' in raw_qty: unit = 'kg'
                            elif 'g' in raw_qty: unit = 'g'
                            elif 'ml' in raw_qty: unit = 'ml'
                            elif 'l' in raw_qty: unit = 'l'
                            elif 'pc' in raw_qty: unit = 'pc'
                            else: unit = 'g'

                        # Save using the Display Name
                        all_recipes.append({
                            'buffet_name': display_name, 
                            'ingredient': ingredient,
                            'quantity': quantity,
                            'unit': unit
                        })

# Save the final CSV
if all_recipes:
    final_df = pd.DataFrame(all_recipes)
    final_df = final_df.drop_duplicates()
    final_df.to_csv("data/buffet_recipes.csv", index=False)
    
    print(f"\n🎉 SUCCESS! Extracted {len(final_df)} total ingredients.")
    print("\nYour Streamlit dropdown will now have ALL these options:")
    for buffet in sorted(final_df['buffet_name'].unique()):
        print(f"  - {buffet}")
else:
    print("\n❌ No buffets found.")