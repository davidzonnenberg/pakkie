# --- app.py (UPDATED) ---

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import os
from db import (
    get_users, get_items, add_item, update_item, delete_item,
    restore_item, mark_packed, mark_unpacked, get_progress,
    get_all_items, load_preset_data, overwrite_user_data,
    COLUMNS, list_presets
)

# ---------- Config ----------
st.set_page_config(page_title="Paklijst App", layout="wide")

# ---------- Constants ----------
DEFAULT_CATEGORIES = [
    "Boodschappen", "EHBO & Medicatie", "Elektronica", "Hygiëne & Verzorging",
    "Kamperen & Slaap", "Keuken & Eten", "Kleding & Accessoires", "Overig", "Party Gear"
]

CATEGORY_EMOJIS = {
    "Kamperen & Slaap": "⛺", "Hygiëne & Verzorging": "🫄", "EHBO & Medicatie": "💊",
    "Kleding & Accessoires": "👕", "Elektronica": "🔌", "Keuken & Eten": "🍽️",
    "Boodschappen": "🛒", "Party Gear": "🎉", "Overig": "📦"
}

# ---------- UI ----------
st.sidebar.title("👥 Gebruiker")
users = get_users()
user = st.sidebar.radio("Selecteer gebruiker", users)

st.sidebar.markdown("### 🌦️ Weer Geestmerambacht (24-27 juli)")
st.sidebar.info("""
**24 juli**: 21°C, lichte regen  
**25 juli**: 25°C, zonnig  
**26 juli**: 22°C, licht bewolkt  
**27 juli**: 21°C, zon
""")

st.sidebar.markdown("### 🎵 Packing Playlist")
components.iframe(
    "https://open.spotify.com/embed/playlist/1IA3twAv0jJATy8gkqlydh?utm_source=generator",
    height=80, scrolling=False
)

# ---------- Tabs ----------
st.title(f"📚 Paklijst – {user}")
tab1, tab_preset, tab2, tab3 = st.tabs(["📋 Lijst", "📦 Load preset", "➕ Toevoegen", "📊 Voortgang"])


# --- Tab 1: Lijst ---
with tab1:
    search_query = st.text_input("🔍 Zoek een item in de lijst", key="search_bar").strip().lower()
    filter_option = st.radio("", ["Alle", "Niet ingepakt", "Ingepakt", "Verwijderd"], horizontal=True)
    df = get_items(user, filter_option, search_query)

    if "id" not in df.columns:
        st.warning("Database is leeg. Voeg een item toe hieronder!")
        df = pd.DataFrame(columns=["id"] + COLUMNS)
        st.stop()

    if filter_option == "Ingepakt":
        with st.expander("🔄 Alles uitpakken"):
            if st.checkbox("Ja, ik wil alles uitpakken"):
                mark_unpacked(user)
                st.rerun()

    for cat in DEFAULT_CATEGORIES:
        cat_df = df[df["Category"] == cat].sort_values("Item")
        total = len(cat_df)
        packed = cat_df["Packed"].sum()
        pct = int((packed / total) * 100) if total > 0 else 0
        if total == 0:
            continue
        with st.expander(f"{CATEGORY_EMOJIS.get(cat, '')} {cat} – {packed}/{total} ({pct}%)", expanded=True):
            for _, row in cat_df.iterrows():
                idx = row["id"]
                cols = st.columns([0.05, 0.35, 0.15, 0.2, 0.2, 0.05])
                with cols[0]:
                    packed_val = st.checkbox(" ", value=row["Packed"], key=f"packed_{idx}", label_visibility="collapsed")
                    if packed_val != row["Packed"]:
                        mark_packed(user, idx, packed_val)
                        st.rerun()
                with cols[1]:
                    new_item = st.text_input("Naam", value=row["Item"], key=f"item_{idx}", label_visibility="collapsed")
                    if new_item != row["Item"] and new_item.strip():
                        update_item(user, idx, "Item", new_item.strip())
                        st.rerun()
                with cols[2]:
                    new_cat = st.selectbox("Categorie", DEFAULT_CATEGORIES, index=DEFAULT_CATEGORIES.index(row["Category"]) if row["Category"] in DEFAULT_CATEGORIES else 0, key=f"cat_{idx}", label_visibility="collapsed")
                    if new_cat != row["Category"]:
                        update_item(user, idx, "Category", new_cat)
                        st.rerun()
                with cols[3]:
                    note = st.text_input("Notitie", value=row["Notes"] or "", key=f"note_{idx}", label_visibility="collapsed")
                    if note != (row["Notes"] or ""):
                        update_item(user, idx, "Notes", note)
                with cols[4]:
                    if filter_option == "Verwijderd":
                        if st.button("♻️", key=f"restore_{idx}"):
                            restore_item(user, idx)
                            st.rerun()
                    else:
                        if st.button("🗑️", key=f"delete_{idx}"):
                            delete_item(user, idx)
                            st.rerun()
                # Quick add
            if filter_option != "Verwijderd" and not search_query:
                quick_add = st.text_input(f"Snel toevoegen aan {cat}", key=f"quickadd_{cat}")
                if st.button("Toevoegen", key=f"quickadd_btn_{cat}") and quick_add.strip():
                    add_item(user, quick_add.strip(), cat, packed=(filter_option == "Ingepakt"))
                    st.success(f"Toegevoegd: {quick_add.strip()} ({cat})")
                    st.rerun()

    # Random picker (independent of filter)
    st.markdown("---")
    st.markdown("#### 🌪️ Random Item Picker")
    all_items = get_items(user, "Alle")
    unpacked_items = all_items[(~all_items["Packed"]) & (~all_items["Deleted"])]
    if st.button("Suggest een willekeurig item!"):
        if not unpacked_items.empty:
            st.session_state["random_suggestion"] = unpacked_items.sample(1).iloc[0]
            st.rerun()
        else:
            st.info("Geen niet-ingepakte items meer!")
    suggestion = st.session_state.get("random_suggestion")
    if suggestion is not None:
        st.success(f"👚 Suggestie: **{suggestion['Item']}**")
        if st.button("Heb 'm!", key=f"packed_picker_{suggestion['Item']}"):
            mark_packed(user, suggestion["id"], True)
            st.session_state["random_suggestion"] = None
            st.rerun()

