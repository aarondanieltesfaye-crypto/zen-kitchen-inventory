import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from auth import require_passcode
from sheets_backend import read_sheet, write_sheet, clean_types

# Page config
st.set_page_config(
    page_title="Zen Kitchen Inventory Management",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Zen Kitchen Inventory Management")
st.markdown("---")

require_passcode()

# --- HELPER: FIX OLD CATEGORIES AND DATA ---
def _fix_legacy_categories(df):
    """
    Ensures legacy data uses the new categories and fixes known errors.
    """
    category_map = {
        'Vegetable': 'Produce',
        'Fruit': 'Produce',
        'Spices': 'Spices & Condiments',
        'Dairy': 'Dairy & Eggs'
    }
    df['category'] = df['category'].replace(category_map)

    df.loc[df['item'].str.strip() == 'Nile perch', 'category'] = 'Proteins'
    df.loc[df['item'].str.strip() == 'Nile Perch', 'category'] = 'Proteins'
    df.loc[df['item'].str.strip() == 'Nile pearch', 'category'] = 'Proteins'
    df.loc[df['item'].str.strip() == 'Egg', 'category'] = 'Dairy & Eggs'
    df.loc[df['item'].str.strip() == 'Eggs', 'category'] = 'Dairy & Eggs'

    df.loc[df['item'].str.strip() == 'Table Butter', 'category'] = 'Dairy & Eggs'
    df.loc[df['item'].str.strip() == 'Milk', 'category'] = 'Dairy & Eggs'
    df.loc[df['item'].str.strip() == 'Sugar', 'category'] = 'Dry Goods'
    df.loc[df['item'].str.strip() == 'Chicken Breast', 'category'] = 'Proteins'
    df.loc[df['item'].str.strip() == 'Beef', 'category'] = 'Proteins'
    return df

# --- DATA LOADING FUNCTIONS (Google Sheets backed) ---

@st.cache_data(ttl=30)
def load_inventory():
    df = read_sheet("inventory")
    if df.empty:
        df = pd.DataFrame({
            'item': ['Chicken Breast', 'Nile Perch', 'Eggs', 'Onion', 'Tomato', 'Milk', 'Butter', 'Flour', 'White Rice', 'Cooking Oil', 'Salt', 'Black Pepper'],
            'category': ['Proteins', 'Proteins', 'Dairy & Eggs', 'Produce', 'Produce', 'Dairy & Eggs', 'Dairy & Eggs', 'Dry Goods', 'Dry Goods', 'Dry Goods', 'Spices & Condiments', 'Spices & Condiments'],
            'unit': ['kg', 'kg', 'pc', 'kg', 'kg', 'l', 'kg', 'kg', 'kg', 'l', 'kg', 'g'],
            'quantity': [15.0, 5.0, 60.0, 20.0, 15.0, 10.0, 2.0, 25.0, 30.0, 20.0, 5.0, 500.0],
            'reorder_level': [2.0, 1.0, 12.0, 3.0, 3.0, 2.0, 0.5, 5.0, 5.0, 4.0, 1.0, 100.0]
        })
        write_sheet("inventory", df)
    df = clean_types(df, text_cols=['item', 'category', 'unit'], number_cols=['quantity', 'reorder_level'])
    df = _fix_legacy_categories(df)
    return df

@st.cache_data(ttl=30)
def load_recipes():
    df = read_sheet("recipes")
    if df.empty:
        df = pd.DataFrame({
            'recipe_name': ['Grilled Fish', 'Grilled Fish', 'Grilled Fish', 'Grilled Fish', 'Classic Omelette', 'Classic Omelette', 'Classic Omelette'],
            'ingredient': ['Nile Perch', 'Salt', 'Black Pepper', 'Cooking Oil', 'Eggs', 'Butter', 'Salt'],
            'quantity': [200.0, 5.0, 2.0, 10.0, 2.0, 5.0, 1.0],
            'unit': ['g', 'g', 'g', 'ml', 'pc', 'g', 'g']
        })
        write_sheet("recipes", df)
    df = clean_types(df, text_cols=['recipe_name', 'ingredient', 'unit'], number_cols=['quantity'])
    return df

@st.cache_data(ttl=30)
def load_buffet_recipes():
    df = read_sheet("buffet_recipes")
    if df.empty:
        df = pd.DataFrame({
            'buffet_name': ['Continental Breakfast', 'Continental Breakfast', 'Continental Breakfast', 'Continental Breakfast', 'Continental Breakfast'],
            'ingredient': ['Eggs', 'Milk', 'Butter', 'Flour', 'Salt'],
            'quantity': [1.0, 100.0, 10.0, 50.0, 1.0],
            'unit': ['pc', 'ml', 'g', 'g', 'g']
        })
        write_sheet("buffet_recipes", df)
    df = clean_types(df, text_cols=['buffet_name', 'ingredient', 'unit'], number_cols=['quantity'])
    return df

@st.cache_data(ttl=30)
def load_order_history():
    df = read_sheet("order_history")
    if df.empty:
        return pd.DataFrame(columns=['timestamp', 'item', 'quantity', 'unit'])
    df = clean_types(df, text_cols=['timestamp', 'item', 'unit'], number_cols=['quantity'])
    return df

# --- SAVE FUNCTIONS ---

def save_inventory(df):
    df = _fix_legacy_categories(df)
    write_sheet("inventory", df)

def save_recipes(df):
    write_sheet("recipes", df)

def save_buffet_recipes(df):
    write_sheet("buffet_recipes", df)

def log_order_history(ingredients_list):
    """Appends deducted ingredients to the order_history sheet."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    hist_df = read_sheet("order_history")
    if hist_df.empty:
        hist_df = pd.DataFrame(columns=['timestamp', 'item', 'quantity', 'unit'])

    new_rows = []
    for ing in ingredients_list:
        try:
            qty = float(ing['quantity'])
        except (ValueError, TypeError):
            qty = 0
        new_rows.append({
            'timestamp': now,
            'item': ing['item'],
            'quantity': qty,
            'unit': ing['unit']
        })

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        hist_df = pd.concat([hist_df, new_df], ignore_index=True)
        write_sheet("order_history", hist_df)

# --- INVENTORY DEDUCTION FUNCTION ---

def deduct_inventory(inventory_df, ingredients_list):
    """
    Deduct ingredients from inventory.
    ingredients_list: list of dicts [{'item': 'Onion', 'quantity': 100, 'unit': 'g'}, ...]
    Returns: (updated_inventory, messages, errors)
    """
    messages = []
    errors = []

    updated_df = inventory_df.copy()
    updated_df['quantity'] = updated_df['quantity'].astype(float)

    for ingredient in ingredients_list:
        item_name = ingredient['item']
        unit_needed = ingredient['unit']

        try:
            qty_str = str(ingredient['quantity']).strip()
            if not qty_str or qty_str.lower() == 'nan':
                raise ValueError
            qty_needed = float(qty_str)
        except (ValueError, TypeError):
            errors.append(f"❌ Recipe data for '{item_name}' has an invalid quantity. Fix it in Edit Data!")
            continue

        mask = updated_df['item'] == item_name
        if not mask.any():
            errors.append(f"❌ '{item_name}' not found in inventory!")
            continue

        try:
            current_qty = float(updated_df.loc[mask, 'quantity'].values[0])
        except (ValueError, TypeError):
            errors.append(f"❌ Inventory data for '{item_name}' invalid. Edit it in Edit Data!")
            continue

        current_unit = updated_df.loc[mask, 'unit'].values[0]

        if unit_needed != current_unit:
            if unit_needed == 'g' and current_unit == 'kg':
                qty_needed = qty_needed / 1000
            elif unit_needed == 'kg' and current_unit == 'g':
                qty_needed = qty_needed * 1000
            elif unit_needed == 'ml' and current_unit == 'l':
                qty_needed = qty_needed / 1000
            elif unit_needed == 'l' and current_unit == 'ml':
                qty_needed = qty_needed * 1000

        if current_qty < qty_needed:
            errors.append(f"❌ Not enough '{item_name}'. Have: {current_qty:.1f} {current_unit}, Need: {qty_needed:.1f} {unit_needed}")
            continue

        new_qty = current_qty - qty_needed
        updated_df.loc[mask, 'quantity'] = new_qty
        messages.append(f"✅ Deducted {qty_needed:.1f} {unit_needed} of '{item_name}'. Remaining: {new_qty:.1f} {current_unit}")

    return updated_df, messages, errors

# --- LOAD DATA ---

inventory_df = load_inventory()
recipes_df = load_recipes()
buffet_df = load_buffet_recipes()

st.sidebar.title("📋 Navigation")
page = st.sidebar.radio(
    "Go to:",
    ["📊 Dashboard", "📝 Take Order", "🍽️ Buffet Order", "✏️ Edit Data", "📈 Consumption Analytics"]
)

# --- PAGE 1: DASHBOARD ---
if page == "📊 Dashboard":
    st.header("📊 Inventory Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    total_items = len(inventory_df)
    total_quantity = inventory_df['quantity'].sum()
    low_stock = len(inventory_df[inventory_df['quantity'] <= inventory_df['reorder_level']])
    out_of_stock = len(inventory_df[inventory_df['quantity'] == 0])

    with col1:
        st.metric("Total Items", total_items)
    with col2:
        st.metric("Total Quantity", f"{total_quantity:.0f}")
    with col3:
        st.metric("Low Stock Items", low_stock, delta="-urgent" if low_stock > 0 else None)
    with col4:
        st.metric("Out of Stock", out_of_stock, delta="⚠️" if out_of_stock > 0 else None)

    st.markdown("---")

    if low_stock > 0:
        st.warning(f"⚠️ {low_stock} item(s) are below reorder level!")
        low_stock_items = inventory_df[inventory_df['quantity'] <= inventory_df['reorder_level']]
        st.dataframe(low_stock_items[['item', 'category', 'quantity', 'unit', 'reorder_level']])

    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Stock by Category")
        category_summary = inventory_df.groupby('category')['quantity'].sum().reset_index()
        fig = px.pie(category_summary, values='quantity', names='category', title="Inventory by Category")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 10 Items by Quantity")
        top_items = inventory_df.nlargest(10, 'quantity')
        fig = px.bar(
            top_items,
            x='item',
            y='quantity',
            color='category',
            title="Top 10 Items",
            labels={'quantity': 'Quantity'}
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("📋 Full Inventory")
    st.dataframe(inventory_df, use_container_width=True)

# --- PAGE 2: TAKE ORDER ---
elif page == "📝 Take Order":
    st.header("📝 Take Customer Order")

    available_recipes = recipes_df['recipe_name'].unique().tolist()

    if not available_recipes:
        st.warning("No recipes defined yet! Go to Edit Data to add recipes.")
    else:
        selected_recipe = st.selectbox("Select Dish", available_recipes)
        recipe_ingredients = recipes_df[recipes_df['recipe_name'] == selected_recipe]

        st.subheader(f"📋 {selected_recipe} - Ingredients")
        st.dataframe(recipe_ingredients[['ingredient', 'quantity', 'unit']])

        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            quantity = st.number_input("Number of portions", min_value=1, max_value=50, value=1, step=1)

        st.markdown("---")

        if st.button("✅ Confirm Order", type="primary"):
            ingredients_list = []
            for _, row in recipe_ingredients.iterrows():
                ingredients_list.append({
                    'item': row['ingredient'],
                    'quantity': row['quantity'] * quantity,
                    'unit': row['unit']
                })

            updated_inventory, messages, errors = deduct_inventory(inventory_df, ingredients_list)

            if errors:
                for error in errors:
                    st.error(error)
            else:
                save_inventory(updated_inventory)
                log_order_history(ingredients_list)

                st.success(f"✅ Order for {quantity}x {selected_recipe} confirmed!")
                st.balloons()
                st.subheader("📊 Inventory Updated")
                for msg in messages:
                    st.info(msg)
                st.rerun()

# --- PAGE 3: BUFFET ORDER ---
elif page == "🍽️ Buffet Order":
    st.header("🍽️ Buffet Order")

    available_buffets = buffet_df['buffet_name'].unique().tolist()

    if not available_buffets:
        st.warning("No buffet menus defined yet! Go to Edit Data to add buffet recipes.")
    else:
        selected_buffet = st.selectbox("Select Buffet Type", available_buffets)
        buffet_ingredients = buffet_df[buffet_df['buffet_name'] == selected_buffet]

        st.subheader(f"📋 {selected_buffet} - Ingredients (per person)")
        st.dataframe(buffet_ingredients[['ingredient', 'quantity', 'unit']])

        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            num_guests = st.number_input("Number of guests", min_value=1, max_value=200, value=10, step=1)

        st.markdown("---")

        if st.button("✅ Confirm Buffet Order", type="primary"):
            total_guest_ingredients = []
            for _, row in buffet_ingredients.iterrows():
                total_guest_ingredients.append({
                    'item': row['ingredient'],
                    'quantity': row['quantity'] * num_guests,
                    'unit': row['unit']
                })

            updated_inventory, messages, errors = deduct_inventory(inventory_df, total_guest_ingredients)

            if errors:
                for error in errors:
                    st.error(error)
            else:
                save_inventory(updated_inventory)
                log_order_history(total_guest_ingredients)

                st.success(f"✅ Buffet for {num_guests} guests confirmed!")
                st.balloons()
                st.subheader("📊 Inventory Updated")
                for msg in messages[:10]:
                    st.info(msg)
                st.rerun()

# --- PAGE 4: EDIT DATA ---
elif page == "✏️ Edit Data":
    st.header("✏️ Edit Data")

    tab1, tab2, tab3 = st.tabs(["📦 Inventory", "📝 Recipes", "🍽️ Buffet Recipes"])

    with tab1:
        st.subheader("📦 Edit Inventory")

        # Reliable mobile-friendly quantity updater (avoids the data_editor
        # touch-editing bug for numeric cells on phones/tablets)
        with st.container(border=True):
            st.markdown("**🔢 Quick Update Quantity**")
            st.caption("Use this on a phone — it's more reliable than tapping cells directly below.")
            if not inventory_df.empty:
                qty_item = st.selectbox("Item", inventory_df['item'].tolist(), key="qty_update_item")
                current_row = inventory_df[inventory_df['item'] == qty_item].iloc[0]
                current_qty = float(current_row['quantity'])
                st.caption(f"Current quantity: {current_qty} {current_row['unit']}")
                new_qty_value = st.number_input(
                    "New quantity", min_value=0.0, value=current_qty, step=0.1, key="qty_update_value"
                )
                if st.button("✅ Update Quantity", type="primary", key="qty_update_btn"):
                    inventory_df.loc[inventory_df['item'] == qty_item, 'quantity'] = new_qty_value
                    save_inventory(inventory_df)
                    st.success(f"✅ {qty_item} updated to {new_qty_value} {current_row['unit']}")
                    st.rerun()

        st.markdown("---")
        st.caption("💡 Full table below — best used on desktop. Double-tap a cell to edit, then use 'Save Inventory Changes'.")

        edited_inventory = st.data_editor(
            inventory_df,
            num_rows="dynamic",
            use_container_width=True,
            key="inventory_editor",
            column_config={
                "item": st.column_config.TextColumn("Item"),
                "category": st.column_config.TextColumn("Category"),
                "unit": st.column_config.TextColumn("Unit"),
                "quantity": st.column_config.NumberColumn("Quantity", step=0.1, format="%.2f"),
                "reorder_level": st.column_config.NumberColumn("Reorder Level", step=0.1, format="%.2f"),
            }
        )

        with st.expander("➕ Quick Add Item"):
            col1, col2 = st.columns(2)
            with col1:
                new_item = st.text_input("Item Name", key="add_inv_item")
                new_category = st.selectbox(
                    "Category",
                    ["Produce", "Proteins", "Dairy & Eggs", "Dry Goods", "Spices & Condiments", "Beverages", "Other"],
                    key="add_inv_category"
                )
            with col2:
                new_unit = st.selectbox("Unit", ["kg", "g", "l", "ml", "pc", "piece"], key="add_inv_unit")
                new_quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.1, key="add_inv_qty")
                new_reorder = st.number_input("Reorder Level", min_value=0.0, value=1.0, step=0.1, key="add_inv_reorder")

            if st.button("➕ Add Item", key="add_inv_btn"):
                if new_item:
                    new_row = pd.DataFrame({
                        'item': [new_item],
                        'category': [new_category],
                        'unit': [new_unit],
                        'quantity': [new_quantity],
                        'reorder_level': [new_reorder]
                    })
                    updated = pd.concat([inventory_df, new_row], ignore_index=True)
                    save_inventory(updated)
                    st.success(f"✅ Added '{new_item}'!")
                    st.rerun()
                else:
                    st.error("❌ Please enter an Item Name.")

        if st.button("💾 Save Inventory Changes", type="primary"):
            try:
                save_inventory(edited_inventory)
                st.success("✅ Inventory saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving: {e}")

    with tab2:
        st.subheader("📝 Edit Recipes")

        with st.container(border=True):
            st.markdown("**🔢 Quick Update Ingredient Quantity**")
            st.caption("Use this on a phone — it's more reliable than tapping cells directly below.")
            if not recipes_df.empty:
                r_recipe = st.selectbox("Recipe", recipes_df['recipe_name'].unique().tolist(), key="qty_update_recipe")
                r_options = recipes_df[recipes_df['recipe_name'] == r_recipe]['ingredient'].tolist()
                if r_options:
                    r_ingredient = st.selectbox("Ingredient", r_options, key="qty_update_recipe_ing")
                    r_row = recipes_df[(recipes_df['recipe_name'] == r_recipe) & (recipes_df['ingredient'] == r_ingredient)].iloc[0]
                    st.caption(f"Current: {float(r_row['quantity'])} {r_row['unit']}")
                    r_new_qty = st.number_input("New quantity", min_value=0.0, value=float(r_row['quantity']), step=0.1, key="qty_update_recipe_value")
                    if st.button("✅ Update Ingredient Quantity", type="primary", key="qty_update_recipe_btn"):
                        recipes_df.loc[(recipes_df['recipe_name'] == r_recipe) & (recipes_df['ingredient'] == r_ingredient), 'quantity'] = r_new_qty
                        save_recipes(recipes_df)
                        st.success(f"✅ {r_ingredient} in {r_recipe} updated to {r_new_qty} {r_row['unit']}")
                        st.rerun()

        st.markdown("---")

        if not recipes_df.empty:
            st.dataframe(recipes_df)

        with st.expander("➕ Add New Recipe"):
            col1, col2 = st.columns(2)
            with col1:
                new_recipe_name = st.text_input("Recipe Name", key="add_recipe_name")
            with col2:
                new_ingredient = st.text_input("Ingredient", key="add_recipe_ingredient")

            col1, col2, col3 = st.columns(3)
            with col1:
                new_quantity = st.number_input("Quantity", min_value=0.0, value=1.0, step=0.1, key="add_recipe_qty")
            with col2:
                new_unit = st.selectbox("Unit", ["g", "kg", "ml", "l", "pc", "piece"], key="add_recipe_unit")

            if st.button("➕ Add Ingredient to Recipe"):
                if new_recipe_name and new_ingredient:
                    new_row = pd.DataFrame({
                        'recipe_name': [new_recipe_name],
                        'ingredient': [new_ingredient],
                        'quantity': [new_quantity],
                        'unit': [new_unit]
                    })
                    updated_recipes = pd.concat([recipes_df, new_row], ignore_index=True)
                    save_recipes(updated_recipes)
                    st.success(f"✅ Added '{new_ingredient}' to '{new_recipe_name}'!")
                    st.rerun()
                else:
                    st.error("❌ Please fill in all fields")

        st.subheader("✏️ Edit All Recipes")
        edited_recipes = st.data_editor(
            recipes_df,
            num_rows="dynamic",
            use_container_width=True,
            key="recipes_editor",
            column_config={
                "recipe_name": st.column_config.TextColumn("Recipe Name"),
                "ingredient": st.column_config.TextColumn("Ingredient"),
                "quantity": st.column_config.NumberColumn("Quantity", step=0.1, format="%.2f"),
                "unit": st.column_config.TextColumn("Unit"),
            }
        )
        if st.button("💾 Save Recipe Changes", type="primary"):
            try:
                save_recipes(edited_recipes)
                st.success("✅ Recipes saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving: {e}")

    with tab3:
        st.subheader("🍽️ Edit Buffet Recipes")

        with st.container(border=True):
            st.markdown("**🔢 Quick Update Ingredient Quantity**")
            st.caption("Use this on a phone — it's more reliable than tapping cells directly below.")
            if not buffet_df.empty:
                b_buffet = st.selectbox("Buffet", buffet_df['buffet_name'].unique().tolist(), key="qty_update_buffet")
                b_options = buffet_df[buffet_df['buffet_name'] == b_buffet]['ingredient'].tolist()
                if b_options:
                    b_ingredient = st.selectbox("Ingredient", b_options, key="qty_update_buffet_ing")
                    b_row = buffet_df[(buffet_df['buffet_name'] == b_buffet) & (buffet_df['ingredient'] == b_ingredient)].iloc[0]
                    st.caption(f"Current: {float(b_row['quantity'])} {b_row['unit']} per person")
                    b_new_qty = st.number_input("New quantity (per person)", min_value=0.0, value=float(b_row['quantity']), step=0.1, key="qty_update_buffet_value")
                    if st.button("✅ Update Ingredient Quantity", type="primary", key="qty_update_buffet_btn"):
                        buffet_df.loc[(buffet_df['buffet_name'] == b_buffet) & (buffet_df['ingredient'] == b_ingredient), 'quantity'] = b_new_qty
                        save_buffet_recipes(buffet_df)
                        st.success(f"✅ {b_ingredient} in {b_buffet} updated to {b_new_qty} {b_row['unit']}")
                        st.rerun()

        st.markdown("---")

        if not buffet_df.empty:
            st.dataframe(buffet_df)

        with st.expander("➕ Add New Buffet Recipe"):
            col1, col2 = st.columns(2)
            with col1:
                new_buffet_name = st.text_input("Buffet Name", key="add_buffet_name")
            with col2:
                new_buffet_ingredient = st.text_input("Ingredient", key="add_buffet_ingredient")

            col1, col2, col3 = st.columns(3)
            with col1:
                new_buffet_qty = st.number_input("Quantity (per person)", min_value=0.0, value=100.0, step=1.0, key="add_buffet_qty")
            with col2:
                new_buffet_unit = st.selectbox("Unit", ["g", "kg", "ml", "l", "pc", "piece"], key="add_buffet_unit")

            if st.button("➕ Add Ingredient to Buffet"):
                if new_buffet_name and new_buffet_ingredient:
                    new_row = pd.DataFrame({
                        'buffet_name': [new_buffet_name],
                        'ingredient': [new_buffet_ingredient],
                        'quantity': [new_buffet_qty],
                        'unit': [new_buffet_unit]
                    })
                    updated_buffet = pd.concat([buffet_df, new_row], ignore_index=True)
                    save_buffet_recipes(updated_buffet)
                    st.success(f"✅ Added '{new_buffet_ingredient}' to '{new_buffet_name}'!")
                    st.rerun()
                else:
                    st.error("❌ Please fill in all fields")

        st.subheader("✏️ Edit All Buffet Recipes")
        edited_buffet = st.data_editor(
            buffet_df,
            num_rows="dynamic",
            use_container_width=True,
            key="buffet_editor",
            column_config={
                "buffet_name": st.column_config.TextColumn("Buffet Name"),
                "ingredient": st.column_config.TextColumn("Ingredient"),
                "quantity": st.column_config.NumberColumn("Quantity (per person)", step=0.1, format="%.2f"),
                "unit": st.column_config.TextColumn("Unit"),
            }
        )
        if st.button("💾 Save Buffet Changes", type="primary"):
            try:
                save_buffet_recipes(edited_buffet)
                st.success("✅ Buffet recipes saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error saving: {e}")

# --- PAGE 5: CONSUMPTION ANALYTICS ---
elif page == "📈 Consumption Analytics":
    st.header("📈 Consumption Analytics")

    history_df = load_order_history()

    if history_df.empty:
        st.info("No orders have been placed yet. Start taking orders to see consumption analytics here!")
    else:
        consumption = history_df.groupby('item')['quantity'].sum().reset_index()
        consumption = consumption.sort_values(by='quantity', ascending=False)

        beverage_keywords = ['juice', 'orange', 'pineapple', 'papaya', 'mango', 'coffee', 'tea', 'water', 'soda', 'coke', 'sprit', 'lemonade', 'milk']

        food_df = consumption[~consumption['item'].str.lower().str.contains('|'.join(beverage_keywords))]
        beverage_df = consumption[consumption['item'].str.lower().str.contains('|'.join(beverage_keywords))]

        top_food = food_df.head(10)
        top_beverages = beverage_df.head(10)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("🍔 Top 10 Most Consumed Foods")
            if not top_food.empty:
                fig_food = px.bar(
                    top_food,
                    x='item',
                    y='quantity',
                    title="Most Consumed Food Items",
                    labels={'quantity': 'Total Quantity Consumed', 'item': ''},
                    color='quantity',
                    color_continuous_scale='Tealgrn'
                )
                st.plotly_chart(fig_food, use_container_width=True)
            else:
                st.caption("No food items have been consumed yet.")

        with col2:
            st.subheader("🥤 Top 10 Most Consumed Beverages")
            if not top_beverages.empty:
                fig_drink = px.bar(
                    top_beverages,
                    x='item',
                    y='quantity',
                    title="Most Consumed Beverages",
                    labels={'quantity': 'Total Quantity Consumed', 'item': ''},
                    color='quantity',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_drink, use_container_width=True)
            else:
                st.caption("No beverages have been consumed yet.")

# Footer
st.markdown("---")
st.caption("🍽️ Zen Kitchen Inventory Management System")
