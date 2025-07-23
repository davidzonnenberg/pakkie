import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import random
import streamlit.components.v1 as components

# ---------- Config ----------
st.set_page_config(page_title="Paklijst App", layout="wide")

# ---------- Google Sheets ----------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = st.secrets["gcp_service_account"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

SHEET_NAME = "Paklijst Data"



# ---------- Constants ----------

TEMPLATE_FILE = "packing_list.xlsx"
DEFAULT_CATEGORIES = [
    "Boodschappen",
    "EHBO & Medicatie",
    "Elektronica",
    "Hygiëne & Verzorging",
    "Kamperen & Slaap",
    "Keuken & Eten",
    "Kleding & Accessoires",
    "Overig",
    "Party Gear"
]

CATEGORY_EMOJIS = {
    "Kamperen & Slaap": "⛺",
    "Hygiëne & Verzorging": "🧼",
    "EHBO & Medicatie": "💊",
    "Kleding & Accessoires": "👕",
    "Elektronica": "🔌",
    "Keuken & Eten": "🍽️",
    "Boodschappen": "🛒",
    "Party Gear": "🎉",
    "Overig": "📦",
}

# ---------- Helpers ----------
def load_data():
    dfs = {}
    try:
        spreadsheet = client.open(SHEET_NAME)
        for user in ["David & Julia", "Koen & Rumeysa"]:
            try:
                sheet = spreadsheet.worksheet(user)
                data = sheet.get_all_records()
                df = pd.DataFrame(data)
            except gspread.exceptions.WorksheetNotFound:
                df = pd.DataFrame(columns=["Item", "Category", "Packed", "Deleted", "Timestamp", "Notes", "History"])
                spreadsheet.add_worksheet(title=user, rows="100", cols="10")
            for col in ["Packed", "Deleted", "Timestamp", "Notes", "History"]:
                if col not in df.columns:
                    df[col] = pd.NaT if col == "Timestamp" else ""
            dfs[user] = df.astype({
                "Item": "string",
                "Category": "string",
                "Packed": "bool",
                "Deleted": "bool",
                "Notes": "string",
                "History": "string"
            })
    except Exception as e:
        st.error(f"Fout bij laden van Google Sheet: {e}")
    return dfs


def save_data(dfs):
    spreadsheet = client.open(SHEET_NAME)
    for user, df in dfs.items():
        try:
            sheet = spreadsheet.worksheet(user)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=user, rows="100", cols="10")
        sheet.clear()
        sheet.update([df.columns.values.tolist()] + df.fillna("").values.tolist())


def add_item(df, item, category):
    return pd.concat([df, pd.DataFrame([{
        "Item": item,
        "Category": category,
        "Packed": False,
        "Deleted": False,
        "Timestamp": pd.NaT,
        "Notes": "",
        "History": ""
    }])], ignore_index=True)

def filter_df(df, filter_option):
    if filter_option == "Alle":
        return df[~df["Deleted"]]
    if filter_option == "Ingepakt":
        return df[(df["Packed"]) & (~df["Deleted"])]
    if filter_option == "Niet ingepakt":
        return df[(~df["Packed"]) & (~df["Deleted"])]
    if filter_option == "Verwijderd":
        return df[df["Deleted"]]
    return df

def show_stats(df):
    st.markdown("### 📊 Voortgang")
    stats = []
    for cat in sorted(df["Category"].dropna().unique()):
        subset = df[(df["Category"] == cat) & (~df["Deleted"])]
        if len(subset) == 0:
            continue
        pct = int(subset["Packed"].mean() * 100)
        stats.append((cat, pct, len(subset)))
    for cat, pct, total in stats:
        st.write(f"{CATEGORY_EMOJIS.get(cat, '')} **{cat}**: {pct}% ({total} items)")
        st.progress(pct)

