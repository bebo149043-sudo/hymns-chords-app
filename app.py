import os
import sqlite3
import uuid
import base64
import shutil
import platform
import re
import requests
import streamlit as st
from PIL import Image

# Attempt to import document parsing libraries
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Attempt to import pytesseract. 
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

# Set page config
st.set_page_config(page_title="Hymn Library", layout="wide", initial_sidebar_state="expanded")

# ==========================================
# FILE UPLOADER DYNAMIC STATE INITIALIZATION
# ==========================================
if "single_file_key" not in st.session_state:
    st.session_state["single_file_key"] = "uploader_single_init"
if "multi_file_key" not in st.session_state:
    st.session_state["multi_file_key"] = "uploader_multi_init"

# =========================================================
# WARM IVORY & ACOUSTIC WOOD LIGHT-THEME STYLING
# =========================================================
st.markdown("""
    <style>
    /* Main body background - Warm Aged Paper Ivory */
    .stApp {
        background-color: #fcfaf2 !important;
        color: #2c2a29 !important;
        font-family: 'Georgia', 'Helvetica Neue', Arial, sans-serif !important;
    }
    
    /* Sidebar structural framing - Soft Sand Wood */
    section[data-testid="stSidebar"] {
        background-color: #f3f0e6 !important;
        border-right: 1px solid #dfdace !important;
    }
    
    /* Typography color accents - Rich Mahogany / Espresso */
    h1, h2, h3, h4, .stSubheader {
        color: #4a2c11 !important;
        font-weight: 800 !important;
    }
    
    /* Text labels inside widgets */
    div[data-testid="stRadio"] label, div[data-testid="stMarkdownContainer"] p {
        color: #2c2a29 !important;
        font-weight: 700 !important;
        font-size: 15px !important;
    }
    
    /* ---------------- BUTTONS COLOR PALETTE ---------------- */
    
    /* Global base button transitions */
    button {
        border-radius: 8px !important;
        padding: 10px 18px !important;
        font-weight: 800 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        transition: all 0.2s ease-in-out !important;
        cursor: pointer !important;
        transform: scale(1) !important;
    }
    button:hover {
        transform: scale(1.02) !important;
    }
    
    /* Primary Buttons (Upload & Extract) - Forest Green */
    button[kind="primary"] {
        background: linear-gradient(135deg, #2d6a4f 0%, #1b4332 100%) !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(45, 106, 79, 0.3) !important;
    }
    button[kind="primary"]:hover {
        background: linear-gradient(135deg, #40916c 0%, #2d6a4f 100%) !important;
        box-shadow: 0 6px 18px rgba(45, 106, 79, 0.5) !important;
    }

    /* Secondary Buttons (Search, Clear, View text) - Ocean Blue / Deep Teal */
    button[kind="secondary"] {
        background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%) !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(29, 78, 216, 0.3) !important;
    }
    button[kind="secondary"]:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%) !important;
        box-shadow: 0 6px 18px rgba(29, 78, 216, 0.5) !important;
    }

    /* Danger / Delete Wrapper - Crimson Red */
    .danger-btn-wrapper button {
        background: linear-gradient(135deg, #c53030 0%, #9b2c2c 100%) !important;
        color: #ffffff !important;
        border: none !important;
        box-shadow: 0 4px 12px rgba(197, 48, 48, 0.3) !important;
    }
    .danger-btn-wrapper button:hover {
        background: linear-gradient(135deg, #f56565 0%, #c53030 100%) !important;
        box-shadow: 0 6px 18px rgba(197, 48, 48, 0.5) !important;
    }

    /* ---------------- INPUTS & SELECTORS ---------------- */
    
    /* Custom input boxes - Clean light border */
    div[data-testid="stTextInput"] input {
        background-color: #ffffff !important;
        color: #2c2a29 !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        padding: 10px !important;
        font-size: 15px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #1d4ed8 !important;
        box-shadow: 0 0 10px rgba(29, 78, 216, 0.2) !important;
    }

    /* Styled Expander Panels (View Lyrics) */
    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
    }

    /* Web Workspace Menu Tabs */
    button[data-baseweb="tab"] {
        color: #64748b !important;
        font-size: 15px !important;
        font-weight: 700 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #4a2c11 !important;
        border-bottom-color: #4a2c11 !important;
    }
    </style>
""", unsafe_allow_html=True)

