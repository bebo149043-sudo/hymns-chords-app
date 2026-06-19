import os
import sqlite3
import shutil
import uuid
import platform
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image, ImageTk

# Attempt to import pytesseract. 
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

# ==========================================
# AUTOMATIC MAC/WINDOWS PATH RESOLUTION
# ==========================================
if PYTESSERACT_AVAILABLE:
    if platform.system() == "Darwin":  # macOS
        mac_paths = [
            "/opt/homebrew/bin/tesseract",  # Apple Silicon M1/M2/M3/M4
            "/usr/local/bin/tesseract"      # Intel Macs
        ]
        for path in mac_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

class HymnLibraryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hymn Library & Viewer")
        self.root.geometry("1150x780")

        # Database and Storage Settings
        self.db_name = "hymns_database.db"
        self.images_dir = "stored_hymns"
        self.init_db()

        # State Variables
        self.current_results = []
        self.current_image_path = None
        self.current_pil_image = None
        self.current_tk_image = None
        self.fs_tk_image = None  # Reference specifically for fullscreen mode
        self.last_canvas_width = 0

        # Enable macOS copy, paste, and select bindings
        self.bind_macos_shortcuts()

        # Apply Modern Creative Theme
        self.apply_creative_theme()

        # Create GUI Layout
        self.setup_gui()
        
        # Load all hymns on startup
        self.search_query("")
        
        # Verify that Arabic language is supported by Tesseract on startup
        self.check_arabic_support()

    def init_db(self):
        if not os.path.exists(self.images_dir):
            os.makedirs(self.images_dir)
        conn = sqlite3.connect(self.db_name)
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
        conn.close()

    def apply_creative_theme(self):
        """Customizes the styling to create a beautiful dark-mode interface."""
        # Theme Color Palette
        self.BG_DARK = "#12131a"        # Clean dark background
        self.BG_SIDEBAR = "#1a1b23"     # Darker sidebar
        self.ACCENT_COLOR = "#6366f1"   # Indigo
        self.ACCENT_HOVER = "#4f46e5"   # Darker Indigo
        self.TEXT_COLOR = "#f3f4f6"     # Off-white
        self.TEXT_MUTED = "#9ca3af"     # Soft gray
        self.LIST_BG = "#1f2937"        # Dark listbox background
        self.BUTTON_BG = "#2e303f"      # Flat dark gray buttons
        self.ENTRY_BG = "#2e303f"       # Dark gray fields

        self.root.configure(bg=self.BG_DARK)

        style = ttk.Style()
        style.theme_use("clam")

        # Global Widget Defaults
        style.configure(".", background=self.BG_DARK, foreground=self.TEXT_COLOR)
        style.configure("TFrame", background=self.BG_DARK)
        style.configure("Sidebar.TFrame", background=self.BG_SIDEBAR)

        # Labels
        style.configure("TLabel", background=self.BG_DARK, foreground=self.TEXT_COLOR)
        style.configure("Muted.TLabel", background=self.BG_SIDEBAR, foreground=self.TEXT_MUTED)

        # Label Frame styling
        style.configure("TLabelframe", background=self.BG_SIDEBAR, bordercolor="#2e303f")
        style.configure("TLabelframe.Label", background=self.BG_SIDEBAR, foreground=self.TEXT_MUTED, font=("Helvetica", 11, "bold"))

        # Primary Buttons
        style.configure("TButton", 
                        background=self.BUTTON_BG, 
                        foreground=self.TEXT_COLOR, 
                        borderwidth=0, 
                        focusthickness=0, 
                        font=("Helvetica", 10, "bold"),
                        padding=(10, 6))
        style.map("TButton",
                  background=[("active", self.ACCENT_HOVER), ("pressed", "#3730a3")],
                  foreground=[("active", "#ffffff")])

        # Accent / Feature Buttons
        style.configure("Accent.TButton", 
                        background=self.ACCENT_COLOR, 
                        foreground="#ffffff", 
                        font=("Helvetica", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", self.ACCENT_HOVER), ("pressed", "#3730a3")])

        # Destructive Action Buttons (Delete)
        style.configure("Danger.TButton", 
                        background="#ef4444", 
                        foreground="#ffffff", 
                        font=("Helvetica", 10, "bold"))
        style.map("Danger.TButton",
                  background=[("active", "#dc2626"), ("pressed", "#991b1b")])

        # Text Input Box Styling
        style.configure("TEntry", 
                        fieldbackground=self.ENTRY_BG, 
                        foreground=self.TEXT_COLOR, 
                        bordercolor="#374151", 
                        lightcolor="#374151", 
                        darkcolor="#374151",
                        insertcolor=self.TEXT_COLOR)

    def check_arabic_support(self):
        """Warns the user on startup if Tesseract is missing the Arabic language pack."""
        if not PYTESSERACT_AVAILABLE:
            return
        try:
            available_langs = pytesseract.get_languages(config='')
            if 'ara' not in available_langs:
                messagebox.showwarning(
                    "Arabic Support Missing",
                    "The Arabic language pack ('ara') was not detected by Tesseract.\n\n"
                    "Arabic text inside photos will not be searchable.\n\n"
                    "Please execute the curl command in your Terminal to download the 'ara.traineddata' file."
                )
        except Exception as e:
            pass

    def bind_macos_shortcuts(self):
        if platform.system() == "Darwin":
            self.root.bind_class("Entry", "<Command-c>", "<<Copy>>")
            self.root.bind_class("Entry", "<Command-v>", "<<Paste>>")
            self.root.bind_class("Entry", "<Command-x>", "<<Cut>>")
            self.root.bind_class("Entry", "<Command-a>", self.select_all)
            
            self.root.bind_class("Text", "<Command-c>", "<<Copy>>")
            self.root.bind_class("Text", "<Command-v>", "<<Paste>>")
            self.root.bind_class("Text", "<Command-x>", "<<Cut>>")
            self.root.bind_class("Text", "<Command-a>", self.select_all)

    def select_all(self, event):
        event.widget.select_range(0, 'end')
        event.widget.icursor('end')
        return "break"

    def setup_gui(self):
        """Sets up the layout of the Tkinter application."""
        self.paned_window = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # ----------------- SIDEBAR PANEL (Left) -----------------
        sidebar = ttk.Frame(self.paned_window, width=320, padding=12, style="Sidebar.TFrame")
        self.paned_window.add(sidebar, weight=0)

        # Search Controls Frame
        search_frame = ttk.LabelFrame(sidebar, text="Search Hymns", padding=8)
        search_frame.pack(fill=tk.X, pady=(0, 10))

        self.search_entry = ttk.Entry(search_frame, font=("Arial", 14), style="TEntry")
        self.search_entry.pack(fill=tk.X, side=tk.TOP, pady=5)
        self.search_entry.bind("<KeyRelease>", self.on_search_keypress)

        btn_frame = ttk.Frame(search_frame, style="Sidebar.TFrame")
        btn_frame.pack(fill=tk.X, side=tk.TOP, pady=2)

        ttk.Button(btn_frame, text="Search", command=self.trigger_search).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="Clear", command=self.clear_search).pack(side=tk.RIGHT, padx=2, expand=True, fill=tk.X)

        # Listbox for search results
        list_frame = ttk.Frame(sidebar, style="Sidebar.TFrame")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.results_listbox = tk.Listbox(
            list_frame, 
            selectmode=tk.EXTENDED, 
            font=("Helvetica", 13),
            bg=self.LIST_BG,
            fg=self.TEXT_COLOR,
            selectbackground=self.ACCENT_COLOR,
            selectforeground="#ffffff",
            bd=0,
            highlightthickness=1,
            highlightcolor="#374151",
            highlightbackground="#1a1b23"
        )
        list_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.results_listbox.yview)
        self.results_listbox.configure(yscrollcommand=list_scrollbar.set)

        self.results_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.results_listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        # Import & Manage Frame
        action_frame = ttk.LabelFrame(sidebar, text="Manage Library", padding=8)
        action_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(action_frame, text="Import Single Image", command=self.import_single_hymn).pack(fill=tk.X, pady=3)
        ttk.Button(action_frame, text="Import Multiple Images", command=self.import_multiple_hymns).pack(fill=tk.X, pady=3)
        ttk.Button(action_frame, text="Import Folder", command=self.import_folder).pack(fill=tk.X, pady=3)
        ttk.Button(action_frame, text="View Extracted Text", command=self.view_extracted_text).pack(fill=tk.X, pady=3)
        
        ttk.Button(action_frame, text="Delete Selected", command=self.delete_hymn, style="Danger.TButton").pack(fill=tk.X, pady=(12, 3))

        # Status Label at the bottom of the sidebar
        self.status_label = ttk.Label(sidebar, text="Ready.", anchor="w", font=("Arial", 9, "italic"), style="Muted.TLabel")
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        # ----------------- VIEWER PANEL (Right) -----------------
        viewer_frame = ttk.Frame(self.paned_window, padding=8)
        self.paned_window.add(viewer_frame, weight=1)

        # Top Toolbar inside the viewer frame
        toolbar = ttk.Frame(viewer_frame, padding=5)
        toolbar.pack(fill=tk.X, side=tk.TOP, pady=(0, 6))

        self.hymn_title_label = ttk.Label(
            toolbar, 
            text="No hymn selected", 
            font=("Helvetica", 13, "bold"), 
            foreground=self.TEXT_COLOR
        )
        self.hymn_title_label.pack(side=tk.LEFT, padx=5)

        self.fullscreen_btn = ttk.Button(
            toolbar, 
            text="⛶ Full Screen", 
            command=self.open_fullscreen,
            style="Accent.TButton"
        )
        self.fullscreen_btn.pack(side=tk.RIGHT, padx=5)

        # Main Viewer Canvas with scrollbars
        self.canvas_container = ttk.Frame(viewer_frame)
        self.canvas_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_container, bg="#0f1015", highlightthickness=0)
        self.v_scrollbar = ttk.Scrollbar(self.canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scrollbar = ttk.Scrollbar(self.canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")

        self.canvas_container.rowconfigure(0, weight=1)
        self.canvas_container.columnconfigure(0, weight=1)

        # Bind zoom/resize and scrolling events
        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel) 
        self.canvas.bind("<Button-5>", self.on_mousewheel) 

        # Shortcuts for sheet music navigation
        self.root.bind("<Prior>", lambda e: self.canvas.yview_scroll(-1, "pages"))
        self.root.bind("<Next>", lambda e: self.canvas.yview_scroll(1, "pages"))
        self.root.bind("<Up>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.root.bind("<Down>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.root.bind("<f>", lambda e: self.open_fullscreen())

    # ----------------- REUSABLE IMPORT PROCESSOR -----------------
    def process_and_save_image(self, file_path, title=None, db_cursor=None):
        if not title:
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            title = base_name.replace('_', ' ').replace('-', ' ').strip().title()

        extracted_text = ""
        if PYTESSERACT_AVAILABLE:
            try:
                img = Image.open(file_path)
                # Performs combined Arabic and English OCR scanning
                extracted_text = pytesseract.image_to_string(img, lang='ara+eng')
            except Exception as e:
                print(f"OCR Error: {e}")

        file_ext = os.path.splitext(file_path)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        dest_path = os.path.join(self.images_dir, unique_filename)

        try:
            shutil.copy(file_path, dest_path)
        except Exception as e:
            return False

        db_cursor.execute('INSERT INTO hymns (title, image_path, extracted_text) VALUES (?, ?, ?)', 
                          (title, dest_path, extracted_text))
        return True

    # ----------------- IMPORT ACTIONS -----------------
    def import_single_hymn(self):
        file_path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not file_path: return
        title = simpledialog.askstring("Title", "Enter title:", initialvalue=os.path.splitext(os.path.basename(file_path))[0])
        if not title: return

        self.root.config(cursor="watch")
        self.status_label.config(text="Processing Arabic OCR...")
        self.root.update()

        conn = sqlite3.connect(self.db_name)
        self.process_and_save_image(file_path, title=title, db_cursor=conn.cursor())
        conn.commit()
        conn.close()

        self.root.config(cursor="")
        self.status_label.config(text="Ready.")
        self.search_query(self.search_entry.get())

    def import_multiple_hymns(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not file_paths: return
        self.root.config(cursor="watch")
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        for i, path in enumerate(file_paths):
            self.status_label.config(text=f"Scanning {i+1}/{len(file_paths)}...")
            self.root.update()
            self.process_and_save_image(path, db_cursor=cursor)
        conn.commit()
        conn.close()
        self.root.config(cursor="")
        self.status_label.config(text="Ready.")
        self.search_query(self.search_entry.get())

    def import_folder(self):
        folder = filedialog.askdirectory()
        if not folder: return
        exts = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff')
        files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(exts)]
        if not files: return
        if not messagebox.askyesno("Confirm", f"Import {len(files)} Arabic hymns?"): return
        
        self.root.config(cursor="watch")
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        for i, path in enumerate(files):
            self.status_label.config(text=f"Scanning {i+1}/{len(files)}...")
            self.root.update()
            self.process_and_save_image(path, db_cursor=cursor)
        conn.commit()
        conn.close()
        self.root.config(cursor="")
        self.status_label.config(text="Ready.")
        self.search_query("")

    def delete_hymn(self):
        selected = self.results_listbox.curselection()
        if not selected: return
        if not messagebox.askyesno("Delete", f"Delete {len(selected)} songs?"): return

        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        deleted_paths = []
        for idx in selected:
            h_id, title, img_path = self.current_results[idx]
            cursor.execute("DELETE FROM hymns WHERE id = ?", (h_id,))
            if os.path.exists(img_path): os.remove(img_path)
            deleted_paths.append(img_path)
        conn.commit()
        conn.close()

        if self.current_image_path in deleted_paths:
            self.canvas.delete("all")
            self.current_pil_image = None
            self.hymn_title_label.config(text="No hymn selected")
        self.search_query(self.search_entry.get())

    def view_extracted_text(self):
        selected = self.results_listbox.curselection()
        if not selected: return
        h_id = self.current_results[selected[0]][0]
        conn = sqlite3.connect(self.db_name)
        text = conn.execute("SELECT extracted_text FROM hymns WHERE id=?", (h_id,)).fetchone()[0]
        conn.close()

        win = tk.Toplevel(self.root)
        win.title("Detected Arabic Text")
        txt = tk.Text(win, wrap=tk.WORD, font=("Arial", 14), padx=10, pady=10)
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, text if text.strip() else "No Arabic text found.")
        txt.config(state=tk.DISABLED)

    # ----------------- SEARCH LOGIC -----------------
    def on_search_keypress(self, event): self.trigger_search()
    def trigger_search(self): self.search_query(self.search_entry.get())
    def clear_search(self): self.search_entry.delete(0, tk.END); self.search_query("")

    def search_query(self, text):
        conn = sqlite3.connect(self.db_name)
        if not text.strip():
            cursor = conn.execute("SELECT id, title, image_path FROM hymns ORDER BY title ASC")
        else:
            cursor = conn.execute("SELECT id, title, image_path FROM hymns WHERE title LIKE ? OR extracted_text LIKE ? ORDER BY title ASC", (f"%{text}%", f"%{text}%"))
        self.current_results = cursor.fetchall()
        conn.close()
        self.results_listbox.delete(0, tk.END)
        for row in self.current_results: self.results_listbox.insert(tk.END, row[1])

    # ----------------- FULL SCREEN FEATURE -----------------
    def open_fullscreen(self):
        """Launches a dedicated distraction-free fullscreen viewport."""
        if not self.current_pil_image:
            messagebox.showwarning("Fullscreen Error", "Please select a hymn to view in fullscreen first.")
            return

        # Create fullscreen overlay window
        fs_win = tk.Toplevel(self.root)
        fs_win.title("Hymn Fullscreen Mode")
        fs_win.attributes("-fullscreen", True)
        fs_win.configure(bg="#000000") # Pure black for maximum screen contrast

        # Fullscreen Canvas (No border decorations)
        fs_canvas = tk.Canvas(fs_win, bg="#000000", highlightthickness=0)
        fs_canvas.pack(fill=tk.BOTH, expand=True)

        # Close bindings (Double click or press ESC)
        fs_win.bind("<Escape>", lambda e: fs_win.destroy())
        fs_win.bind("<Double-Button-1>", lambda e: fs_win.destroy())

        # Scrolling controls inside fullscreen window
        fs_win.bind("<MouseWheel>", lambda e: self.on_fs_mousewheel(e, fs_canvas))
        fs_win.bind("<Button-4>", lambda e: self.on_fs_mousewheel(e, fs_canvas))
        fs_win.bind("<Button-5>", lambda e: self.on_fs_mousewheel(e, fs_canvas))
        fs_win.bind("<Prior>", lambda e: fs_canvas.yview_scroll(-1, "pages"))
        fs_win.bind("<Next>", lambda e: fs_canvas.yview_scroll(1, "pages"))
        fs_win.bind("<Up>", lambda e: fs_canvas.yview_scroll(-1, "units"))
        fs_win.bind("<Down>", lambda e: fs_canvas.yview_scroll(1, "units"))

        # Render image inside the fullscreen viewport
        self.render_fullscreen_image(fs_canvas, fs_win)

    def render_fullscreen_image(self, canvas, window):
        """Scales the sheet music to fit the monitor screen width."""
        window.update()
        scr_width = window.winfo_width()
        img_w, img_h = self.current_pil_image.size

        # Scale based on screen width for clean vertical reading layout
        ratio = scr_width / img_w
        new_w = int(img_w * ratio)
        new_h = int(img_h * ratio)

        res_img = self.current_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.fs_tk_image = ImageTk.PhotoImage(res_img)  # Save active reference

        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=self.fs_tk_image)
        canvas.config(scrollregion=(0, 0, new_w, new_h))

    def on_fs_mousewheel(self, event, canvas):
        """Allows scrollbar operation inside the fullscreen canvas."""
        if event.num == 5 or event.delta < 0:
            canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            canvas.yview_scroll(-1, "units")

    # ----------------- DISPLAY & VIEW -----------------
    def on_listbox_select(self, event):
        sel = self.results_listbox.curselection()
        if sel: 
            h_title = self.current_results[sel[-1]][1]
            h_path = self.current_results[sel[-1]][2]
            
            # Update visual title label on toolbar
            self.hymn_title_label.config(text=h_title)
            self.display_image(h_path)

    def display_image(self, path):
        if not os.path.exists(path): return
        self.current_image_path = path
        self.current_pil_image = Image.open(path)
        self.render_image()

    def render_image(self):
        if not self.current_pil_image: return
        w = self.canvas.winfo_width()
        if w <= 1: w = 700
        img_w, img_h = self.current_pil_image.size
        ratio = w / img_w
        new_w, new_h = int(img_w * ratio), int(img_h * ratio)
        res = self.current_pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.current_tk_image = ImageTk.PhotoImage(res)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.current_tk_image)
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))

    def on_canvas_resize(self, event):
        if abs(event.width - self.last_canvas_width) > 10:
            self.last_canvas_width = event.width
            self.render_image()

    def on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0: self.canvas.yview_scroll(1, "units")
        else: self.canvas.yview_scroll(-1, "units")


if __name__ == "__main__":
    root = tk.Tk()
    app = HymnLibraryApp(root)
    root.mainloop()