def load_preset():
    if os.path.exists(TEMPLATE_FILE):
        df = pd.read_excel(TEMPLATE_FILE, engine="openpyxl")
        for col in ["Packed", "Deleted", "Timestamp", "Notes", "History"]:
            if col not in df.columns:
                df[col] = pd.NaT if col == "Timestamp" else ""
        return df.astype({
            "Item": "string",
            "Category": "string",
            "Packed": "bool",
            "Deleted": "bool",
            "Notes": "string",
            "History": "string"
        })
    return pd.DataFrame(columns=["Item", "Category", "Packed", "Deleted", "Timestamp", "Notes", "History"])

# ---------- App ----------

# --- Make checkboxes bigger ---
st.markdown("""
    <style>
    input[type="checkbox"] {
        transform: scale(1.5);
        margin-right: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar: User + Weather + Playlist ---
st.sidebar.title("👥 Gebruiker")
user = st.sidebar.radio("Selecteer gebruiker", ["David & Julia", "Koen & Rumeysa"])

st.sidebar.markdown("### 🌦️ Weer Geestmerambacht (24-27 juli)")
st.sidebar.info("""
**24 juli**: 22°C, zon  
**25 juli**: 23°C, half bewolkt  
**26 juli**: 21°C, kans op bui  
**27 juli**: 22°C, zon
""")

st.sidebar.markdown("### 🎵 Packing Playlist")
components.iframe(
    "https://open.spotify.com/embed/playlist/1IA3twAv0jJATy8gkqlydh?utm_source=generator",
    height=80,
    scrolling=False
)

dfs = load_data()
df = dfs.get(user, pd.DataFrame(columns=["Item", "Category", "Packed", "Deleted", "Timestamp", "Notes", "History"]))

st.title(f"🎒 Paklijst – {user}")

tab1, tab_preset, tab2, tab3 = st.tabs([
    "📋 Lijst",
    "📦 Load preset",
    "➕ Toevoegen",
    "📊 Voortgang"
])

# --- Mobile detection (simple) ---
is_mobile = False
if st.query_params.get("mobile") == ["1"]:
    is_mobile = True

# --- Tab 1: Lijst ---
with tab1:
    # --- Search bar ---
    search_query = st.text_input("🔍 Zoek een item in de lijst", key="search_bar").strip().lower()

    filter_option = st.radio("", ["Alles", "Niet ingepakt", "Ingepakt", "Verwijderd"], horizontal=True)
    filtered_df = filter_df(df, filter_option)

    # Apply search filter
    if search_query:
        filtered_df = filtered_df[filtered_df["Item"].str.lower().str.contains(search_query)]

    if filter_option == "Ingepakt":
        with st.expander("🔄 Alles uitpakken"):
            st.markdown("Weet je zeker dat je alles wilt uitpakken?")
            confirm_unpack = st.checkbox("Ja, ik wil alles uitpakken")
            if confirm_unpack and st.button("Uitpakken bevestigen"):
                df.loc[df["Packed"] & (~df["Deleted"]), "Packed"] = False
                df.loc[df["Packed"] & (~df["Deleted"]), "Timestamp"] = pd.NaT
                dfs[user] = df
                save_data(dfs)
                st.rerun()

    for cat in DEFAULT_CATEGORIES:
        cat_df = filtered_df[filtered_df["Category"] == cat].sort_values("Item")
        total = len(df[(df["Category"] == cat) & (~df["Deleted"])])
        packed = len(df[(df["Category"] == cat) & (~df["Deleted"]) & (df["Packed"])])
        pct = int((packed / total) * 100) if total > 0 else 0
        if cat_df.empty and total == 0:
            continue

        with st.expander(f"{CATEGORY_EMOJIS.get(cat, '')} {cat} – {packed}/{total} ({pct}%)", expanded=True):
            for _, row in cat_df.iterrows():
                idx = row.name
                cols = st.columns([0.05, 0.35, 0.15, 0.2, 0.2, 0.05])
                with cols[0]:
                    packed_val = st.checkbox(" ", value=row["Packed"], key=f"packed_{idx}", label_visibility="collapsed")
                    if packed_val != row["Packed"]:
                        df.at[idx, "Packed"] = packed_val
                        df.at[idx, "Timestamp"] = datetime.now() if packed_val else pd.NaT
                        df.at[idx, "History"] += f"{datetime.now().strftime('%Y-%m-%d')} - {'Ingepakt' if packed_val else 'Uitgepakt'}: {row['Item']}\n"
                        dfs[user] = df
                        save_data(dfs)
                        st.rerun()
                # --- Editable item name ---
                with cols[1]:
                    new_item_name = st.text_input("Naam", value=row["Item"], key=f"itemname_{idx}", label_visibility="collapsed")
                    if new_item_name != row["Item"] and new_item_name.strip():
                        df.at[idx, "Item"] = new_item_name.strip()
                        dfs[user] = df
                        save_data(dfs)
                        st.rerun()
                if not is_mobile:
                    with cols[2]:
                        new_cat = st.selectbox("Categorie", DEFAULT_CATEGORIES, index=DEFAULT_CATEGORIES.index(row["Category"]) if row["Category"] in DEFAULT_CATEGORIES else 0, key=f"cat_{idx}", label_visibility="collapsed")
                        df.at[idx, "Category"] = new_cat
                    with cols[3]:
                        note_value = "" if pd.isna(row["Notes"]) else row["Notes"]
                        df.at[idx, "Notes"] = st.text_input("Notitie", value=note_value, key=f"note_{idx}", placeholder="Notitie", label_visibility="collapsed")
                with cols[4]:
                    if filter_option == "Verwijderd":
                        if st.button("♻️", key=f"restore_{idx}"):
                            df.at[idx, "Deleted"] = False
                            dfs[user] = df
                            save_data(dfs)
                            st.rerun()
                    else:
                        if st.button("🗑️", key=f"delete_{idx}"):
                            df.at[idx, "Deleted"] = True
                            dfs[user] = df
                            save_data(dfs)
                            st.rerun()
            # --- Quick add under each category ---
            show_quick_add = filter_option != "Verwijderd" and not search_query
            if show_quick_add:
                quick_add = st.text_input(f"Snel toevoegen aan {cat}", key=f"quickadd_{cat}")
                if st.button("Toevoegen", key=f"quickadd_btn_{cat}"):
                    if quick_add.strip():
                        df = add_item(df, quick_add.strip(), cat)
                        # If in 'Ingepakt', set as packed and update timestamp/history
                        if filter_option == "Ingepakt":
                            idx_new = df.index[-1]
                            df.at[idx_new, "Packed"] = True
                            df.at[idx_new, "Timestamp"] = datetime.now()
                            df.at[idx_new, "History"] = f"{datetime.now().strftime('%Y-%m-%d')} - Ingepakt: {quick_add.strip()}\n"
                        dfs[user] = df
                        save_data(dfs)
                        st.success(f"Toegevoegd: {quick_add.strip()} ({cat})")
                        st.rerun()

    # --- Random Item Picker (at the bottom) ---
    st.markdown("---")
    st.markdown("#### 🎲 Random Item Picker")
    if "random_suggestion" not in st.session_state:
        st.session_state["random_suggestion"] = None
    unpacked_items = df[(~df["Packed"]) & (~df["Deleted"])]["Item"].dropna().tolist()
    if st.button("Suggest een willekeurig item!"):
        if unpacked_items:
            suggestion = random.choice(unpacked_items)
            st.session_state["random_suggestion"] = suggestion
            st.rerun()
        else:
            st.info("Geen niet-ingepakte items meer!")
            st.session_state["random_suggestion"] = None

    suggestion = st.session_state.get("random_suggestion", None)
    if suggestion and suggestion in unpacked_items:
        st.success(f"🎒 Suggestie: **{suggestion}**")
        if st.button(f"Heb 'm!", key=f"packed_picker_{suggestion}"):
            idx = df[df["Item"] == suggestion].index[0]
            df.at[idx, "Packed"] = True
            df.at[idx, "Timestamp"] = datetime.now()
            df.at[idx, "History"] += f"{datetime.now().strftime('%Y-%m-%d')} - Ingepakt: {suggestion}\n"
            dfs[user] = df
            save_data(dfs)
            st.session_state["random_suggestion"] = None
            st.rerun()

# --- Tab: Load preset ---
with tab_preset:
    st.markdown("### 📦 Laad presetlijst")
    preset_options = {
        "Liquicity25": TEMPLATE_FILE
    }
    selected_preset = st.selectbox("PAS OP! ALS JE EEN PRESET KIEST, VERLIES JE AL JE HUIDIGE VOORTGANG EN TOEGEVOEGDE ITEMS!", list(preset_options.keys()))
    if st.button("Preset laden"):
        preset_df = pd.read_excel(preset_options[selected_preset], engine="openpyxl")
        for col in ["Packed", "Deleted", "Timestamp", "Notes", "History"]:
            if col not in preset_df.columns:
                preset_df[col] = pd.NaT if col == "Timestamp" else ""
        preset_df["Packed"] = False
        preset_df["Deleted"] = False
        preset_df["Timestamp"] = pd.NaT
        preset_df["Notes"] = ""
        preset_df["History"] = ""
        preset_df = preset_df.astype({
            "Item": "string",
            "Category": "string",
            "Packed": "bool",
            "Deleted": "bool",
            "Notes": "string",
            "History": "string"
        })
        dfs[user] = preset_df
        save_data(dfs)
        st.success("Presetlijst geladen en toegepast!")
        st.rerun()

# --- Tab 2: Toevoegen ---
with tab2:
    all_items = set()
    all_cats = {}
    for other_user, other_df in dfs.items():
        if other_user != user:
            for _, row in other_df.iterrows():
                if pd.notna(row["Item"]):
                    all_items.add(row["Item"])
                    all_cats[row["Item"]] = row["Category"]
    suggestions = sorted(all_items - set(df["Item"].dropna().unique()))
    if suggestions:
        st.markdown("### Suggesties van andere gebruikers")
        for suggestion in suggestions:
            cat = all_cats.get(suggestion, "Overig")
            col1, col2, col3 = st.columns([0.6, 0.3, 0.1])
            with col1:
                st.text(suggestion)
            with col2:
                st.markdown(f"*{cat}*")
            with col3:
                if st.button("Toevoegen", key=f"suggest_{suggestion}"):
                    df = add_item(df, suggestion, cat)
                    dfs[user] = df
                    st.success(f"Toegevoegd: {suggestion} ({cat})")
                    save_data(dfs)
                    st.rerun()
    st.markdown("### Nieuw item")
    with st.form("add_form", clear_on_submit=True):
        item = st.text_input("Itemnaam")
        category = st.selectbox("Categorie", DEFAULT_CATEGORIES)
        note = st.text_input("Notitie (optioneel)")
        submitted = st.form_submit_button("Toevoegen")
        if submitted and item:
            df = add_item(df, item, category)
            df.at[df.index[-1], "Notes"] = note
            dfs[user] = df
            st.success(f"Toegevoegd: {item} ({category})")
            save_data(dfs)
            st.rerun()

# --- Tab 3: Voortgang ---
with tab3:
    # Total progress
    total_items = len(df[~df["Deleted"]])
    total_packed = len(df[(df["Packed"]) & (~df["Deleted"])])
    total_pct = int((total_packed / total_items) * 100) if total_items > 0 else 0
    st.markdown(f"### 📊 Totale voortgang: {total_packed}/{total_items} ({total_pct}%)")
    st.progress(total_pct)

    show_stats(df)

    st.markdown("---")
    st.markdown("### Voortgang van andere gebruikers")
    for other_user, other_df in dfs.items():
        if other_user == user:
            continue
        total_items_other = len(other_df[~other_df["Deleted"]])
        total_packed_other = len(other_df[(other_df["Packed"]) & (~other_df["Deleted"])])
        total_pct_other = int((total_packed_other / total_items_other) * 100) if total_items_other > 0 else 0
        st.markdown(f"**{other_user}**: {total_packed_other}/{total_items_other} ({total_pct_other}%)")
        st.progress(total_pct_other)
        # Optionally show per-category stats for others:
        # show_stats(other_df)

# --- Save and update ---
dfs[user] = df
save_data(dfs)
