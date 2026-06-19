import os
import sqlite3
import streamlit as st

# Set page layout to wide and rename the browser tab
st.set_page_config(page_title="Hymn Library", layout="wide", initial_sidebar_state="expanded")

# Custom Slate-Indigo Styling for Streamlit
st.markdown("""
    <style>
    .stApp {
        background-color: #12131a;
        color: #f3f4f6;
    }
    div[data-testid="stSidebar"] {
        background-color: #1a1b23;
    }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

DB_NAME = "hymns_database.db"

# Fetch hymns from SQLite with search filter
def get_hymns(search_query=""):
    if not os.path.exists(DB_NAME):
        return []
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if search_query.strip() == "":
        cursor.execute("SELECT id, title, image_path FROM hymns ORDER BY title ASC")
    else:
        cursor.execute('''
            SELECT id, title, image_path FROM hymns 
            WHERE title LIKE ? OR extracted_text LIKE ? 
            ORDER BY title ASC
        ''', (f"%{search_query}%", f"%{search_query}%"))
    results = cursor.fetchall()
    conn.close()
    return results

# ----------------- SIDEBAR (Left) -----------------
st.sidebar.title("Hymn Search")

# Real-time search box
search_term = st.sidebar.text_input(
    "Search title or lyrics", 
    placeholder="بحث العنوان أو الكلمات...", 
    label_visibility="collapsed"
)

# Load matching songs
hymn_list = get_hymns(search_term)

selected_hymn = None

if hymn_list:
    titles = [row[1] for row in hymn_list]
    
    # Render song selector in the sidebar
    selected_title = st.sidebar.radio(
        f"Select a song ({len(titles)} found):",
        options=titles,
        label_visibility="collapsed"
    )
    
    # Retrieve the path of the highlighted song
    selected_hymn = next(row for row in hymn_list if row[1] == selected_title)
else:
    st.sidebar.info("No hymns match your search.")

# ----------------- MAIN VIEWER (Right) -----------------
if selected_hymn:
    hymn_id, title, image_path = selected_hymn
    
    # Title Header
    st.subheader(title)
    
    # Display the Image
    if os.path.exists(image_path):
        st.image(image_path, use_container_width=True)
    else:
        st.error(f"Image file not found on server: {image_path}")
else:
    st.write("### Welcome to the Hymn Library")
    st.write("Select a hymn from the sidebar menu to begin playing.")
