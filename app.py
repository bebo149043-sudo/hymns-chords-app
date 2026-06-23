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

# ----------------- INTELLECTUAL MUSIC CHORD ANALYZER -----------------
def extract_ai_chords(lyrics, api_key, target_key):
    """Calls Google Gemini API to analyze lyrics and align high-quality chords [13]."""
    # FIXED: Swapped to the stable v1 endpoint
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
    
    # FIXED: API Key is now passed securely in the 'x-goog-api-key' header instead of the URL
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    
    prompt = (
        "You are an expert musician and worship leader. I will give you the lyrics of a Christian hymn (which may be in Arabic or English).\n"
        f"Your task is to analyze the lyrics, set them in the musical key of '{target_key}', and write suitable, beautiful chord progressions (using standard chords like C, G, Am, F, Dm, Em, etc.).\n"
        "You must place these chords EXACTLY above the syllables/words where they should be played, using spaces for horizontal alignment.\n"
        "Keep the output formatted cleanly so it can be rendered in a monospaced font.\n"
        "Do not include any introductory, explaining, or concluding text. Only return the final raw lyrics with chords formatted.\n\n"
        f"Lyrics:\n{lyrics}"
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30.0)
        if response.status_code == 200:
            data = response.json()
            ai_text = data["contents"][0]["parts"][0]["text"] if "contents" in data else data["candidates"][0]["content"]["parts"][0]["text"]
            # Clean up potential markdown formatting code blocks returned by Gemini
            if ai_text.startswith("```"):
                ai_text = re.sub(r"^```[^\n]*\n", "", ai_text)
                ai_text = re.sub(r"\n```$", "", ai_text)
            return ai_text.strip()
        else:
            return f"Gemini API Error (Status {response.status_code}): {response.text}"
    except Exception as e:
        return f"Failed to harmonize chords via API: {e}"