# Supported extensions
SUPPORTED_EXTENSIONS = ["jpg", "jpeg", "png", "bmp", "tiff", "pdf", "docx", "txt"]

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

# ----------------- FILENAME TITLE PARSER -----------------
def get_title_from_filename(filename):
    """Generates a clean title directly from the original imported filename."""
    base_name = os.path.splitext(filename)[0]
    cleaned = base_name.replace('_', ' ').replace('-', ' ').strip()
    return cleaned.title()

# ----------------- DOCUMENT TEXT EXTRACTORS -----------------
def extract_text_from_pdf(file_path):
    if not PYPDF_AVAILABLE:
        return ""
    text = ""
    try:
        reader = pypdf.PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"PDF extraction error: {e}")
    return text

def extract_text_from_docx(file_path):
    if not DOCX_AVAILABLE:
        return ""
    text = ""
    try:
        doc = docx.Document(file_path)
        text = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        print(f"DOCX extraction error: {e}")
    return text

def extract_text_from_txt(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return ""
    except Exception:
        return ""

# ----------------- ARABIC FUZZY SEARCH NORMALIZATION -----------------
def normalize_arabic(text):
    """Normalizes Arabic characters to allow spelling-tolerant, fuzzy searches."""
    if not text:
        return ""
    text = text.lower().strip()
    # Remove Tashkeel (Arabic diacritics)
    text = re.sub(r"[\u064B-\u0652]", "", text)
    # Normalize Alif variants (أ, إ, آ -> ا)
    text = re.sub(r"[أإآ]", "ا", text)
    # Normalize Yaa and Alef Layena (ى -> ي)
    text = re.sub(r"ى", "ي", text)
    # Normalize Taa Marbuta and Haa (ة -> ه)
    text = re.sub(r"ة", "ه", text)
    return text

# ----------------- DATABASE UTILITIES -----------------
def get_db_connection():
    """Establishes connection, registers custom Arabic normalizer, and ensures table exists."""
    conn = sqlite3.connect(DB_NAME, timeout=30.0)
    # Register our custom normalizer function with SQLite
    conn.create_function("normalize_arabic", 1, normalize_arabic)
    
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
            normalized_query = normalize_arabic(search_query)
            cursor.execute('''
                SELECT id, title, image_path FROM hymns 
                WHERE normalize_arabic(title) LIKE ? 
                   OR normalize_arabic(extracted_text) LIKE ? 
                ORDER BY title ASC
            ''', (f"%{normalized_query}%", f"%{normalized_query}%"))
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
    filename = os.path.basename(image_path)
    tmp_path = os.path.join("/tmp", filename)
    if os.path.exists(tmp_path):
        return tmp_path
    return image_path

# ==========================================
# APP WORKSPACE TABS
# ==========================================
tab_view, tab_import, tab_manage = st.tabs(["📖 View & Search", "➕ Import Hymns", "🛠️ Manage Library"])

# ------------------------------------------
# TAB 1: VIEW & SEARCH
# ------------------------------------------
with tab_view:
    col_side, col_main = st.columns([1, 3])

    with col_side:
        st.subheader("Hymn Index")
        view_search = st.text_input(
            "Search titles or lyrics", 
            placeholder="بحث العنوان أو الكلمات...", 
            key="view_search_box"
        )
        
        hymn_list = get_hymns(view_search)
        selected_hymn = None

        if hymn_list:
            titles = [row[1] for row in hymn_list]
            selected_title = st.radio(
                f"Songs found ({len(titles)}):",
                options=titles,
                key="view_song_selector"
            )
            selected_hymn = next(row for row in hymn_list if row[1] == selected_title)
        else:
            st.info("No hymns found.")

    with col_main:
        if selected_hymn:
            hymn_id, title, image_path = selected_hymn
            
            # Subheader and Focus Mode Toggle Layout
            col_title, col_toggle = st.columns([3, 1])
            with col_title:
                st.markdown(f"## {title}")
            with col_toggle:
                focus_mode = st.toggle(
                    "⛶ Focus Mode", 
                    value=False, 
                    help="Collapses all sidebars and headers to give you 100% fullscreen reading space."
                )
            
            # Direct CSS injection to collapse the entire page structure when in Focus Mode
            if focus_mode:
                st.markdown("""
                    <style>
                    /* Collapse sidebar menu */
                    section[data-testid="stSidebar"] {
                        display: none !important;
                    }
                    /* Collapse main top header bar */
                    header {
                        display: none !important;
                    }
                    /* Expand main container limits */
                    div[data-testid="stAppViewBlockContainer"] {
                        max-width: 100% !important;
                        padding: 1rem 2rem !important;
                    }
                    /* Hide non-active workspace tabs */
                    div[data-testid="stTabs"] [data-baseweb="tab-list"] {
                        display: none !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
            
            resolved_path = get_image_path(image_path)
            if os.path.exists(resolved_path):
                ext = os.path.splitext(resolved_path)[1].lower()
                
                # Render Based on File Type
                if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff'):
                    st.image(resolved_path, use_container_width=True)
                    
                elif ext == '.pdf':
                    try:
                        with open(resolved_path, "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="900" type="application/pdf" style="border: none; border-radius: 8px;"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Failed to display PDF: {e}")
                        
                elif ext in ('.docx', '.txt'):
                    text_content = ""
                    if ext == '.txt':
                        text_content = extract_text_from_txt(resolved_path)
                    elif ext == '.docx':
                        text_content = extract_text_from_docx(resolved_path)
                        
                    st.markdown(
                        f"<pre style='font-family: monospace; font-size: 16px; background-color: #fcfaf2; color: #2c2a29; border: 1px solid #dfdace; padding: 15px; border-radius: 8px; white-space: pre-wrap;'>{text_content}</pre>", 
                        unsafe_allow_html=True
                    )
            else:
                st.error(f"File not found on server: {resolved_path}")
            
            # View Extracted Text Expander (Hidden in Focus Mode automatically if wrapped inside tab)
            with st.expander("🔍 View Extracted Text (Lyrics & Chords)", expanded=False):
                conn = get_db_connection()
                row = conn.execute("SELECT extracted_text FROM hymns WHERE id=?", (hymn_id,)).fetchone()
                conn.close()
                text = row[0] if (row and row[0]) else ""
                
                st.text_area(
                    "Indexed OCR / Document Text:", 
                    value=text if text.strip() else "No text extracted from this hymn.",
                    height=250,
                    disabled=True
                )
        else:
            st.write("### Welcome to the Hymn Library")
            st.write("Select a hymn from the index on the left to display sheet music.")

# ------------------------------------------
# TAB 2: IMPORT HYMNS
# ------------------------------------------
with tab_import:
    st.header("Import Hymns")
    
    import_mode = st.radio("Upload Mode:", ["Single File Upload", "Multiple Files / Folder Upload"], horizontal=True)

    if import_mode == "Single File Upload":
        # Uses dynamically rotated key to auto-clear files on success
        uploaded_file = st.file_uploader(
            "Select Sheet Music Image or Document", 
            type=SUPPORTED_EXTENSIONS, 
            key=st.session_state["single_file_key"]
        )
        
        if uploaded_file:
            detected_title = get_title_from_filename(uploaded_file.name)
            final_title = st.text_input("Hymn Title (العنوان):", value=detected_title)

            if st.button("Confirm and Upload", type="primary"):
                with st.spinner("Processing Upload and Text Extraction..."):
                    file_bytes = uploaded_file.getvalue()
                    file_ext = os.path.splitext(uploaded_file.name)[1].lower()
                    
                    # Save temporarily to /tmp
                    unique_name = f"{uuid.uuid4()}{file_ext}"
                    temp_image_path = os.path.join("/tmp", unique_name)
                    with open(temp_image_path, "wb") as f:
                        f.write(file_bytes)

                    # Extract text
                    extracted_text = ""
                    if file_ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff'):
                        if PYTESSERACT_AVAILABLE:
                            try:
                                img = Image.open(uploaded_file)
                                extracted_text = pytesseract.image_to_string(img, lang='ara+eng')
                            except Exception as e:
                                st.error(f"OCR Error: {e}")
                    elif file_ext == '.pdf':
                        extracted_text = extract_text_from_pdf(temp_image_path)
                    elif file_ext == '.docx':
                        extracted_text = extract_text_from_docx(temp_image_path)
                    elif file_ext == '.txt':
                        extracted_text = extract_text_from_txt(temp_image_path)

                    git_image_path = f"stored_hymns/{unique_name}"

                    # Insert to DB
                    try:
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            'INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)', 
                            (final_title, git_image_path, extracted_text)
                        )
                        conn.commit()
                        conn.close()
                    except Exception as e:
                        st.error(f"Failed to write to local database: {e}")

                    # Push to GitHub
                    if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                        token = st.secrets["GITHUB_TOKEN"]
                        repo = st.secrets["GITHUB_REPO"]
                        
                        with open(DB_NAME, "rb") as f:
                            db_bytes = f.read()
                        
                        success_img = upload_to_github(token, repo, git_image_path, file_bytes, f"Uploaded '{final_title}'")
                        success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Updated database with '{final_title}'")
                        
                        if success_img and success_db:
                            st.success(f"Successfully uploaded and permanently synced '{final_title}'!")
                            
                            # Rotate single file uploader key to wipe the UI files
                            st.session_state["single_file_key"] = f"uploader_single_{uuid.uuid4()}"
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Error syncing with GitHub. Check secrets token configurations.")
                    else:
                        st.warning("GITHUB_TOKEN not configured. Song is saved temporarily on the server.")
                        st.session_state["single_file_key"] = f"uploader_single_{uuid.uuid4()}"
                        st.cache_data.clear()
                        st.rerun()

    else:
        # Multiple Uploads
        uploaded_files = st.file_uploader(
            "Select multiple images/documents (or select all inside a folder)", 
            type=SUPPORTED_EXTENSIONS, 
            accept_multiple_files=True,
            key=st.session_state["multi_file_key"]
        )
        
        if uploaded_files:
            st.write(f"Selected {len(uploaded_files)} files.")
            
            if st.button("Extract & Upload All", type="primary"):
                progress_bar = st.progress(0)
                status_txt = st.empty()
                
                conn = get_db_connection()
                cursor = conn.cursor()

                uploaded_images = [] 
                
                for idx, file in enumerate(uploaded_files):
                    status_txt.write(f"Processing [{idx+1}/{len(uploaded_files)}]: {file.name}")
                    
                    file_bytes = file.getvalue()
                    file_ext = os.path.splitext(file.name)[1].lower()
                    
                    # Save locally temporarily to /tmp
                    unique_name = f"{uuid.uuid4()}{file_ext}"
                    temp_image_path = os.path.join("/tmp", unique_name)
                    with open(temp_image_path, "wb") as f:
                        f.write(file_bytes)

                    # Extract searchable text
                    extracted_text = ""
                    if file_ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff'):
                        if PYTESSERACT_AVAILABLE:
                            try:
                                img = Image.open(file)
                                extracted_text = pytesseract.image_to_string(img, lang='ara+eng')
                            except Exception:
                                pass
                    elif file_ext == '.pdf':
                        extracted_text = extract_text_from_pdf(temp_image_path)
                    elif file_ext == '.docx':
                        extracted_text = extract_text_from_docx(temp_image_path)
                    elif file_ext == '.txt':
                        extracted_text = extract_text_from_txt(temp_image_path)
                    
                    detected_title = get_title_from_filename(file.name)
                    git_image_path = f"stored_hymns/{unique_name}"
                    
                    # Add to database
                    cursor.execute(
                        'INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)', 
                        (detected_title, git_image_path, extracted_text)
                    )
                    
                    uploaded_images.append((git_image_path, file_bytes, detected_title))
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                conn.commit()
                conn.close()

                # Sync Batch to GitHub
                if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                    token = st.secrets["GITHUB_TOKEN"]
                    repo = st.secrets["GITHUB_REPO"]
                    
                    status_txt.write("Syncing files with GitHub...")
                    
                    # Push images/documents
                    img_failures = 0
                    for git_path, img_bytes, s_title in uploaded_images:
                        if not upload_to_github(token, repo, git_path, img_bytes, f"Batch upload '{s_title}'"):
                            img_failures += 1
                    
                    # Push database
                    with open(DB_NAME, "rb") as f:
                        db_bytes = f.read()
                    success_db = upload_to_github(token, repo, REPO_DB, db_bytes, "Batch update database")
                    
                    status_txt.empty()
                    progress_bar.empty()
                    
                    if success_db and img_failures == 0:
                        st.success(f"Batch upload complete! Successfully processed and permanently synced {len(uploaded_files)} hymns.")
                        
                        # Rotate multi file uploader key to wipe the UI files
                        st.session_state["multi_file_key"] = f"uploader_multi_{uuid.uuid4()}"
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error(f"Database synced, but {img_failures} files failed to push. Verify token permissions.")
                else:
                    status_txt.empty()
                    progress_bar.empty()
                    st.warning("Batch complete, but saved only temporarily (no GITHUB_TOKEN configured).")
                    st.session_state["multi_file_key"] = f"uploader_multi_{uuid.uuid4()}"
                    st.cache_data.clear()
                    st.rerun()

# ------------------------------------------
# TAB 3: MANAGE LIBRARY
# ------------------------------------------
with tab_manage:
    st.header("Library Administration")
    
    all_hymns = get_hymns("")
    
    if all_hymns:
        st.subheader("Bulk Deletion")
        st.write("Select one or more hymns below to permanently delete them from the library and from GitHub.")
        
        # Map titles to database rows
        hymn_map = {row[1]: row for row in all_hymns}
        
        to_delete = st.multiselect("Select hymns to delete:", options=list(hymn_map.keys()))
        
        # Wrapped in custom danger container to force red styling
        st.markdown("<div class='danger-btn-wrapper'>", unsafe_allow_html=True)
        if st.button("🗑️ Delete Selected Hymns", type="secondary"):
            if not to_delete:
                st.warning("Please select at least one hymn to delete.")
            else:
                with st.spinner("Deleting files and syncing with GitHub..."):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # Check token
                    has_github = "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets
                    if has_github:
                        token = st.secrets["GITHUB_TOKEN"]
                        repo = st.secrets["GITHUB_REPO"]
                    
                    deleted_count = 0
                    for title in to_delete:
                        hymn_id, _, image_path = hymn_map[title]
                        
                        # 1. Remove from SQLite in /tmp
                        cursor.execute("DELETE FROM hymns WHERE id = ?", (hymn_id,))
                        
                        # 2. Delete from GitHub if connected
                        if has_github:
                            try:
                                delete_from_github(token, repo, image_path, f"Deleted hymn '{title}'")
                            except Exception:
                                pass 
                        
                        deleted_count += 1
                        
                    conn.commit()
                    conn.close()
                    
                    # Sync DB to GitHub
                    if has_github:
                        with open(DB_NAME, "rb") as f:
                            db_bytes = f.read()
                        success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Batch deleted {deleted_count} hymns")
                        
                        if success_db:
                            st.success(f"Permanently deleted {deleted_count} hymns and synced with GitHub!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Deleted from local session database, but failed to sync changes back to GitHub.")
                    else:
                        st.warning(f"Deleted {deleted_count} hymns locally. Changes will be lost when the server restarts.")
                        st.cache_data.clear()
                        st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("No hymns in the library to manage.")