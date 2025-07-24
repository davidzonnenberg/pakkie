# --- db.py (UPDATED) ---

import streamlit as st
import sqlitecloud
import pandas as pd
import os

DB_FILE = "paklijst.db"
USERS = ["David_and_Julia", "Koen_and_Rumeysa"]
COLUMNS = ["Item", "Category", "Packed", "Deleted", "Notes"]


def connect_db():
    return sqlitecloud.connect(st.secrets["sqlitecloud_url"])


def init_db():
    conn = connect_db()
    cursor = conn.cursor()
    for user in USERS:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {user} (
                id INTEGER PRIMARY KEY,
                Item TEXT,
                Category TEXT,
                Packed BOOLEAN,
                Deleted BOOLEAN,
                Notes TEXT
            )
        """)
    conn.commit()
    conn.close()

def get_users():
    return [user.replace("_", " ").replace("and", "&") for user in USERS]

def get_items(user, filter_option="Alle", search_query=""):
    table = user.replace(" ", "_").replace("&", "and")
    conn = connect_db()
    cursor = conn.execute(f"SELECT * FROM {table}")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)

    conn.close()

    if df.empty:
        preset_df = load_preset_data()
        if not preset_df.empty:
            overwrite_user_data(user, preset_df)
            conn = connect_db()
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            conn.close()

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = False if col in ["Packed", "Deleted"] else ""
    if "id" not in df.columns:
        df["id"] = df.index

    df = df.astype({
        "Item": "string",
        "Category": "string",
        "Packed": "bool",
        "Deleted": "bool",
        "Notes": "string"
    })

    if filter_option == "Ingepakt":
        df = df[(df["Packed"]) & (~df["Deleted"])]
    elif filter_option == "Niet ingepakt":
        df = df[~df["Packed"] & (~df["Deleted"])]
    elif filter_option == "Verwijderd":
        df = df[df["Deleted"]]
    else:
        df = df[~df["Deleted"]]

    if search_query:
        df = df[df["Item"].str.lower().str.contains(search_query)]

    return df

def get_all_items(user):
    return get_items(user, "Alle")

def add_item(user, item, category, note="", packed=False):
    table = user.replace(" ", "_").replace("&", "and")
    item_data = (item, category, packed, False, note)
    save_item(table, item_data)

def save_item(user, item_data):
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        INSERT INTO {user} (Item, Category, Packed, Deleted, Notes)
        VALUES (?, ?, ?, ?, ?)
    """, item_data)
    conn.commit()
    conn.close()

def update_item(user, item_id, column, value):
    table = user.replace(" ", "_").replace("&", "and")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE {table}
        SET {column} = ?
        WHERE id = ?
    """, (value, item_id))
    conn.commit()
    conn.close()

def delete_item(user, item_id):
    update_item(user, item_id, "Deleted", True)

def restore_item(user, item_id):
    update_item(user, item_id, "Deleted", False)

def mark_packed(user, item_id, packed=True):
    table = user.replace(" ", "_").replace("&", "and")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE {table}
        SET Packed = ?
        WHERE id = ?
    """, (int(packed), item_id))
    conn.commit()
    conn.close()

def mark_unpacked(user):
    table = user.replace(" ", "_").replace("&", "and")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE {table}
        SET Packed = 0
        WHERE Packed = 1 AND Deleted = 0
    """)
    conn.commit()
    conn.close()

def get_progress(user):
    df = get_items(user, "Alle")
    total = len(df)
    packed = df["Packed"].sum()
    return total, packed

def list_presets():
    return [f for f in os.listdir(".") if f.endswith(".csv") and f.startswith("_")]

def load_preset_data(preset_file="packing_list.csv"):
    try:
        df = pd.read_csv(preset_file, sep=";")
        df = df.fillna("")
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = False if col in ["Packed", "Deleted"] else ""
        df = df.astype({
            "Item": "string",
            "Category": "string",
            "Packed": "bool",
            "Deleted": "bool",
            "Notes": "string"
        })
        return df[COLUMNS]
    except Exception as e:
        st.warning(f"Kan presetlijst niet laden: {e}")
        return pd.DataFrame(columns=COLUMNS)

def overwrite_user_data(user, df):
    table = user.replace(" ", "_").replace("&", "and")
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table}")
    for _, row in df.iterrows():
        item_data = (
            str(row.get("Item", "") or ""),
            str(row.get("Category", "") or ""),
            bool(row.get("Packed", False)),
            bool(row.get("Deleted", False)),
            str(row.get("Notes", "") or "")
        )
        cursor.execute(f"""
            INSERT INTO {table} (Item, Category, Packed, Deleted, Notes)
            VALUES (?, ?, ?, ?, ?)
        """, item_data)
    conn.commit()
    conn.close()

# Initialiseer database bij import
init_db()