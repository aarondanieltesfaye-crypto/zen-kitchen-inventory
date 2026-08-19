import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# Page config
st.set_page_config(
    page_title="Zen Kitchen Inventory",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ Zen Kitchen Inventory Management")
st.markdown("---")

# --- GOOGLE SHEETS CONNECTION ---
# Credentials come from Streamlit secrets (Settings > Secrets on Streamlit Cloud),
# never from a file committed to GitHub.

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

@st.cache_resource
def get_gspread_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

def get_worksheet(sheet_name):
    client = get_gspread_client()
    spreadsheet = client.open_by_key(st.secrets["sheet_id"])
    try:
        return spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return spreadsheet.add_worksheet(title=sheet_name, rows=200, cols=10)

def read_sheet(sheet_name):
    ws = get_worksheet(sheet_name)
    records = ws.get_all_records()
    return pd.DataFrame(records)

def write_sheet(sheet_name, df):
    ws = get_worksheet(sheet_name)
    ws.clear()
    if not df.empty:
        ws.update([df.columns.values.tolist()] + df.astype(str).values.tolist())
    else:
        ws.update([df.columns.values.tolist()])
    st.cache_data.clear()

# --- DATA LOADING FUNCTIONS ---
# ttl=30 means Streamlit re-checks the sheet at most every 30 seconds per user,
# so multiple staff members see reasonably fresh data without hammering the API.

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
    else:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
        df['reorder_level'] = pd.to_numeric(df['reorder_level'], errors='coerce')
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
    else:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
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
    else:
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
    return df

# --- LOAD DATA ---

inventory_df = load_inventory()
recipes_df = load_recipes()
buffet_df = load_buffet_recipes()

# --- NAVIGATION SIDEBAR ---

st.sidebar.title("📋 Navigation")
page = st.sidebar.radio(
    "Go to:",
    ["Dashboard", "Take Order", "Buffet Order", "Edit Data", "Consumption Analytics"],
    key="nav_radio"
)

# --- PAGE: DASHBOARD ---

if page == "Dashboard":
    st.header("📊 Dashboard")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Inventory Items", len(inventory_df))
    with col2:
        st.metric("Total Recipes", len(recipes_df['recipe_name'].unique()) if not recipes_df.empty else 0)
    with col3:
        st.metric("Total Buffet Menus", len(buffet_df['buffet_name'].unique()) if not buffet_df.empty else 0)

    st.subheader("📦 Low Stock Alert")
    low_stock = inventory_df[inventory_df['quantity'] <= inventory_df['reorder_level']]
    if not low_stock.empty:
        st.warning("The following items are low in stock:")
        st.dataframe(low_stock, use_container_width=True)
    else:
        st.success("✅ All items are well-stocked!")

# --- PAGE: TAKE ORDER ---

elif page == "Take Order":
    st.header("📝 Take Order")

    if recipes_df.empty:
        st.warning("No recipes found. Please add recipes in the 'Edit Data' tab first.")
    else:
        recipe_names = recipes_df['recipe_name'].unique()
        selected_recipe = st.selectbox("Select Recipe", recipe_names, key="order_select_recipe")
        quantity = st.number_input("Number of Servings", min_value=1, value=1, step=1, key="order_quantity")

        if st.button("🛒 Process Order", type="primary", key="order_process_btn"):
            recipe_ingredients = recipes_df[recipes_df['recipe_name'] == selected_recipe]

            can_make = True
            deductions = []
            for _, row in recipe_ingredients.iterrows():
                ingredient = row['ingredient']
                needed_qty = row['quantity'] * quantity

                inv_row = inventory_df[inventory_df['item'] == ingredient]
                if inv_row.empty:
                    st.error(f"❌ Missing ingredient: {ingredient}")
                    can_make = False
                elif inv_row.iloc[0]['quantity'] < needed_qty:
                    st.error(f"❌ Not enough {ingredient}. Have {inv_row.iloc[0]['quantity']}, need {needed_qty}")
                    can_make = False
                else:
                    deductions.append({'ingredient': ingredient, 'quantity': needed_qty})

            if can_make:
                for ded in deductions:
                    inventory_df.loc[inventory_df['item'] == ded['ingredient'], 'quantity'] -= ded['quantity']

                write_sheet("inventory", inventory_df)

                st.success(f"✅ Order for {quantity} x {selected_recipe} completed!")
                st.balloons()

                st.subheader("📋 Ingredients Used:")
                st.dataframe(pd.DataFrame(deductions), use_container_width=True)
                st.rerun()

# --- PAGE: BUFFET ORDER ---

elif page == "Buffet Order":
    st.header("🍽️ Buffet Order")

    if buffet_df.empty:
        st.warning("No buffet recipes found. Please add buffet recipes in the 'Edit Data' tab first.")
    else:
        buffet_names = buffet_df['buffet_name'].unique()
        selected_buffet = st.selectbox("Select Buffet Menu", buffet_names, key="buffet_select_menu")
        guests = st.number_input("Number of Guests", min_value=1, value=1, step=1, key="buffet_guests")

        if st.button("🍽️ Process Buffet Order", type="primary", key="buffet_process_btn"):
            buffet_ingredients = buffet_df[buffet_df['buffet_name'] == selected_buffet]

            can_serve = True
            deductions = []
            for _, row in buffet_ingredients.iterrows():
                ingredient = row['ingredient']
                needed_qty = row['quantity'] * guests

                inv_row = inventory_df[inventory_df['item'] == ingredient]
                if inv_row.empty:
                    st.error(f"❌ Missing ingredient: {ingredient}")
                    can_serve = False
                elif inv_row.iloc[0]['quantity'] < needed_qty:
                    st.error(f"❌ Not enough {ingredient}. Have {inv_row.iloc[0]['quantity']}, need {needed_qty}")
                    can_serve = False
                else:
                    deductions.append({'ingredient': ingredient, 'quantity': needed_qty})

            if can_serve:
                for ded in deductions:
                    inventory_df.loc[inventory_df['item'] == ded['ingredient'], 'quantity'] -= ded['quantity']

                write_sheet("inventory", inventory_df)

                st.success(f"✅ Buffet for {guests} guests on '{selected_buffet}' is ready!")
                st.balloons()

                st.subheader("📋 Ingredients Used:")
                st.dataframe(pd.DataFrame(deductions), use_container_width=True)
                st.rerun()

# --- PAGE: EDIT DATA ---

elif page == "Edit Data":
    st.title("✏️ Edit Kitchen Data")
    st.markdown("---")

    inventory_df = load_inventory()
    recipes_df = load_recipes()
    buffet_df = load_buffet_recipes()

    tab1, tab2, tab3 = st.tabs(["📦 Inventory", "📝 Recipes", "🍽️ Buffet Recipes"])

    # --- Inventory Tab ---
    with tab1:
        st.subheader("📦 Edit Inventory")
        st.caption("💡 Edit quantities, categories, and reorder levels. Double-click any cell to edit.")

        edited_inventory = st.data_editor(
            inventory_df,
            num_rows="dynamic",
            use_container_width=True,
            key="app_editor_inventory"
        )

        if st.button("💾 Save Inventory Changes", type="primary", key="app_save_inventory"):
            write_sheet("inventory", edited_inventory)
            st.success("✅ Inventory saved!")
            st.rerun()

        with st.expander("➕ Quick Add Item"):
            new_item = st.text_input("Item Name*", key="app_inv_item")
            new_cat = st.selectbox("Category", ["Produce", "Proteins", "Dairy & Eggs", "Dry Goods", "Spices & Condiments", "Beverages", "Other"], key="app_inv_cat")
            new_unit = st.selectbox("Unit", ["kg", "g", "l", "ml", "pc", "piece"], key="app_inv_unit")
            new_qty = st.number_input("Quantity", min_value=0.0, step=0.1, key="app_inv_qty")
            new_level = st.number_input("Reorder Level", min_value=0.0, step=0.1, key="app_inv_reorder")

            if st.button("➕ Add Item", key="app_inv_add"):
                new_row = pd.DataFrame({'item': [new_item], 'category': [new_cat], 'unit': [new_unit], 'quantity': [new_qty], 'reorder_level': [new_level]})
                updated_df = pd.concat([inventory_df, new_row], ignore_index=True)
                write_sheet("inventory", updated_df)
                st.success(f"Added {new_item}")
                st.rerun()

    # --- Recipes Tab ---
    with tab2:
        st.subheader("📝 Edit Recipes")

        if not recipes_df.empty:
            st.subheader("📋 Current Recipes")
            for recipe in recipes_df['recipe_name'].unique():
                with st.expander(f"📖 {recipe}"):
                    st.dataframe(recipes_df[recipes_df['recipe_name'] == recipe][['ingredient', 'quantity', 'unit']], use_container_width=True)

        with st.expander("➕ Add New Recipe"):
            new_recipe = st.text_input("Recipe Name*", key="app_recipe_name")
            new_ing = st.text_input("Ingredient*", key="app_recipe_ing")
            new_qty = st.number_input("Quantity*", min_value=0.0, step=0.1, key="app_recipe_qty")
            new_unit = st.selectbox("Unit*", ["g", "kg", "ml", "l", "pc", "piece"], key="app_recipe_unit")

            if st.button("➕ Add Ingredient", key="app_recipe_add"):
                new_row = pd.DataFrame({'recipe_name': [new_recipe], 'ingredient': [new_ing], 'quantity': [new_qty], 'unit': [new_unit]})
                updated = pd.concat([recipes_df, new_row], ignore_index=True)
                write_sheet("recipes", updated)
                st.success("Added!")
                st.rerun()

        edited_recipes = st.data_editor(recipes_df, num_rows="dynamic", use_container_width=True, key="app_editor_recipes")
        if st.button("💾 Save Recipes", type="primary", key="app_save_recipes"):
            write_sheet("recipes", edited_recipes)
            st.success("Recipes saved!")
            st.rerun()

    # --- Buffet Tab ---
    with tab3:
        st.subheader("🍽️ Edit Buffet Recipes")
        st.caption("💡 Quantities are PER PERSON")

        if not buffet_df.empty:
            st.subheader("📋 Current Buffets")
            for buffet in buffet_df['buffet_name'].unique():
                with st.expander(f"🍽️ {buffet}"):
                    st.dataframe(buffet_df[buffet_df['buffet_name'] == buffet][['ingredient', 'quantity', 'unit']], use_container_width=True)

        with st.expander("➕ Add New Buffet"):
            new_buffet_name = st.text_input("Buffet Name*", key="app_buffet_name")
            new_buffet_ing = st.text_input("Ingredient*", key="app_buffet_ingredient")
            new_buffet_qty = st.number_input("Quantity (per person)*", min_value=0.0, step=0.1, key="app_buffet_qty")
            new_buffet_unit = st.selectbox("Unit*", ["g", "kg", "ml", "l", "pc", "piece"], key="app_buffet_unit")

            if st.button("➕ Add Ingredient to Buffet", key="app_buffet_add"):
                new_row = pd.DataFrame({'buffet_name': [new_buffet_name], 'ingredient': [new_buffet_ing], 'quantity': [new_buffet_qty], 'unit': [new_buffet_unit]})
                updated = pd.concat([buffet_df, new_row], ignore_index=True)
                write_sheet("buffet_recipes", updated)
                st.success("Added!")
                st.rerun()

        edited_buffet = st.data_editor(buffet_df, num_rows="dynamic", use_container_width=True, key="app_editor_buffet")
        if st.button("💾 Save Buffet Changes", type="primary", key="app_save_buffet"):
            write_sheet("buffet_recipes", edited_buffet)
            st.success("Buffet saved!")
            st.rerun()

# --- PAGE: CONSUMPTION ANALYTICS ---

elif page == "Consumption Analytics":
    st.header("📊 Consumption Analytics")

    if inventory_df.empty:
        st.warning("No inventory data to analyze.")
    else:
        st.subheader("📦 Current Inventory Level")
        st.dataframe(inventory_df, use_container_width=True)

        st.subheader("⚠️ Items Below Reorder Level")
        low_stock = inventory_df[inventory_df['quantity'] <= inventory_df['reorder_level']]
        if not low_stock.empty:
            st.warning(low_stock[['item', 'quantity', 'reorder_level']])
        else:
            st.success("All items are above reorder level.")

        st.info("💡 *Note: Detailed consumption charts will be available in a future update.*")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("🍽️ Zen Kitchen v1.0")