def generate_local_heuristic_chords(text, target_key):
    """Mathematical local fallback to automatically overlay standard chord progressions."""
    progression = ["C", "G", "Am", "F"] if ("C" in target_key or "Am" in target_key) else ["G", "D", "Em", "C"]
    
    lines = text.split("\n")
    output = []
    chord_idx = 0
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            output.append("")
            continue
        
        # Check if line is already chords
        chord_chars = set("abcdefg#m7susadd/123456789 ")
        if set(line_stripped.lower()).issubset(chord_chars) and len(line_stripped) < 15:
            output.append(line)
            continue
            
        words = line_stripped.split()
        if len(words) >= 4:
            c1 = progression[chord_idx % 4]
            chord_idx += 1
            c2 = progression[chord_idx % 4]
            chord_idx += 1
            
            # Estimate horizontal padding
            space_len = max(len(line_stripped) // 2, 5)
            chord_line = c1 + " " * space_len + c2
        else:
            c1 = progression[chord_idx % 4]
            chord_idx += 1
            chord_line = c1
            
        output.append(chord_line)
        output.append(line)
        
    return "\n".join(output)

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
# GLOBAL FULLSCREEN OVERLAY INJECTION (100% INSIDE THE APP)
# ==========================================
if "fullscreen_active" not in st.session_state:
    st.session_state["fullscreen_active"] = False

# If fullscreen is active, hijack rendering to show ONLY the edge-to-edge document viewport
if st.session_state["fullscreen_active"] and "current_selected_id" in st.session_state:
    conn = get_db_connection()
    active_row = conn.execute("SELECT id, title, image_path FROM hymns WHERE id = ?", (st.session_state["current_selected_id"],)).fetchone()
    conn.close()
    
    if active_row:
        h_id, h_title, h_path = active_row
        resolved_path = get_image_path(h_path)
        ext = os.path.splitext(resolved_path)[1].lower()
        
        # Inject CSS to override and clear all default layouts, sidebars, and paddings
        st.markdown("""
            <style>
            section[data-testid="stSidebar"] { display: none !important; }
            header { display: none !important; }
            footer { display: none !important; }
            div[data-testid="stAppViewBlockContainer"] {
                max-width: 100% !important;
                padding: 0 !important;
                margin: 0 !important;
                background-color: #fcfaf2 !important; /* Soft warm ivory paper */
            }
            .pdf-iframe {
                height: 94vh !important;
                width: 100% !important;
                border: none !important;
                overflow: auto !important;
                -webkit-overflow-scrolling: touch !important;
            }
            pre {
                background-color: #fcfaf2 !important;
                color: #2c2a29 !important;
                height: 94vh !important;
                overflow-y: auto !important;
                padding: 20px !important;
                font-size: 18px !important;
                white-space: pre-wrap !important;
                border: none !important;
            }
            </style>
        """, unsafe_allow_html=True)
        
        # Mini Header Toolbar
        col_fs_title, col_fs_close = st.columns([5, 1])
        with col_fs_title:
            st.markdown(f"<h2 style='color: #4a2c11; margin-left: 20px; margin-top: 10px;'>{h_title}</h2>", unsafe_allow_html=True)
        with col_fs_close:
            st.markdown("<div style='margin-top: 10px; margin-right: 20px;'>", unsafe_allow_html=True)
            if st.button("❌ Close", type="primary"):
                st.session_state["fullscreen_active"] = False
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            
        # Display active document
        if os.path.exists(resolved_path):
            if ext in ('.jpg', '.jpeg', '.png', '.bmp', '.tiff'):
                st.image(resolved_path, use_container_width=True)
            elif ext == '.pdf':
                try:
                    with open(resolved_path, "rb") as f:
                        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                    # Displays inside a seamless viewport with momentum-touch scrolling active
                    pdf_display = f'<iframe class="pdf-iframe" src="data:application/pdf;base64,{base64_pdf}"></iframe>'
                    st.markdown(pdf_display, unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Failed to display PDF: {e}")
            elif ext in ('.docx', '.txt'):
                text_content = extract_text_from_txt(resolved_path) if ext == '.txt' else extract_text_from_docx(resolved_path)
                st.markdown(f"<pre>{text_content}</pre>", unsafe_allow_html=True)
        else:
            st.error("Document not found on the server.")
            
        # Stops the execution here to keep only the fullscreen container on screen
        st.stop()

# ==========================================
# APP WORKSPACE TABS (Standard Layout)
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
            
            # Save selection to remember during Fullscreen Rerun
            if selected_hymn:
                st.session_state["current_selected_id"] = selected_hymn[0]
        else:
            st.info("No hymns found.")

    with col_main:
        if selected_hymn:
            hymn_id, title, image_path = selected_hymn
            
            # Subheader and Fullscreen Button Layout
            col_title, col_btn = st.columns([3, 1])
            with col_title:
                st.markdown(f"## {title}")
            with col_btn:
                # Triggers the new, robust Fullscreen Overlay Mode
                if st.button("⛶ Full Screen", type="secondary"):
                    st.session_state["fullscreen_active"] = True
                    st.rerun()
            
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
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf" style="border: none; border-radius: 8px;"></iframe>'
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
            
            # View Extracted Text Expander
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
                
            # ----------------- EXPANDED MULTI-SOURCE CHORD GENERATOR -----------------
            with st.expander("🎸 AI Chord Generator (Auto-Harmonize)", expanded=False):
                st.write("Generate beautiful, aligned guitar/piano chords right above your hymn lyrics!")
                
                # Dynamic Lyrics Source Selection
                source_mode = st.radio(
                    "Select Lyrics Source:", 
                    ["Use Active Hymn", "Paste / Write Lyrics", "Upload Lyrics File"], 
                    horizontal=True,
                    key="ai_lyrics_source_select"
                )
                
                raw_text = ""
                temp_title_placeholder = ""
                
                if source_mode == "Use Active Hymn":
                    conn = get_db_connection()
                    row = conn.execute("SELECT extracted_text FROM hymns WHERE id=?", (hymn_id,)).fetchone()
                    conn.close()
                    raw_text = row[0] if (row and row[0]) else ""
                    temp_title_placeholder = title
                    if not raw_text.strip():
                        st.warning("This hymn has no extracted text or lyrics yet. Please choose another source option or make sure the OCR has run.")
                        
                elif source_mode == "Paste / Write Lyrics":
                    raw_text = st.text_area("Paste or write your lyrics here:", height=200, placeholder="أكتب كلمات الترنيمة هنا...", key="ai_pasted_lyrics_box")
                    temp_title_placeholder = "New Harmonized Hymn"
                    
                elif source_mode == "Upload Lyrics File":
                    ai_uploaded_file = st.file_uploader(
                        "Upload a text, docx, or pdf file containing lyrics", 
                        type=["txt", "docx", "pdf"], 
                        key="ai_chord_file_uploader"
                    )
                    if ai_uploaded_file:
                        file_bytes = ai_uploaded_file.getvalue()
                        file_ext = os.path.splitext(ai_uploaded_file.name)[1].lower()
                        temp_path = os.path.join("/tmp", f"ai_temp_{uuid.uuid4()}{file_ext}")
                        
                        with open(temp_path, "wb") as f:
                            f.write(file_bytes)
                        
                        if file_ext == '.pdf':
                            raw_text = extract_text_from_pdf(temp_path)
                        elif file_ext == '.docx':
                            raw_text = extract_text_from_docx(temp_path)
                        elif file_ext == '.txt':
                            raw_text = extract_text_from_txt(temp_path)
                        
                        temp_title_placeholder = get_title_from_filename(ai_uploaded_file.name)
                        st.text_area("Extracted Lyrics Preview:", value=raw_text, height=150, disabled=True, key="ai_extracted_preview")

                chord_key = st.selectbox("Select Key Signature:", ["C Major", "G Major", "A Minor", "E Minor"], key="ai_chord_key_select")
                
                # Session state keys configuration
                session_chord_key = f"generated_chords_active" if source_mode != "Use Active Hymn" else f"generated_chords_{hymn_id}"
                
                if raw_text.strip():
                    if st.button("Generate Chords", type="primary", key="ai_generate_chords_btn"):
                        if "GEMINI_API_KEY" in st.secrets:
                            api_key = st.secrets["GEMINI_API_KEY"]
                            with st.spinner("AI is analyzing lyrics and placing chords..."):
                                chords_output = extract_ai_chords(raw_text, api_key, chord_key)
                                st.session_state[session_chord_key] = chords_output
                        else:
                            with st.spinner("Generating local fallback chords... (Add GEMINI_API_KEY in secrets for professional chords!)"):
                                chords_output = generate_local_heuristic_chords(raw_text, chord_key)
                                st.session_state[session_chord_key] = chords_output
                    
                    # Display and Save logic
                    if session_chord_key in st.session_state:
                        generated_text = st.session_state[session_chord_key]
                        st.markdown(
                            f"<pre style='font-family: monospace; font-size: 16px; background-color: #fcfaf2; color: #2c2a29; border: 1px solid #dfdace; padding: 15px; border-radius: 8px; white-space: pre-wrap;'>{generated_text}</pre>", 
                            unsafe_allow_html=True
                        )
                        
                        if source_mode == "Use Active Hymn":
                            if st.button("💾 Save Chords to Active Hymn", key="save_to_active_btn"):
                                with st.spinner("Saving and Syncing with GitHub..."):
                                    # Update locally
                                    conn = get_db_connection()
                                    conn.execute("UPDATE hymns SET extracted_text = ? WHERE id = ?", (generated_text, hymn_id))
                                    conn.commit()
                                    conn.close()
                                    
                                    # Push updated DB to Git
                                    if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                                        token = st.secrets["GITHUB_TOKEN"]
                                        repo = st.secrets["GITHUB_REPO"]
                                        with open(DB_NAME, "rb") as f:
                                            db_bytes = f.read()
                                        success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Saved generated chords to '{title}'")
                                        if success_db:
                                            st.success("Chords successfully saved and synced permanently to GitHub!")
                                            st.rerun()
                                        else:
                                            st.error("Saved locally, but failed to sync changes to GitHub.")
                                    else:
                                        st.warning("Saved temporarily (GITHUB_TOKEN not configured in secrets).")
                                        st.rerun()
                        else:
                            # Save as a NEW hymn in the library
                            st.write("---")
                            st.subheader("💾 Save Chords as a New Hymn")
                            new_hymn_title = st.text_input("Enter New Hymn Title:", value=temp_title_placeholder, key="new_hymn_title_input")
                            
                            if st.button("💾 Save as New Hymn", key="save_as_new_btn"):
                                if not new_hymn_title.strip():
                                    st.error("Please enter a valid title.")
                                else:
                                    with st.spinner("Creating new hymn and syncing to GitHub..."):
                                        # 1. Save chords as a .txt file inside /tmp
                                        unique_name = f"{uuid.uuid4()}.txt"
                                        temp_file_path = os.path.join("/tmp", unique_name)
                                        with open(temp_file_path, "w", encoding="utf-8") as f:
                                            f.write(generated_text)
                                            
                                        git_file_path = f"stored_hymns/{unique_name}"
                                        
                                        # 2. Insert to local DB
                                        conn = get_db_connection()
                                        cursor = conn.cursor()
                                        cursor.execute(
                                            'INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)',
                                            (new_hymn_title, git_file_path, generated_text)
                                        )
                                        conn.commit()
                                        conn.close()
                                        
                                        # 3. Sync file and updated DB back to GitHub
                                        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
                                            token = st.secrets["GITHUB_TOKEN"]
                                            repo = st.secrets["GITHUB_REPO"]
                                            
                                            with open(DB_NAME, "rb") as f:
                                                db_bytes = f.read()
                                            with open(temp_file_path, "rb") as f:
                                                file_bytes = f.read()
                                                
                                            success_file = upload_to_github(token, repo, git_file_path, file_bytes, f"Uploaded new harmonized hymn text '{new_hymn_title}'")
                                            success_db = upload_to_github(token, repo, REPO_DB, db_bytes, f"Updated database with '{new_hymn_title}'")
                                            
                                            if success_file and success_db:
                                                st.success(f"Successfully saved and permanently synced '{new_hymn_title}' to your library!")
                                                st.cache_data.clear()
                                                st.rerun()
                                            else:
                                                st.error("Failed to sync to GitHub. Check your token permissions.")
                                        else:
                                            st.warning("Saved temporarily on server (no GITHUB_TOKEN configured).")
                                            st.cache_data.clear()
                                            st.rerun()
                else:
                    st.info("Please provide or upload some lyrics to generate chords.")
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