# --- Tab: Load preset ---
with tab_preset:
    st.markdown("### 📦 Laad presetlijst")
    preset_files = list_presets()
    selected_file = st.selectbox("Selecteer preset bestand", preset_files)
    if st.button("Preset laden"):
        preset_df = load_preset_data(selected_file)
        overwrite_user_data(user, preset_df)
        st.success("Presetlijst geladen en toegepast!")
        st.rerun()
    
    # --- Download paklijst ---
    st.markdown("### 💾 Download jouw paklijst")
    export_df = get_all_items(user)
    st.download_button(
        label="Download als CSV",
        data=export_df.to_csv(index=False, sep=";"),
        file_name=f"{user.replace(' ', '_')}_paklijst.csv",
        mime="text/csv"
    )

    # --- Upload paklijst ---
    st.markdown("### 📤 Upload jouw paklijst")

    # Ensure session flag is initialized
    if "uploaded_done" not in st.session_state:
        st.session_state.uploaded_done = False

    # File uploader
    uploaded_file = st.file_uploader("Kies een CSV bestand", type=["csv"], key="file_upload")

    # 🔁 Reset uploaded_done when file is cleared
    if uploaded_file is None and st.session_state.uploaded_done:
        st.session_state.uploaded_done = False

    # Only process if file exists and not already processed
    if uploaded_file is not None and not st.session_state.uploaded_done:
        try:
            uploaded_df = pd.read_csv(uploaded_file, sep=";")
            overwrite_user_data(user, uploaded_df)
            st.session_state.uploaded_done = True
            st.success("Paklijst hersteld uit upload!")
            st.rerun()
        except Exception as e:
            st.error(f"Fout bij inladen: {e}")





# --- Tab 2: Toevoegen ---
with tab2:
    st.markdown("### Suggesties van andere gebruikers")
    current_items = set(get_all_items(user)["Item"])
    suggestions = []
    for other in users:
        if other == user:
            continue
        other_df = get_all_items(other)
        for _, row in other_df.iterrows():
            if row["Item"] not in current_items and not row["Deleted"]:
                suggestions.append((row["Item"], row["Category"]))
    for item, cat in sorted(set(suggestions)):
        col1, col2, col3 = st.columns([0.6, 0.3, 0.1])
        col1.text(item)
        col2.markdown(f"*{cat}*")
        if col3.button("Toevoegen", key=f"suggest_{item}"):
            add_item(user, item, cat)
            st.success(f"Toegevoegd: {item} ({cat})")
            st.rerun()

    st.markdown("### Nieuw item")
    with st.form("add_form", clear_on_submit=True):
        item = st.text_input("Itemnaam")
        category = st.selectbox("Categorie", DEFAULT_CATEGORIES)
        note = st.text_input("Notitie (optioneel)")
        submitted = st.form_submit_button("Toevoegen")
        if submitted and item:
            add_item(user, item, category, note=note)
            st.success(f"Toegevoegd: {item} ({category})")
            st.rerun()

# --- Tab 3: Voortgang ---
with tab3:
    st.markdown("### 📊 Totale voortgang")
    total, packed = get_progress(user)
    pct = int((packed / total) * 100) if total > 0 else 0
    st.markdown(f"**{packed}/{total} ({pct}%)**")
    st.progress(pct)

    st.markdown("### Per categorie")
    df = get_all_items(user)
    for cat in DEFAULT_CATEGORIES:
        sub = df[(df["Category"] == cat) & (~df["Deleted"])]
        if len(sub) == 0:
            continue
        pct = int(sub["Packed"].mean() * 100)
        st.write(f"{CATEGORY_EMOJIS.get(cat, '')} **{cat}**: {pct}% ({len(sub)} items)")
        st.progress(pct)

    st.markdown("---")
    st.markdown("### Voortgang van andere gebruikers")
    for other_user in users:
        if other_user == user:
            continue
        total_o, packed_o = get_progress(other_user)
        pct_o = int((packed_o / total_o) * 100) if total_o > 0 else 0
        st.markdown(f"**{other_user}**: {packed_o}/{total_o} ({pct_o}%)")
        st.progress(pct_o)
