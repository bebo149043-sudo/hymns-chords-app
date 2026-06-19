import os
import sqlite3
import uuid
import base64
import requests
import streamlit as st
from PIL import Image

# Attempt to import pytesseract. 
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

# Set page config
st.set_page_config(page_title="Hymn Library", layout="wide", initial_sidebar_state="expanded")

# Custom Dark Mode styling
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
IMAGES_DIR = "stored_hymns"

# Ensure image directory exists locally
if not os.path.exists(IMAGES_DIR):
    os.makedirs(IMAGES_DIR)

# ----------------- GITHUB AUTO-SYNC LOGIC -----------------
def upload_to_github(token, repo, file_path, content_bytes, commit_message):
    """Commits and pushes a file directly to the GitHub repository via REST API."""
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if file exists to get its unique SHA key (required for updating files in Git)
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        
    content_encoded = base64.b64encode(content_bytes).decode("utf-8")
    payload = {
        "message": commit_message,
        "content": content_encoded,
    }
    if sha:
        payload["sha"] = sha
        
    response = requests.put(url, headers=headers, json=payload)
    return response.status_code in [200, 201]

# ----------------- DATABASE UTILITIES -----------------
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

# ----------------- SIDEBAR MENU (Left) -----------------
st.sidebar.title("Hymn Search")

search_term = st.sidebar.text_input(
    "Search title or lyrics", 
    placeholder="بحث العنوان أو الكلمات...", 
    label_visibility="collapsed"
)

hymn_list = get_hymns(search_term)
selected_hymn = None

if hymn_list:
    titles = [row[1] for row in hymn_list]
    selected_title = st.sidebar.radio(
        f"Select a song ({len(titles)} found):",
        options=titles,
        label_visibility="collapsed"
    )
    selected_hymn = next(row for row in hymn_list if row[1] == selected_title)
else:
    st.sidebar.info("No hymns match your search.")

# ----------------- UPLOAD NEW SONG EXPANDER -----------------
with st.sidebar.expander("➕ Upload New Hymn", expanded=False):
    st.write("Upload a sheet music photo to automatically run Arabic OCR and sync to your library.")
    
    upload_title = st.text_input("Hymn Title (العنوان)")
    uploaded_file = st.file_uploader("Choose Sheet Music Photo", type=["jpg", "jpeg", "png", "bmp", "tiff"])
    
    if st.button("Extract & Upload"):
        if not upload_title.strip():
            st.error("Please enter a title.")
        elif not uploaded_file:
            st.error("Please select an image file.")
        else:
            with st.spinner("Running Arabic/English OCR in the Cloud..."):
                # 1. Read uploaded image bytes
                image_bytes = uploaded_file.getvalue()
                
                # 2. Perform OCR directly on the Streamlit server
                extracted_text = ""
                if PYTESSERACT_AVAILABLE:
                    try:
                        img = Image.open(uploaded_file)
                        extracted_text = pytesseract.image_to_string(img, lang='ara+eng')
                    except Exception as e:
                        st.error(f"OCR failed on server: {e}")
                
                # 3. Generate local unique path and save temporarily on server disk
                file_ext = os.path.splitext(uploaded_file.name)[1]
                unique_name = f"{uuid.uuid4()}{file_ext}"
                local_image_path = os.path.join(IMAGES_DIR, unique_name)
                
                with open(local_image_path, "wb") as f:
                    f.write(image_bytes)

                # 4. Insert record into local SQLite file
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)', 
                    (upload_title, local_image_path, extracted_text)
                )
                conn.commit()
                conn.close()

                # 5. Sync files to GitHub Repository permanently
                if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                    token = st.secrets["GITHUB_TOKEN"]
                    repo = st.secrets["GITHUB_REPO"]
                    
                    with st.spinner("Uploading and Syncing to GitHub Repository..."):
                        # Read updated SQLite binary bytes
                        with open(DB_NAME, "rb") as f:
                            db_bytes = f.read()
                            
                        # Commit image and SQLite database via API
                        success_img = upload_to_github(token, repo, local_image_path, image_bytes, f"Uploaded sheet music for '{upload_title}'")
                        success_db = upload_to_github(token, repo, DB_NAME, db_bytes, f"Updated database with entry '{upload_title}'")
                        
                        if success_img and success_db:
                            st.success(f"Success! '{upload_title}' has been uploaded and permanently saved to GitHub.")
                            st.cache_data.clear() # Clear streamlit cache to reload lists
                            st.rerun()
                        else:
                            st.error("Linked successfully to server, but failed to sync changes to GitHub. Verify your token permissions.")
                else:
                    st.warning(
                        "Song saved locally but GITHUB_TOKEN is not configured in secrets. "
                        "This upload will be lost when the Streamlit server restarts."
                    )
                    st.cache_data.clear()
                    st.rerun()

# ----------------- MAIN VIEW WINDOW -----------------
if selected_hymn:
    hymn_id, title, image_path = selected_hymn
    st.subheader(title)
    
    if os.path.exists(image_path):
        st.image(image_path, use_container_width=True)
    else:
        st.error(f"Image file not found on server: {image_path}")
else:
    st.write("### Welcome to the Hymn Library")
    st.write("Select a hymn from the sidebar menu to begin playing.")
