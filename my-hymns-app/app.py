import os
import sqlite3
import uuid
import base64
import shutil
import platform
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

# ==========================================
# WRITEABLE PATH WORKAROUND FOR CLOUD
# ==========================================
REPO_DB = "hymns_database.db"
DB_NAME = "/tmp/hymns_database.db"  # Writeable path on Streamlit Cloud

# Copy database to writeable /tmp folder if it doesn't exist
if os.path.exists(REPO_DB):
    if not os.path.exists(DB_NAME):
        shutil.copy(REPO_DB, DB_NAME)

# ==========================================
# AUTOMATIC MAC/WINDOWS PATH RESOLUTION
# ==========================================
if PYTESSERACT_AVAILABLE:
    if platform.system() == "Darwin":  # macOS
        mac_paths = [
            "/opt/homebrew/bin/tesseract",
            "/usr/local/bin/tesseract"
        ]
        for path in mac_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

# ----------------- GITHUB AUTO-SYNC LOGIC -----------------
def upload_to_github(token, repo, file_path, content_bytes, commit_message):
    """Commits and pushes a file directly to the GitHub repository via REST API."""
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Check if file exists to get its unique SHA key
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

def delete_from_github(token, repo, file_path, commit_message):
    """Deletes a file directly from the GitHub repository via REST API."""
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
        payload = {
            "message": commit_message,
            "sha": sha
        }
        requests.delete(url, headers=headers, json=payload)

# ----------------- DATABASE UTILITIES -----------------
def get_db_connection():
    """Establishes connection and ensures the table exists to prevent OperationalErrors."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hymns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            image_path TEXT NOT NULL,
            extracted_text TEXT
        )
    ''')
    conn.commit()
    return conn

def get_hymns(search_query=""):
    try:
        conn = get_db_connection()
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
    except Exception as e:
        st.error(f"Database Query Error: {e}")
        return []

def get_image_path(image_path):
    """Locates the image on the server, fallback to /tmp if not yet synced with Git."""
    if os.path.exists(image_path):
        return image_path
    
    # If the file hasn't synced to Git yet, it will be in the writable /tmp directory
    filename = os.path.basename(image_path)
    tmp_path = os.path.join("/tmp", filename)
    if os.path.exists(tmp_path):
        return tmp_path
        
    return image_path

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
                
                # 3. Save temporarily in writable /tmp directory on the server
                file_ext = os.path.splitext(uploaded_file.name)[1]
                unique_name = f"{uuid.uuid4()}{file_ext}"
                temp_image_path = os.path.join("/tmp", unique_name)
                
                with open(temp_image_path, "wb") as f:
                    f.write(image_bytes)

                # The path we want to record in the DB (for long-term Git usage)
                git_image_path = f"stored_hymns/{unique_name}"

                # 4. Insert record into writeable SQLite database in /tmp
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        'INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)', 
                        (upload_title, git_image_path, extracted_text)
                    )
                    conn.commit()
                    conn.close()
                except Exception as e:
                    st.error(f"Failed to write to local database: {e}")

                # 5. Sync files to GitHub Repository permanently
                if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                    token = st.secrets["GITHUB_TOKEN"]
                    repo = st.secrets["GITHUB_REPO"]
                    
                    with st.spinner("Uploading and Syncing to GitHub Repository..."):
                        # Read updated SQLite binary bytes from /tmp
                        with open(DB_NAME, "rb") as f:
                            db_bytes = f.read()
                            
                        # Commit image to stored_hymns/ and commit database file
                        success_img = upload_to_github(token, repo, git_image_path, image_bytes, f"Uploaded sheet music for '{upload_title}'")
                        success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Updated database with entry '{upload_title}'")
                        
                        if success_img and success_db:
                            st.success(f"Success! '{upload_title}' has been uploaded and permanently saved to GitHub.")
                            st.cache_data.clear() 
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
    
    # 1. Sidebar option to Delete
    if st.sidebar.button("🗑️ Delete Selected Hymn", type="secondary"):
        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
            token = st.secrets["GITHUB_TOKEN"]
            repo = st.secrets["GITHUB_REPO"]
            
            with st.spinner("Deleting and Syncing with GitHub..."):
                # Remove entry from DB
                try:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM hymns WHERE id = ?", (hymn_id,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    st.error(f"Failed to delete from local database: {e}")
                
                # Try to delete the physical image file on GitHub
                try:
                    delete_from_github(token, repo, image_path, f"Deleted hymn '{title}'")
                except Exception:
                    pass
                
                # Push updated SQLite database bytes back to Git
                with open(DB_NAME, "rb") as f:
                    db_bytes = f.read()
                success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Deleted hymn '{title}' from DB")
                
                if success_db:
                    st.success(f"'{title}' has been successfully deleted!")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to sync database deletion to GitHub.")
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM hymns WHERE id = ?", (hymn_id,))
                conn.commit()
                conn.close()
            except Exception as e:
                st.error(f"Failed to delete from local database: {e}")
            st.warning("Deleted temporarily on the server. Change will be lost when the server restarts.")
            st.cache_data.clear()
            st.rerun()

    # 2. Display Image
    resolved_path = get_image_path(image_path)
    if os.path.exists(resolved_path):
        st.image(resolved_path, use_container_width=True)
    else:
        st.error(f"Image file not found on server: {resolved_path}")
else:
    st.write("### Welcome to the Hymn Library")
    st.write("Select a hymn from the sidebar menu to begin playing.")
