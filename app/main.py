import ctypes
import json
import logging
import os
import sys
import tempfile
import threading
from tkinter import Canvas, Listbox, Menu, filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk

from . import font_manager, logging_config, printer_utils
from .label_designer import LabelDesigner

# Setup logging immediately
logging_config.setup_logging()
logger = logging.getLogger(__name__)

# Windows 11 Fluent Design color tokens: (Light, Dark)
FLUENT = {
    "bg": ("#F3F3F3", "#202020"),
    "card": ("#FFFFFF", "#2B2B2B"),
    "card_alt": ("#F9F9F9", "#323232"),
    "stage": ("#E5E5E5", "#171717"),
    "border": ("#E0E0E0", "#3A3A3A"),
    "btn_border": ("#CCCCCC", "#474747"),
    "text": ("#1A1A1A", "#F3F3F3"),
    "text_muted": ("#5F5F5F", "#A6A6A6"),
    "accent": ("#0067C0", "#0078D4"),
    "accent_hover": ("#005A9E", "#106EBE"),
    "accent_soft": ("#EBF3FC", "#1D3650"),
    "danger_text": ("#C42B1C", "#FF99A4"),
    "danger_hover": ("#FDE7E9", "#442726"),
    "canvas_frame": ("#D4D4D4", "#0F0F0F"),
}

UI_FONT = "Segoe UI"


class LabelApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Label Printer Studio — 50.8 × 31 mm")
        self.geometry("1220x760")
        self.minsize(1020, 640)
        self.configure(fg_color=FLUENT["bg"])

        # Core State
        self.designer = LabelDesigner()
        self.selected_element_id = None
        self.current_project_path = None
        self.is_dirty = False
        self.autosave_var = ctk.BooleanVar(value=True)
        self._autosave_draft_path = self._default_autosave_draft_path()
        self._autosave_after_id = None
        self._autosaving = False
        self._recent_store_path = self._default_recent_store_path()
        self.recent_files = self._load_recent_files()
        self.zoom_mode = "Fit"
        self.display_scale = 1.5
        self._canvas_ox = 20
        self._canvas_oy = 20
        self._last_canvas_size = (0, 0)
        self._tk_preview_img = None
        self._drag_data = {"mode": None, "offset_x": 0, "offset_y": 0}
        self._active_snap_guides = {"x": [], "y": []}
        self._inline_editor = None
        self._inline_edit_meta = None
        self._syncing_controls = False

        # Undo / Redo history
        self._undo_stack = []
        self._redo_stack = []
        self._max_history = 50
        self._drag_start_snapshot = None
        self._last_snapshot = self._capture_history_state()

        self.font_catalog = font_manager.get_font_catalog() or [("Arial", "arial.ttf")]
        self.font_ref_to_name = {ref.lower(): name for name, ref in self.font_catalog}
        self.available_fonts = [ref for _, ref in self.font_catalog]
        self._filtered_fonts = list(self.font_catalog)
        self._font_picker_open = False
        self._current_font_ref = self.available_fonts[0]

        self._build_ui()
        self._bind_shortcuts()
        self._apply_win11_titlebar()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.update_preview()
        self.update_layer_list()
        self.update_control_state()
        self._update_history_buttons()
        self.set_status("Ready — Add text, image, or shape to begin")
        self.after(150, self._check_restore_autosave_draft)

    # ------------------------------------------------------------------
    # Windows 11 Native Window Styling
    # ------------------------------------------------------------------
    def _apply_win11_titlebar(self):
        """Syncs Windows 11 DWM dark titlebar & rounded corners when available."""
        if sys.platform != "win32":
            return
        try:
            self.update_idletasks()
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            mode = ctk.get_appearance_mode()
            is_dark = 1 if mode == "Dark" else 0
            # DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(ctypes.c_int(is_dark)), ctypes.sizeof(ctypes.c_int)
            )
            # DWMWA_WINDOW_CORNER_PREFERENCE = 33, DWMWCP_ROUND = 2
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int)
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Top Command Bar
        self.grid_rowconfigure(1, weight=1)  # 3-Pane Workspace
        self.grid_rowconfigure(2, weight=0)  # Bottom Status Bar

        self._build_command_bar()
        self._build_workspace()
        self._build_status_bar()

    def _make_secondary_btn(self, parent, text, command, width=80, danger=False):
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=30,
            corner_radius=6,
            font=(UI_FONT, 12),
            fg_color=FLUENT["card_alt"],
            hover_color=FLUENT["danger_hover"] if danger else FLUENT["border"],
            border_width=1,
            border_color=FLUENT["btn_border"],
            text_color=FLUENT["danger_text"] if danger else FLUENT["text"],
            command=command,
        )

    def _make_primary_btn(self, parent, text, command, width=96):
        return ctk.CTkButton(
            parent,
            text=text,
            width=width,
            height=30,
            corner_radius=6,
            font=(UI_FONT, 12, "bold"),
            fg_color=FLUENT["accent"],
            hover_color=FLUENT["accent_hover"],
            text_color="#FFFFFF",
            command=command,
        )

    def _build_command_bar(self):
        bar = ctk.CTkFrame(
            self,
            height=52,
            corner_radius=0,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(2, weight=1)

        # Left: File Menu & Quick Insert commands
        left_grp = ctk.CTkFrame(bar, fg_color="transparent")
        left_grp.grid(row=0, column=0, padx=12, pady=9, sticky="w")

        self.btn_file_menu = self._make_secondary_btn(left_grp, "File  ▾", self.show_file_menu, width=74)
        self.btn_file_menu.pack(side="left", padx=(0, 6))

        self._build_file_menu()

        self.btn_undo = self._make_secondary_btn(left_grp, "↶", self.undo_action, width=32)
        self.btn_undo.pack(side="left", padx=(0, 3))

        self.btn_redo = self._make_secondary_btn(left_grp, "↷", self.redo_action, width=32)
        self.btn_redo.pack(side="left", padx=(0, 10))

        ctk.CTkFrame(left_grp, width=1, height=22, fg_color=FLUENT["border"]).pack(side="left", padx=(0, 10))

        self.btn_quick_text = self._make_secondary_btn(left_grp, "+ Text", self._quick_add_or_focus_text, width=68)
        self.btn_quick_text.pack(side="left", padx=(0, 4))

        self.btn_upload_image = self._make_secondary_btn(left_grp, "+ Image", self.upload_image, width=74)
        self.btn_upload_image.pack(side="left", padx=(0, 4))

        self.btn_add_box = self._make_secondary_btn(left_grp, "+ Box", self.add_box_shape, width=60)
        self.btn_add_box.pack(side="left", padx=(0, 4))

        self.btn_add_line = self._make_secondary_btn(left_grp, "+ Line", self.add_line_shape, width=62)
        self.btn_add_line.pack(side="left")

        # Right: Theme, Printer, Copies Stepper, Print CTA
        right_grp = ctk.CTkFrame(bar, fg_color="transparent")
        right_grp.grid(row=0, column=3, padx=12, pady=9, sticky="e")

        self.theme_seg = ctk.CTkSegmentedButton(
            right_grp,
            values=["System", "Light", "Dark"],
            command=self.on_theme_change,
            height=28,
            font=(UI_FONT, 11),
            corner_radius=6,
        )
        self.theme_seg.set("System")
        self.theme_seg.pack(side="left", padx=(0, 12))

        ctk.CTkFrame(right_grp, width=1, height=22, fg_color=FLUENT["border"]).pack(side="left", padx=(0, 12))

        detected_printers = printer_utils.list_printers()
        self.printers = detected_printers if detected_printers else ["No Printers Found"]
        self.printer_var = ctk.StringVar(value=self.printers[0])

        self.printer_dropdown = ctk.CTkOptionMenu(
            right_grp,
            variable=self.printer_var,
            values=self.printers,
            width=190,
            height=30,
            corner_radius=6,
            font=(UI_FONT, 12),
            fg_color=FLUENT["card_alt"],
            button_color=FLUENT["border"],
            button_hover_color=FLUENT["btn_border"],
            text_color=FLUENT["text"],
        )
        self.printer_dropdown.pack(side="left", padx=(0, 4))

        self.btn_refresh_printers = self._make_secondary_btn(
            right_grp, "↻", self.refresh_printers, width=32
        )
        self.btn_refresh_printers.pack(side="left", padx=(0, 10))

        # Copies stepper
        copies_box = ctk.CTkFrame(
            right_grp,
            fg_color=FLUENT["card_alt"],
            border_width=1,
            border_color=FLUENT["btn_border"],
            corner_radius=6,
        )
        copies_box.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            copies_box, text="Copies", font=(UI_FONT, 11), text_color=FLUENT["text_muted"]
        ).pack(side="left", padx=(8, 4))

        ctk.CTkButton(
            copies_box,
            text="-",
            width=24,
            height=24,
            corner_radius=4,
            fg_color="transparent",
            hover_color=FLUENT["border"],
            text_color=FLUENT["text"],
            font=(UI_FONT, 13, "bold"),
            command=lambda: self._step_copies(-1),
        ).pack(side="left", pady=2)

        self.entry_copies = ctk.CTkEntry(
            copies_box,
            width=36,
            height=24,
            border_width=0,
            fg_color="transparent",
            justify="center",
            font=(UI_FONT, 12, "bold"),
        )
        self.entry_copies.insert(0, "1")
        self.entry_copies.pack(side="left")

        ctk.CTkButton(
            copies_box,
            text="+",
            width=24,
            height=24,
            corner_radius=4,
            fg_color="transparent",
            hover_color=FLUENT["border"],
            text_color=FLUENT["text"],
            font=(UI_FONT, 13, "bold"),
            command=lambda: self._step_copies(1),
        ).pack(side="left", padx=(0, 2), pady=2)

        self.btn_print = self._make_primary_btn(right_grp, "Print Label", self.print_label, width=104)
        self.btn_print.pack(side="left")

    def _build_workspace(self):
        workspace = ctk.CTkFrame(self, fg_color="transparent")
        workspace.grid(row=1, column=0, sticky="nsew", padx=12, pady=12)
        workspace.grid_columnconfigure(0, weight=0, minsize=265)  # Left: Add & Layers
        workspace.grid_columnconfigure(1, weight=1)               # Center: Interactive Canvas
        workspace.grid_columnconfigure(2, weight=0, minsize=290)  # Right: Inspector
        workspace.grid_rowconfigure(0, weight=1)

        self._build_left_panel(workspace)
        self._build_center_stage(workspace)
        self._build_inspector_panel(workspace)

    def _build_left_panel(self, parent):
        left_col = ctk.CTkFrame(parent, fg_color="transparent", width=265)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_col.grid_propagate(False)
        left_col.grid_rowconfigure(1, weight=1)
        left_col.grid_columnconfigure(0, weight=1)

        # Card 1: Quick Add Elements
        add_card = ctk.CTkFrame(
            left_col,
            corner_radius=8,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        add_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(
            add_card, text="Add Element", font=(UI_FONT, 13, "bold"), text_color=FLUENT["text"]
        ).pack(anchor="w", padx=12, pady=(10, 4))

        self.entry_text = ctk.CTkTextbox(
            add_card,
            height=54,
            corner_radius=6,
            border_width=1,
            border_color=FLUENT["btn_border"],
            font=(UI_FONT, 12),
        )
        self.entry_text.pack(fill="x", padx=12, pady=(0, 6))
        self.entry_text.bind("<Control-Return>", lambda _e: self.add_text_to_label())

        btn_row = ctk.CTkFrame(add_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 6))
        btn_row.grid_columnconfigure((0, 1), weight=1)

        self.btn_add_text = self._make_primary_btn(btn_row, "Add Text", self.add_text_to_label, width=100)
        self.btn_add_text.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._make_secondary_btn(btn_row, "Add Image", self.upload_image, width=100).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        shape_row = ctk.CTkFrame(add_card, fg_color="transparent")
        shape_row.pack(fill="x", padx=12, pady=(0, 10))
        shape_row.grid_columnconfigure((0, 1), weight=1)

        self._make_secondary_btn(shape_row, "+ Box", self.add_box_shape, width=100).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        self._make_secondary_btn(shape_row, "+ Line", self.add_line_shape, width=100).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        # Card 2: Layers
        layers_card = ctk.CTkFrame(
            left_col,
            corner_radius=8,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        layers_card.grid(row=1, column=0, sticky="nsew")
        layers_card.grid_rowconfigure(1, weight=1)
        layers_card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(layers_card, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))
        hdr.grid_columnconfigure(0, weight=1)

        self.lbl_layers_title = ctk.CTkLabel(
            hdr, text="Layers (0)", font=(UI_FONT, 13, "bold"), text_color=FLUENT["text"]
        )
        self.lbl_layers_title.grid(row=0, column=0, sticky="w")

        self.btn_layer_up = self._make_secondary_btn(hdr, "↑", lambda: self.move_selected_layer(1), width=28)
        self.btn_layer_up.grid(row=0, column=1, padx=(0, 4))

        self.btn_layer_down = self._make_secondary_btn(hdr, "↓", lambda: self.move_selected_layer(-1), width=28)
        self.btn_layer_down.grid(row=0, column=2)

        self.layer_frame = ctk.CTkScrollableFrame(layers_card, fg_color="transparent")
        self.layer_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 8))
        self.layer_buttons = {}

    def _build_center_stage(self, parent):
        stage = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=FLUENT["stage"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        stage.grid(row=0, column=1, sticky="nsew")
        stage.grid_rowconfigure(1, weight=1)
        stage.grid_columnconfigure(0, weight=1)

        # Stage header: dimensions & zoom
        top_bar = ctk.CTkFrame(stage, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        top_bar.grid_columnconfigure(0, weight=1)

        self.lbl_canvas_spec = ctk.CTkLabel(
            top_bar,
            text=f"Label Canvas  •  {self.designer.width_mm} × {self.designer.height_mm} mm ({self.designer.width_px}×{self.designer.height_px} px)",
            font=(UI_FONT, 12),
            text_color=FLUENT["text_muted"],
        )
        self.lbl_canvas_spec.grid(row=0, column=0, sticky="w")

        zoom_box = ctk.CTkFrame(top_bar, fg_color="transparent")
        zoom_box.grid(row=0, column=1, sticky="e")
        ctk.CTkLabel(zoom_box, text="Zoom", font=(UI_FONT, 11), text_color=FLUENT["text_muted"]).pack(
            side="left", padx=(0, 6)
        )
        self.zoom_seg = ctk.CTkSegmentedButton(
            zoom_box,
            values=["Fit", "1x", "1.5x", "2x"],
            command=self.on_zoom_change,
            height=26,
            font=(UI_FONT, 11),
            corner_radius=6,
        )
        self.zoom_seg.set("Fit")
        self.zoom_seg.pack(side="left")

        # Interactive Preview Surface (tkinter.Canvas for 1:1 coordinate & handle precision)
        canvas_wrap = ctk.CTkFrame(stage, fg_color="transparent")
        canvas_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        canvas_wrap.grid_rowconfigure(0, weight=1)
        canvas_wrap.grid_columnconfigure(0, weight=1)

        self.preview_canvas = Canvas(
            canvas_wrap,
            highlightthickness=0,
            borderwidth=0,
        )
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        self._h_scroll = ctk.CTkScrollbar(canvas_wrap, orientation="horizontal", command=self.preview_canvas.xview, height=12)
        self._v_scroll = ctk.CTkScrollbar(canvas_wrap, orientation="vertical", command=self.preview_canvas.yview, width=12)
        self.preview_canvas.configure(
            xscrollcommand=self._h_scroll.set,
            yscrollcommand=self._v_scroll.set,
        )

        self._sync_canvas_stage_color()

        self.preview_canvas.bind("<Configure>", self._on_canvas_configure)
        self.preview_canvas.bind("<Button-1>", self._on_canvas_press)
        self.preview_canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.preview_canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.preview_canvas.bind("<Motion>", self._on_canvas_hover)

        # Helpful keyboard/mouse hint
        ctk.CTkLabel(
            stage,
            text="Drag to move  •  Drag image corners to resize  •  Double-click text to edit inline  •  Arrows nudge",
            font=(UI_FONT, 11),
            text_color=FLUENT["text_muted"],
        ).grid(row=2, column=0, pady=(0, 10))

    def _build_inspector_panel(self, parent):
        inspector = ctk.CTkScrollableFrame(
            parent,
            width=290,
            corner_radius=8,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        self.inspector = inspector
        inspector.grid(row=0, column=2, sticky="nsew", padx=(10, 0))

        ctk.CTkLabel(
            inspector, text="Properties", font=(UI_FONT, 14, "bold"), text_color=FLUENT["text"]
        ).pack(anchor="w", padx=12, pady=(10, 2))

        self.lbl_selection_hint = ctk.CTkLabel(
            inspector,
            text="Select an element on the canvas or in Layers",
            font=(UI_FONT, 11),
            text_color=FLUENT["text_muted"],
            wraplength=250,
            justify="left",
        )
        self.lbl_selection_hint.pack(anchor="w", padx=12, pady=(0, 10))

        # --- Position & Alignment ---
        pos_card = ctk.CTkFrame(inspector, corner_radius=6, fg_color=FLUENT["card_alt"], border_width=1, border_color=FLUENT["border"])
        pos_card.pack(fill="x", padx=10, pady=(0, 10))
        pos_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(pos_card, text="Position & Align", font=(UI_FONT, 12, "bold"), text_color=FLUENT["text"]).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 4)
        )

        self.label_val_x = ctk.CTkLabel(pos_card, text="X: 0 px", font=(UI_FONT, 11), width=62, anchor="e")
        self.label_val_x.grid(row=1, column=1, padx=(0, 10), sticky="e")
        self.slider_x = ctk.CTkSlider(pos_card, from_=0, to=self.designer.width_px, command=self.on_pos_change)
        self.slider_x.grid(row=1, column=0, padx=(10, 6), pady=4, sticky="ew")
        self.slider_x.bind("<ButtonRelease-1>", lambda _e: self._flush_pending_history())

        self.label_val_y = ctk.CTkLabel(pos_card, text="Y: 0 px", font=(UI_FONT, 11), width=62, anchor="e")
        self.label_val_y.grid(row=2, column=1, padx=(0, 10), sticky="e")
        self.slider_y = ctk.CTkSlider(pos_card, from_=0, to=self.designer.height_px, command=self.on_pos_change)
        self.slider_y.grid(row=2, column=0, padx=(10, 6), pady=4, sticky="ew")
        self.slider_y.bind("<ButtonRelease-1>", lambda _e: self._flush_pending_history())

        align_row = ctk.CTkFrame(pos_card, fg_color="transparent")
        align_row.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(4, 10))
        align_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_center_h = self._make_secondary_btn(align_row, "Center H", lambda: self.center_selected(True, False), width=70)
        self.btn_center_h.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.btn_center_v = self._make_secondary_btn(align_row, "Center V", lambda: self.center_selected(False, True), width=70)
        self.btn_center_v.grid(row=0, column=1, sticky="ew", padx=3)
        self.btn_center_both = self._make_secondary_btn(align_row, "Center", lambda: self.center_selected(True, True), width=70)
        self.btn_center_both.grid(row=0, column=2, sticky="ew", padx=(3, 0))

        # --- Rotation ---
        rot_card = ctk.CTkFrame(inspector, corner_radius=6, fg_color=FLUENT["card_alt"], border_width=1, border_color=FLUENT["border"])
        rot_card.pack(fill="x", padx=10, pady=(0, 10))

        self.lbl_rotation = ctk.CTkLabel(rot_card, text="Rotation", font=(UI_FONT, 12, "bold"), text_color=FLUENT["text"])
        self.lbl_rotation.pack(anchor="w", padx=10, pady=(8, 6))

        self.rotation_values = ["0°", "90°", "180°", "270°"]
        self.rotation_seg = ctk.CTkSegmentedButton(
            rot_card,
            values=self.rotation_values,
            command=self.on_rotation_change,
            height=28,
            font=(UI_FONT, 12),
            corner_radius=6,
        )
        self.rotation_seg.set("0°")
        self.rotation_seg.pack(fill="x", padx=10, pady=(0, 10))

        # --- Text Properties ---
        self.text_card = ctk.CTkFrame(inspector, corner_radius=6, fg_color=FLUENT["card_alt"], border_width=1, border_color=FLUENT["border"])
        self.text_card.pack(fill="x", padx=10, pady=(0, 10))
        self.text_card.grid_columnconfigure(0, weight=1)

        self.lbl_edit_text = ctk.CTkLabel(self.text_card, text="Text Properties", font=(UI_FONT, 12, "bold"), text_color=FLUENT["text"])
        self.lbl_edit_text.grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(8, 6))

        edit_row = ctk.CTkFrame(self.text_card, fg_color="transparent")
        edit_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        edit_row.grid_columnconfigure(0, weight=1)

        self.entry_edit_text = ctk.CTkTextbox(
            edit_row,
            height=54,
            corner_radius=6,
            border_width=1,
            border_color=FLUENT["btn_border"],
            font=(UI_FONT, 12),
        )
        self.entry_edit_text.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.entry_edit_text.bind("<KeyRelease>", self.on_text_content_change)
        self.entry_edit_text.bind("<FocusOut>", lambda _e: self._flush_pending_history())

        self.btn_update_text = self._make_secondary_btn(edit_row, "Apply", self.on_text_content_change, width=54)
        self.btn_update_text.grid(row=0, column=1, sticky="n")

        self.lbl_font = ctk.CTkLabel(self.text_card, text="Font", font=(UI_FONT, 11), text_color=FLUENT["text_muted"])
        self.lbl_font.grid(row=2, column=0, columnspan=2, sticky="w", padx=10)

        self.btn_font_picker = ctk.CTkButton(
            self.text_card,
            text=f"{self._get_font_display_name(self._current_font_ref)}  ▾",
            height=30,
            corner_radius=6,
            anchor="w",
            font=(UI_FONT, 12),
            fg_color=FLUENT["card"],
            hover_color=FLUENT["border"],
            border_width=1,
            border_color=FLUENT["btn_border"],
            text_color=FLUENT["text"],
            command=self.toggle_font_picker,
        )
        self.btn_font_picker.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8))

        size_hdr = ctk.CTkFrame(self.text_card, fg_color="transparent")
        size_hdr.grid(row=4, column=0, columnspan=2, sticky="ew", padx=10)
        size_hdr.grid_columnconfigure(0, weight=1)
        self.lbl_fontsize = ctk.CTkLabel(size_hdr, text="Font Size", font=(UI_FONT, 11), text_color=FLUENT["text_muted"])
        self.lbl_fontsize.grid(row=0, column=0, sticky="w")
        self.lbl_fontsize_val = ctk.CTkLabel(size_hdr, text="30 pt", font=(UI_FONT, 11, "bold"), text_color=FLUENT["text"])
        self.lbl_fontsize_val.grid(row=0, column=1, sticky="e")

        self.slider_fontsize = ctk.CTkSlider(self.text_card, from_=10, to=120, command=self.on_fontsize_change)
        self.slider_fontsize.set(30)
        self.slider_fontsize.grid(row=5, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 8))
        self.slider_fontsize.bind("<ButtonRelease-1>", lambda _e: self._flush_pending_history())

        self.lbl_align = ctk.CTkLabel(self.text_card, text="Alignment", font=(UI_FONT, 11), text_color=FLUENT["text_muted"])
        self.lbl_align.grid(row=6, column=0, columnspan=2, sticky="w", padx=10)

        self.align_seg = ctk.CTkSegmentedButton(
            self.text_card,
            values=["Left", "Center", "Right"],
            command=self.on_align_change,
            height=26,
            font=(UI_FONT, 11),
            corner_radius=6,
        )
        self.align_seg.set("Left")
        self.align_seg.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 10))

        # Floating ComboBox Popup (placed on root window so scrolling never triggers inspector scroll)
        self._font_popup_width = 250
        self._font_popup_height = 232
        self.font_picker_drawer = ctk.CTkFrame(
            self,
            width=self._font_popup_width,
            height=self._font_popup_height,
            corner_radius=8,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["btn_border"],
        )
        self.font_picker_drawer.grid_propagate(False)
        self.font_picker_drawer.grid_columnconfigure(0, weight=1)
        self.font_picker_drawer.grid_rowconfigure(1, weight=1)

        filter_row = ctk.CTkFrame(self.font_picker_drawer, fg_color="transparent")
        filter_row.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        filter_row.grid_columnconfigure(0, weight=1)

        self.entry_font_filter = ctk.CTkEntry(
            filter_row,
            placeholder_text="Filter font...",
            height=28,
            corner_radius=5,
            font=(UI_FONT, 11),
        )
        self.entry_font_filter.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.entry_font_filter.bind("<KeyRelease>", lambda _e: self._filter_font_list())
        self.entry_font_filter.bind("<Return>", lambda _e: self._apply_highlighted_or_first_font())
        self.entry_font_filter.bind("<Escape>", lambda _e: self._close_font_picker())
        self.entry_font_filter.bind("<Down>", self._focus_font_listbox)
        self.entry_font_filter.bind("<MouseWheel>", self._on_font_list_mousewheel)

        self.btn_clear_font_filter = self._make_secondary_btn(
            filter_row, "×", self._clear_font_filter, width=28
        )
        self.btn_clear_font_filter.grid(row=0, column=1)

        list_wrap = ctk.CTkFrame(self.font_picker_drawer, fg_color="transparent")
        list_wrap.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        list_wrap.grid_columnconfigure(0, weight=1)
        list_wrap.grid_rowconfigure(0, weight=1)

        self.font_listbox = Listbox(
            list_wrap,
            exportselection=False,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            font=(UI_FONT, 10),
        )
        self.font_listbox.grid(row=0, column=0, sticky="nsew")

        font_scroll = ctk.CTkScrollbar(list_wrap, command=self.font_listbox.yview, width=12, height=160)
        font_scroll.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.font_listbox.configure(yscrollcommand=font_scroll.set)

        self.font_listbox.bind("<ButtonRelease-1>", lambda _e: self._select_font_from_listbox())
        self.font_listbox.bind("<Return>", lambda _e: self._select_font_from_listbox())
        self.font_listbox.bind("<Escape>", lambda _e: self._close_font_picker())
        self.font_listbox.bind("<MouseWheel>", self._on_font_list_mousewheel)
        self.font_picker_drawer.bind("<MouseWheel>", self._on_font_list_mousewheel)

        self._sync_font_listbox_colors()
        self._populate_font_listbox(self.font_catalog)
        self.font_picker_drawer.place_forget()

        # --- Image Properties ---
        self.image_card = ctk.CTkFrame(inspector, corner_radius=6, fg_color=FLUENT["card_alt"], border_width=1, border_color=FLUENT["border"])
        self.image_card.pack(fill="x", padx=10, pady=(0, 10))
        self.image_card.grid_columnconfigure(0, weight=1)

        scale_hdr = ctk.CTkFrame(self.image_card, fg_color="transparent")
        scale_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        scale_hdr.grid_columnconfigure(0, weight=1)
        self.lbl_scale = ctk.CTkLabel(scale_hdr, text="Image Scale", font=(UI_FONT, 12, "bold"), text_color=FLUENT["text"])
        self.lbl_scale.grid(row=0, column=0, sticky="w")
        self.lbl_scale_val = ctk.CTkLabel(scale_hdr, text="100%", font=(UI_FONT, 11, "bold"), text_color=FLUENT["text"])
        self.lbl_scale_val.grid(row=0, column=1, sticky="e")

        self.slider_scale = ctk.CTkSlider(self.image_card, from_=0.1, to=3.0, command=self.on_scale_change)
        self.slider_scale.set(1.0)
        self.slider_scale.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))
        self.slider_scale.bind("<ButtonRelease-1>", lambda _e: self._flush_pending_history())

        self.btn_reset_scale = self._make_secondary_btn(
            self.image_card, "Reset Scale (100%)", lambda: self.on_scale_change(1.0, sync_slider=True), width=120
        )
        self.btn_reset_scale.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        # --- Shape Properties ---
        self.shape_card = ctk.CTkFrame(inspector, corner_radius=6, fg_color=FLUENT["card_alt"], border_width=1, border_color=FLUENT["border"])
        self.shape_card.pack(fill="x", padx=10, pady=(0, 10))
        self.shape_card.grid_columnconfigure(0, weight=1)

        stroke_hdr = ctk.CTkFrame(self.shape_card, fg_color="transparent")
        stroke_hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        stroke_hdr.grid_columnconfigure(0, weight=1)
        self.lbl_stroke = ctk.CTkLabel(stroke_hdr, text="Shape Thickness", font=(UI_FONT, 12, "bold"), text_color=FLUENT["text"])
        self.lbl_stroke.grid(row=0, column=0, sticky="w")
        self.lbl_stroke_val = ctk.CTkLabel(stroke_hdr, text="3 px", font=(UI_FONT, 11, "bold"), text_color=FLUENT["text"])
        self.lbl_stroke_val.grid(row=0, column=1, sticky="e")

        self.slider_stroke = ctk.CTkSlider(self.shape_card, from_=1, to=20, number_of_steps=19, command=self.on_shape_stroke_change)
        self.slider_stroke.set(3)
        self.slider_stroke.grid(row=1, column=0, sticky="ew", padx=10, pady=(2, 6))
        self.slider_stroke.bind("<ButtonRelease-1>", lambda _e: self._flush_pending_history())

        self.chk_shape_fill = ctk.CTkCheckBox(
            self.shape_card,
            text="Fill Box",
            font=(UI_FONT, 12),
            command=self.on_shape_fill_change,
        )
        self.chk_shape_fill.grid(row=2, column=0, sticky="w", padx=10, pady=(0, 10))

        # --- Actions ---
        act_row = ctk.CTkFrame(inspector, fg_color="transparent")
        act_row.pack(fill="x", padx=10, pady=(0, 12))
        act_row.grid_columnconfigure((0, 1), weight=1)

        self.btn_duplicate_el = self._make_secondary_btn(act_row, "Duplicate", self.duplicate_element_action, width=100)
        self.btn_duplicate_el.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self.btn_delete_el = self._make_secondary_btn(act_row, "Delete", self.delete_element, width=100, danger=True)
        self.btn_delete_el.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    def _build_status_bar(self):
        status_bar = ctk.CTkFrame(
            self,
            height=28,
            corner_radius=0,
            fg_color=FLUENT["card"],
            border_width=1,
            border_color=FLUENT["border"],
        )
        status_bar.grid(row=2, column=0, sticky="ew")
        status_bar.grid_columnconfigure(2, weight=1)

        self.lbl_status = ctk.CTkLabel(
            status_bar, text="Ready", font=(UI_FONT, 11), text_color=FLUENT["text_muted"], anchor="w"
        )
        self.lbl_status.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=3)

        ctk.CTkFrame(status_bar, width=1, height=14, fg_color=FLUENT["border"]).grid(row=0, column=1, padx=2, pady=4)

        self.lbl_project_path = ctk.CTkLabel(
            status_bar, text="Location: Not saved yet", font=(UI_FONT, 11), text_color=FLUENT["text_muted"], anchor="w"
        )
        self.lbl_project_path.grid(row=0, column=2, sticky="ew", padx=8, pady=3)

        self.lbl_coords_status = ctk.CTkLabel(
            status_bar, text="No selection", font=(UI_FONT, 11), text_color=FLUENT["text_muted"], anchor="e"
        )
        self.lbl_coords_status.grid(row=0, column=3, sticky="e", padx=12, pady=3)

    # ------------------------------------------------------------------
    # Shortcuts & Helpers
    # ------------------------------------------------------------------
    def _bind_shortcuts(self):
        self.bind("<Control-s>", lambda _e: self.save_project_action())
        self.bind("<Control-S>", lambda _e: self.save_project_as_action())
        self.bind("<Control-Shift-S>", lambda _e: self.save_project_as_action())
        self.bind("<Control-o>", lambda _e: self.load_project_action())
        self.bind("<Control-n>", lambda _e: self.clear_label())
        self.bind("<Control-p>", lambda _e: self.print_label())
        self.bind("<Control-z>", lambda _e: self._shortcut_undo())
        self.bind("<Control-y>", lambda _e: self._shortcut_redo())
        self.bind("<Control-Shift-Z>", lambda _e: self._shortcut_redo())
        self.bind("<Control-d>", lambda _e: self._shortcut_duplicate())
        self.bind("<Delete>", lambda _e: self._shortcut_delete())
        self.bind("<Left>", lambda _e: self._nudge_selected(-1, 0))
        self.bind("<Right>", lambda _e: self._nudge_selected(1, 0))
        self.bind("<Up>", lambda _e: self._nudge_selected(0, -1))
        self.bind("<Down>", lambda _e: self._nudge_selected(0, 1))
        self.bind("<Shift-Left>", lambda _e: self._nudge_selected(-10, 0))
        self.bind("<Shift-Right>", lambda _e: self._nudge_selected(10, 0))
        self.bind("<Shift-Up>", lambda _e: self._nudge_selected(0, -10))
        self.bind("<Shift-Down>", lambda _e: self._nudge_selected(0, 10))
        self.bind("<Button-1>", self._on_global_click, add="+")
        self.bind("<MouseWheel>", self._on_global_mousewheel, add="+")

    def _is_typing_in_input(self):
        focus = self.focus_get()
        if focus is None:
            return False
        return focus.winfo_class() in ("Entry", "Text", "TEntry", "Listbox")

    def _shortcut_undo(self):
        if not self._is_typing_in_input():
            self.undo_action()

    def _shortcut_redo(self):
        if not self._is_typing_in_input():
            self.redo_action()

    def _shortcut_duplicate(self):
        if not self._is_typing_in_input():
            self.duplicate_element_action()

    def _shortcut_delete(self):
        if not self._is_typing_in_input():
            self.delete_element()

    def _nudge_selected(self, dx, dy):
        if self._is_typing_in_input() or not self.selected_element_id:
            return
        el = self.designer.get_element(self.selected_element_id)
        if not el:
            return
        new_x = el["x"] + dx
        new_y = el["y"] + dy
        self.designer.update_element_position(self.selected_element_id, new_x, new_y)
        self._sync_position_widgets(new_x, new_y)
        self.update_preview()
        self._commit_history_step()

    # ------------------------------------------------------------------
    # Undo / Redo & Dirty State Tracking
    # ------------------------------------------------------------------
    def _capture_history_state(self):
        return {
            "designer": self.designer.snapshot_state(),
            "selected_id": self.selected_element_id,
        }

    def _update_history_buttons(self):
        if hasattr(self, "btn_undo"):
            self.btn_undo.configure(state="normal" if self._undo_stack else "disabled")
        if hasattr(self, "btn_redo"):
            self.btn_redo.configure(state="normal" if self._redo_stack else "disabled")

    def _refresh_window_title(self):
        star = "*" if self.is_dirty else ""
        if self.current_project_path:
            filename = os.path.basename(self.current_project_path)
            self.title(f"Label Printer Studio — {star}{filename}")
        else:
            self.title(f"Label Printer Studio — {star}{self.designer.width_mm} × {self.designer.height_mm} mm")

    def _set_dirty(self, dirty=True, immediate_autosave=False):
        self.is_dirty = bool(dirty)
        self._refresh_window_title()
        if self.is_dirty and self.autosave_var.get() and not self._autosaving:
            if immediate_autosave:
                self._perform_autosave()
            else:
                self._schedule_autosave()

    def _cancel_scheduled_autosave(self):
        if self._autosave_after_id is not None:
            try:
                self.after_cancel(self._autosave_after_id)
            except Exception:
                pass
            self._autosave_after_id = None

    def _schedule_autosave(self, delay_ms=250):
        self._cancel_scheduled_autosave()
        self._autosave_after_id = self.after(delay_ms, self._perform_autosave)

    def _clear_autosave_draft(self):
        try:
            if os.path.exists(self._autosave_draft_path):
                os.remove(self._autosave_draft_path)
        except OSError:
            pass

    def _perform_autosave(self):
        self._cancel_scheduled_autosave()
        if not self.autosave_var.get() or not self.is_dirty or self._autosaving:
            return False
        self._autosaving = True
        try:
            if self.current_project_path:
                if self.designer.save_project(self.current_project_path):
                    self.is_dirty = False
                    self._refresh_window_title()
                    folder = os.path.dirname(self.current_project_path)
                    filename = os.path.basename(self.current_project_path)
                    self.lbl_project_path.configure(text=f"Saved in: {folder}  ({filename})  •  Autosaved")
                    self.set_status(f"Auto-saved: {self.current_project_path}")
                    self._clear_autosave_draft()
                    return True
            else:
                os.makedirs(os.path.dirname(self._autosave_draft_path), exist_ok=True)
                if self.designer.save_project(self._autosave_draft_path):
                    self.lbl_project_path.configure(text=f"Draft auto-saved: {self._autosave_draft_path}")
                    return True
        except Exception as e:
            logger.warning(f"Autosave failed: {e}")
        finally:
            self._autosaving = False
        return False

    def on_autosave_toggle(self):
        enabled = self.autosave_var.get()
        if enabled:
            self.set_status("Autosave enabled")
            if self.is_dirty:
                self._perform_autosave()
        else:
            self._cancel_scheduled_autosave()
            self.set_status("Autosave disabled")

    def _check_restore_autosave_draft(self):
        if not os.path.exists(self._autosave_draft_path) or self.current_project_path or self.designer.elements:
            return
        try:
            with open(self._autosave_draft_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("elements"):
                self._clear_autosave_draft()
                return
        except Exception:
            return

        if messagebox.askyesno(
            "Recover Unsaved Draft",
            "An auto-saved draft from a previous session was found.\nDo you want to restore it?",
        ):
            if self.designer.load_project(self._autosave_draft_path):
                self.selected_element_id = None
                self.update_layer_list()
                self.update_preview()
                self.update_control_state()
                self._reset_history()
                self._set_dirty(True)
                self.set_status("Recovered auto-saved draft")
        else:
            self._clear_autosave_draft()

    def _commit_history_step(self, prev_snapshot=None, mark_dirty=True):
        snap = prev_snapshot if prev_snapshot is not None else self._last_snapshot
        if snap is not None:
            self._undo_stack.append(snap)
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
        self._last_snapshot = self._capture_history_state()
        self._update_history_buttons()
        if mark_dirty:
            self._set_dirty(True, immediate_autosave=True)

    def _flush_pending_history(self):
        current = self._capture_history_state()
        if current["designer"] != self._last_snapshot["designer"]:
            self._commit_history_step(self._last_snapshot, mark_dirty=True)

    def _reset_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._last_snapshot = self._capture_history_state()
        self._update_history_buttons()
        self._set_dirty(False)

    def _apply_history_snapshot(self, snapshot):
        self._close_font_picker()
        self._close_inline_text_editor(commit=False)
        self.designer.restore_state(snapshot["designer"])
        restored_sel = snapshot.get("selected_id")
        if restored_sel is not None and self.designer.get_element(restored_sel) is None:
            restored_sel = None
        self.selected_element_id = restored_sel
        self._last_snapshot = self._capture_history_state()
        if restored_sel is not None:
            self.select_element(restored_sel)
        else:
            self.update_layer_list()
            self.update_control_state()
            self.update_preview()
        self._set_dirty(True, immediate_autosave=True)
        self._update_history_buttons()

    def undo_action(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(self._capture_history_state())
        snapshot = self._undo_stack.pop()
        self._apply_history_snapshot(snapshot)
        self.set_status("Undo")

    def redo_action(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._capture_history_state())
        snapshot = self._redo_stack.pop()
        self._apply_history_snapshot(snapshot)
        self.set_status("Redo")

    def _confirm_discard_changes(self):
        self._cancel_scheduled_autosave()
        if self.autosave_var.get() and self.is_dirty and self.current_project_path:
            self._perform_autosave()
        if not self.is_dirty:
            return True
        choice = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save before continuing?",
        )
        if choice is None:
            return False
        if choice is True:
            self.save_project_action()
            return not self.is_dirty
        self._clear_autosave_draft()
        return True

    def on_closing(self):
        self._close_inline_text_editor(commit=True)
        if self._confirm_discard_changes():
            self._cancel_scheduled_autosave()
            self.destroy()

    def set_status(self, message):
        self.lbl_status.configure(text=message)

    def _sync_position_widgets(self, x, y):
        self._syncing_controls = True
        try:
            clamped_x = max(0, min(self.designer.width_px, int(x)))
            clamped_y = max(0, min(self.designer.height_px, int(y)))
            self.slider_x.set(clamped_x)
            self.slider_y.set(clamped_y)
            self.label_val_x.configure(text=f"X: {int(x)} px")
            self.label_val_y.configure(text=f"Y: {int(y)} px")
            self.lbl_coords_status.configure(text=f"X: {int(x)} px, Y: {int(y)} px")
        finally:
            self._syncing_controls = False

    # ------------------------------------------------------------------
    # Canvas Direct Manipulation (Move, Image Resize, Inline Text Edit)
    # ------------------------------------------------------------------
    def _sync_canvas_stage_color(self):
        idx = 1 if ctk.get_appearance_mode() == "Dark" else 0
        self.preview_canvas.configure(bg=FLUENT["stage"][idx])

    def _on_canvas_configure(self, event):
        size = (event.width, event.height)
        if size != self._last_canvas_size and event.width > 10 and event.height > 10:
            self._last_canvas_size = size
            self.update_preview()

    def _event_to_canvas_coords(self, event):
        vx = self.preview_canvas.canvasx(event.x)
        vy = self.preview_canvas.canvasy(event.y)
        scale = max(0.1, self.display_scale)
        cx = int(round((vx - self._canvas_ox) / scale))
        cy = int(round((vy - self._canvas_oy) / scale))
        return cx, cy

    def _get_resize_handle_screen(self, event, tolerance=10):
        """Checks if mouse event hits any of the 4 screen-space corner handles of the selected image or shape."""
        if not self.selected_element_id:
            return None
        el = self.designer.get_element(self.selected_element_id)
        if not el or el["type"] not in ("image", "shape"):
            return None
        bounds = self.designer.get_element_bounds(self.selected_element_id)
        if not bounds:
            return None
        bx, by, bw, bh = bounds
        if bw <= 0 or bh <= 0:
            return None

        vx = self.preview_canvas.canvasx(event.x)
        vy = self.preview_canvas.canvasy(event.y)
        s = self.display_scale
        corners = {
            "nw": (self._canvas_ox + bx * s, self._canvas_oy + by * s),
            "ne": (self._canvas_ox + (bx + bw) * s, self._canvas_oy + by * s),
            "sw": (self._canvas_ox + bx * s, self._canvas_oy + (by + bh) * s),
            "se": (self._canvas_ox + (bx + bw) * s, self._canvas_oy + (by + bh) * s),
        }
        best_handle = None
        best_dist = tolerance + 1
        for name, (hx, hy) in corners.items():
            dist = max(abs(vx - hx), abs(vy - hy))
            if dist <= tolerance and dist < best_dist:
                best_dist = dist
                best_handle = name
        return best_handle

    def _on_canvas_hover(self, event):
        if self._drag_data.get("mode"):
            return
        handle = self._get_resize_handle_screen(event)
        if handle in ("nw", "se"):
            self.preview_canvas.configure(cursor="size_nw_se")
            return
        if handle in ("ne", "sw"):
            self.preview_canvas.configure(cursor="size_ne_sw")
            return
        cx, cy = self._event_to_canvas_coords(event)
        if self.designer.hit_test(cx, cy) is not None:
            self.preview_canvas.configure(cursor="fleur")
        else:
            self.preview_canvas.configure(cursor="arrow")

    def _on_canvas_press(self, event):
        self._close_inline_text_editor(commit=True)
        # Move focus off text entry so arrow keys/Del work on canvas
        self.focus_set()

        # Check screen-space resize corner handles on currently selected image/shape first
        handle = self._get_resize_handle_screen(event)
        if handle:
            bounds = self.designer.get_element_bounds(self.selected_element_id)
            el = self.designer.get_element(self.selected_element_id)
            if bounds and el and el["type"] in ("image", "shape"):
                bx, by, bw, bh = bounds
                anchors = {
                    "se": (bx, by),
                    "ne": (bx, by + bh),
                    "sw": (bx + bw, by),
                    "nw": (bx + bw, by + bh),
                }
                ax, ay = anchors[handle]
                self._drag_start_snapshot = self._capture_history_state()
                self._drag_data = {
                    "mode": "resize",
                    "handle": handle,
                    "anchor_x": ax,
                    "anchor_y": ay,
                }
                return

        cx, cy = self._event_to_canvas_coords(event)
        hit_id = self.designer.hit_test(cx, cy)
        if hit_id is not None:
            self.select_element(hit_id)
            el = self.designer.get_element(hit_id)
            if el:
                self._drag_start_snapshot = self._capture_history_state()
                self._drag_data = {
                    "mode": "move",
                    "offset_x": cx - el["x"],
                    "offset_y": cy - el["y"],
                }
        else:
            self.selected_element_id = None
            self.update_layer_list()
            self.update_control_state()
            self.update_preview()

    def _compute_snap(self, element_id, raw_x, raw_y, threshold=5):
        """Snaps element position to canvas center and other elements' edges/centers."""
        bounds = self.designer.get_element_bounds(element_id)
        if not bounds:
            return raw_x, raw_y, [], []
        _, _, bw, bh = bounds
        if bw <= 0 or bh <= 0:
            return raw_x, raw_y, [], []

        x_targets = [self.designer.width_px / 2.0]
        y_targets = [self.designer.height_px / 2.0]

        for other in self.designer.elements:
            if other["id"] == element_id:
                continue
            ob = self.designer.get_element_bounds(other["id"])
            if not ob:
                continue
            ox, oy, ow, oh = ob
            if ow > 0 and oh > 0:
                x_targets.extend([ox, ox + ow / 2.0, ox + ow])
                y_targets.extend([oy, oy + oh / 2.0, oy + oh])

        snapped_x = raw_x
        guides_x = []
        best_dx = threshold + 1
        for edge_offset in (0.0, bw / 2.0, float(bw)):
            pos = raw_x + edge_offset
            for target in x_targets:
                diff = abs(pos - target)
                if diff <= threshold and diff < best_dx:
                    best_dx = diff
                    snapped_x = int(round(target - edge_offset))
                    guides_x = [target]

        snapped_y = raw_y
        guides_y = []
        best_dy = threshold + 1
        for edge_offset in (0.0, bh / 2.0, float(bh)):
            pos = raw_y + edge_offset
            for target in y_targets:
                diff = abs(pos - target)
                if diff <= threshold and diff < best_dy:
                    best_dy = diff
                    snapped_y = int(round(target - edge_offset))
                    guides_y = [target]

        return snapped_x, snapped_y, guides_x, guides_y

    def _on_canvas_drag(self, event):
        mode = self._drag_data.get("mode")
        if not mode or not self.selected_element_id:
            return
        cx, cy = self._event_to_canvas_coords(event)

        if mode == "move":
            raw_x = cx - self._drag_data["offset_x"]
            raw_y = cy - self._drag_data["offset_y"]
            new_x, new_y, gx, gy = self._compute_snap(self.selected_element_id, raw_x, raw_y)
            self._active_snap_guides = {"x": gx, "y": gy}
            self.designer.update_element_position(self.selected_element_id, new_x, new_y)
            self._sync_position_widgets(new_x, new_y)
            self.update_preview()
        elif mode == "resize":
            el = self.designer.get_element(self.selected_element_id)
            if not el or el["type"] not in ("image", "shape"):
                return
            handle = self._drag_data["handle"]
            ax = self._drag_data["anchor_x"]
            ay = self._drag_data["anchor_y"]

            dx = (cx - ax) if "e" in handle else (ax - cx)
            dy = (cy - ay) if "s" in handle else (ay - cy)
            dx = max(8, dx)
            dy = max(8, dy)

            if el["type"] == "image":
                rot = el.get("rotation", 0)
                if rot in (90, 270):
                    unit_w = max(1, el.get("base_height", 1))
                    unit_h = max(1, el.get("base_width", 1))
                else:
                    unit_w = max(1, el.get("base_width", 1))
                    unit_h = max(1, el.get("base_height", 1))

                new_scale = max(0.1, min(3.0, max(dx / unit_w, dy / unit_h)))
                new_w = int(unit_w * new_scale)
                new_h = int(unit_h * new_scale)

                new_x = ax if "e" in handle else ax - new_w
                new_y = ay if "s" in handle else ay - new_h

                self.designer.update_image_transform(self.selected_element_id, new_scale, new_x, new_y)
                self._syncing_controls = True
                try:
                    self.slider_scale.set(new_scale)
                    self.lbl_scale_val.configure(text=f"{int(new_scale * 100)}%")
                finally:
                    self._syncing_controls = False
            else:
                # Shape resize: free width/height for box, length for line
                rot = el.get("rotation", 0)
                if el.get("shape") == "line":
                    stroke = max(1, int(el.get("stroke_width", 4)))
                    if rot in (90, 270):
                        new_w = max(12, dy)
                        new_h = stroke
                        vis_w, vis_h = new_h, new_w
                    else:
                        new_w = max(12, dx)
                        new_h = stroke
                        vis_w, vis_h = new_w, new_h
                else:
                    if rot in (90, 270):
                        new_w = max(10, dy)
                        new_h = max(10, dx)
                        vis_w, vis_h = new_h, new_w
                    else:
                        new_w = max(10, dx)
                        new_h = max(10, dy)
                        vis_w, vis_h = new_w, new_h

                new_x = ax if "e" in handle else ax - vis_w
                new_y = ay if "s" in handle else ay - vis_h
                self.designer.update_shape_properties(
                    self.selected_element_id, width=new_w, height=new_h, x=new_x, y=new_y
                )

            self._sync_position_widgets(new_x, new_y)
            self.update_preview()

    def _on_canvas_release(self, _event):
        mode = self._drag_data.get("mode")
        self._active_snap_guides = {"x": [], "y": []}
        if mode:
            self._drag_data["mode"] = None
            if self._drag_start_snapshot is not None:
                if self._capture_history_state()["designer"] != self._drag_start_snapshot["designer"]:
                    self._commit_history_step(self._drag_start_snapshot, mark_dirty=True)
                self._drag_start_snapshot = None
            self.update_preview()
            el = self.designer.get_element(self.selected_element_id) if self.selected_element_id else None
            if el:
                if mode == "resize":
                    if el["type"] == "image":
                        self.set_status(f"Resized {el['name']} to {int(el.get('scale', 1.0) * 100)}%")
                    else:
                        self.set_status(f"Resized {el['name']} to {el['width']}×{el['height']} px")
                else:
                    self.set_status(f"Moved {el['name']} to ({el['x']}, {el['y']})")

    def _on_canvas_double_click(self, event):
        cx, cy = self._event_to_canvas_coords(event)
        hit_id = self.designer.hit_test(cx, cy)
        if hit_id is None:
            return
        el = self.designer.get_element(hit_id)
        if el and el["type"] == "text":
            self.select_element(hit_id)
            self._open_inline_text_editor(hit_id)

    def _open_inline_text_editor(self, element_id):
        self._close_inline_text_editor(commit=True)
        el = self.designer.get_element(element_id)
        bounds = self.designer.get_element_bounds(element_id)
        if not el or el["type"] != "text":
            return

        bx, by, bw, bh = bounds if bounds else (el["x"], el["y"], 100, 30)
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        s = self.display_scale

        disp_x = self._canvas_ox + bx * s
        disp_y = self._canvas_oy + by * s
        disp_w = bw * s
        disp_h = bh * s

        entry_w = max(160, int((disp_w + 36) / scaling))
        entry_h = max(36, int((disp_h + 18) / scaling))
        max_x = max(4, int((self._canvas_ox + self.designer.width_px * s) / scaling) - entry_w)
        max_y = max(4, int((self._canvas_oy + self.designer.height_px * s) / scaling) - entry_h)
        pos_x = max(4, min(int(disp_x / scaling), max_x))
        pos_y = max(4, min(int(disp_y / scaling), max_y))

        ui_font_px = max(12, min(26, int(el.get("font_size", 30) * s / (scaling * 2.0))))

        editor = ctk.CTkTextbox(
            self.preview_canvas,
            width=entry_w,
            height=entry_h,
            fg_color="#FFFFFF",
            text_color="#000000",
            border_color="#0067C0",
            border_width=2,
            corner_radius=4,
            font=(UI_FONT, ui_font_px),
        )
        editor.insert("1.0", el["content"])
        editor.place(x=pos_x, y=pos_y)
        editor.lift()
        editor.focus_set()
        editor.tag_add("sel", "1.0", "end-1c")

        editor.bind("<KeyRelease>", self._on_inline_text_key)
        editor.bind("<Return>", self._on_inline_commit_return)
        editor.bind("<Shift-Return>", lambda _e: None)
        editor.bind("<Escape>", lambda _e: self._close_inline_text_editor(commit=False))
        editor.bind("<FocusOut>", lambda _e: self._close_inline_text_editor(commit=True))

        self._inline_editor = editor
        self._inline_edit_meta = {
            "element_id": element_id,
            "original_text": el["content"],
            "pre_snapshot": self._capture_history_state(),
        }
        self.set_status("Editing text inline — Enter apply, Shift+Enter new line, Esc cancel")

    def _on_inline_commit_return(self, _event=None):
        self._close_inline_text_editor(commit=True)
        return "break"

    def _on_inline_text_key(self, _event=None):
        if self._inline_editor is None or not self._inline_edit_meta:
            return
        eid = self._inline_edit_meta["element_id"]
        new_text = self._inline_editor.get("1.0", "end-1c")
        self.designer.update_element_content(eid, new_text)

        self._syncing_controls = True
        try:
            if self.selected_element_id == eid:
                self.entry_edit_text.delete("1.0", "end")
                self.entry_edit_text.insert("1.0", new_text)
        finally:
            self._syncing_controls = False

        self.update_layer_list()
        self.update_preview()

    def _close_inline_text_editor(self, commit=True):
        if self._inline_editor is None:
            return
        editor = self._inline_editor
        meta = self._inline_edit_meta
        self._inline_editor = None
        self._inline_edit_meta = None

        if not commit and meta:
            eid = meta["element_id"]
            orig = meta["original_text"]
            self.designer.update_element_content(eid, orig)
            self._syncing_controls = True
            try:
                if self.selected_element_id == eid:
                    self.entry_edit_text.delete("1.0", "end")
                    self.entry_edit_text.insert("1.0", orig)
            finally:
                self._syncing_controls = False
            self.update_layer_list()
            self.update_preview()
            self.set_status("Canceled inline text edit")
        elif meta:
            el = self.designer.get_element(meta["element_id"])
            if el and el["content"] != meta["original_text"]:
                self._commit_history_step(meta.get("pre_snapshot"), mark_dirty=True)
            if el:
                self.set_status(f"Updated text: {el['content']}")

        try:
            editor.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Preview, Layers & State Sync
    # ------------------------------------------------------------------
    def on_theme_change(self, mode):
        ctk.set_appearance_mode(mode)
        self.after(50, self._apply_win11_titlebar)
        self.after(50, self._sync_font_listbox_colors)
        self.after(50, self._sync_canvas_stage_color)
        self.set_status(f"Theme set to {mode}")

    def on_zoom_change(self, value):
        self._close_inline_text_editor(commit=True)
        self.zoom_mode = value
        if value != "Fit":
            self.display_scale = float(value.replace("x", ""))
        self.update_preview()
        self.set_status(f"Zoom: {value}")

    def update_preview(self):
        avail_w = self.preview_canvas.winfo_width()
        avail_h = self.preview_canvas.winfo_height()
        if avail_w <= 10:
            avail_w = 640
        if avail_h <= 10:
            avail_h = 440

        pad = 24
        if self.zoom_mode == "Fit":
            fit_w = max(100, avail_w - 2 * pad) / max(1, self.designer.width_px)
            fit_h = max(100, avail_h - 2 * pad) / max(1, self.designer.height_px)
            self.display_scale = max(0.5, min(fit_w, fit_h, 2.0))

        s = self.display_scale
        disp_w = max(1, int(self.designer.width_px * s))
        disp_h = max(1, int(self.designer.height_px * s))

        virt_w = max(avail_w, disp_w + 2 * pad)
        virt_h = max(avail_h, disp_h + 2 * pad)
        ox = (virt_w - disp_w) // 2
        oy = (virt_h - disp_h) // 2
        self._canvas_ox = ox
        self._canvas_oy = oy

        # Toggle scrollbars only when zoomed larger than stage
        if virt_w > avail_w:
            self._h_scroll.grid(row=1, column=0, sticky="ew")
        else:
            self._h_scroll.grid_remove()
        if virt_h > avail_h:
            self._v_scroll.grid(row=0, column=1, sticky="ns")
        else:
            self._v_scroll.grid_remove()

        self.preview_canvas.configure(scrollregion=(0, 0, virt_w, virt_h))
        self.preview_canvas.delete("all")

        # Subtle paper frame border
        self.preview_canvas.create_rectangle(
            ox - 2, oy - 2, ox + disp_w + 1, oy + disp_h + 1,
            outline="#9A9A9A", width=1
        )

        # Render pure label image scaled smoothly to display size
        resized = self.designer.image.resize((disp_w, disp_h), Image.Resampling.BILINEAR)
        self._tk_preview_img = ImageTk.PhotoImage(resized)
        self.preview_canvas.create_image(ox, oy, anchor="nw", image=self._tk_preview_img)

        # Snap guide lines while dragging
        for gx in self._active_snap_guides.get("x", []):
            sx = ox + gx * s
            self.preview_canvas.create_line(
                sx, oy, sx, oy + disp_h, fill="#E81123", width=1, dash=(4, 3)
            )
        for gy in self._active_snap_guides.get("y", []):
            sy = oy + gy * s
            self.preview_canvas.create_line(
                ox, sy, ox + disp_w, sy, fill="#E81123", width=1, dash=(4, 3)
            )

        # Crisp vector selection outline + corner resize handles
        if self.selected_element_id is not None:
            el = self.designer.get_element(self.selected_element_id)
            bounds = self.designer.get_element_bounds(self.selected_element_id)
            if bounds:
                bx, by, bw, bh = bounds
                if bw > 0 and bh > 0:
                    x0 = ox + bx * s
                    y0 = oy + by * s
                    x1 = ox + (bx + bw) * s
                    y1 = oy + (by + bh) * s
                    self.preview_canvas.create_rectangle(
                        x0, y0, x1, y1, outline="#0067C0", width=2
                    )
                    if el and el["type"] in ("image", "shape"):
                        r = 5
                        for hx, hy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                            self.preview_canvas.create_rectangle(
                                hx - r, hy - r, hx + r, hy + r,
                                fill="#FFFFFF", outline="#0067C0", width=2
                            )

    def update_layer_list(self):
        for btn in self.layer_buttons.values():
            btn.destroy()
        self.layer_buttons = {}

        self.lbl_layers_title.configure(text=f"Layers ({len(self.designer.elements)})")

        # Display topmost layer first
        for el in reversed(self.designer.elements):
            is_selected = el["id"] == self.selected_element_id
            if el["type"] == "text":
                prefix = "T  "
            elif el["type"] == "shape":
                prefix = "BOX  " if el.get("shape") == "rect" else "LINE  "
            else:
                prefix = "IMG  "
            btn_text = f"{prefix}{el['name']}"

            btn = ctk.CTkButton(
                self.layer_frame,
                text=btn_text,
                fg_color=FLUENT["accent_soft"] if is_selected else "transparent",
                hover_color=FLUENT["accent_soft"] if is_selected else FLUENT["card_alt"],
                border_width=1,
                border_color=FLUENT["accent"] if is_selected else FLUENT["border"],
                text_color=FLUENT["text"],
                height=32,
                corner_radius=6,
                anchor="w",
                font=(UI_FONT, 12, "bold" if is_selected else "normal"),
                command=lambda eid=el["id"]: self.select_element(eid),
            )
            btn.pack(fill="x", pady=2, padx=2)
            self.layer_buttons[el["id"]] = btn

    def select_element(self, element_id):
        self._close_font_picker()
        if self._inline_edit_meta and self._inline_edit_meta.get("element_id") != element_id:
            self._close_inline_text_editor(commit=True)
        self.selected_element_id = element_id
        self.update_layer_list()

        el = self.designer.get_element(element_id)
        if el:
            self._syncing_controls = True
            try:
                self._sync_position_widgets(el["x"], el["y"])

                if el["type"] == "image":
                    scale = el.get("scale", 1.0)
                    self.slider_scale.set(scale)
                    self.lbl_scale_val.configure(text=f"{int(scale * 100)}%")
                elif el["type"] == "text":
                    self._set_font_picker_value(el.get("font", "arial.ttf"))
                    fsize = el.get("font_size", 30)
                    self.slider_fontsize.set(fsize)
                    self.lbl_fontsize_val.configure(text=f"{int(fsize)} pt")

                    align_map = {"left": "Left", "center": "Center", "right": "Right"}
                    self.align_seg.set(align_map.get(el.get("align", "left"), "Left"))

                    self.entry_edit_text.configure(state="normal")
                    self.entry_edit_text.delete("1.0", "end")
                    self.entry_edit_text.insert("1.0", el["content"])
                elif el["type"] == "shape":
                    stroke = el.get("stroke_width", 3)
                    self.slider_stroke.set(stroke)
                    self.lbl_stroke_val.configure(text=f"{int(stroke)} px")
                    if el.get("filled", False):
                        self.chk_shape_fill.select()
                    else:
                        self.chk_shape_fill.deselect()

                current_rot = el.get("rotation", 0)
                rot_map = {0: "0°", 90: "90°", 180: "180°", 270: "270°"}
                self.rotation_seg.set(rot_map.get(current_rot, "0°"))
            finally:
                self._syncing_controls = False

        self.update_control_state()
        self.update_preview()

    def update_control_state(self):
        el = self.designer.get_element(self.selected_element_id) if self.selected_element_id else None

        state_global = "normal" if el else "disabled"
        for widget in (
            self.slider_x,
            self.slider_y,
            self.btn_center_h,
            self.btn_center_v,
            self.btn_center_both,
            self.rotation_seg,
            self.btn_delete_el,
            self.btn_duplicate_el,
            self.btn_layer_up,
            self.btn_layer_down,
        ):
            widget.configure(state=state_global)

        if el:
            self.lbl_selection_hint.configure(text=f"Editing: {el['name']}")
            self.lbl_coords_status.configure(text=f"X: {el['x']} px, Y: {el['y']} px")
        else:
            self.lbl_selection_hint.configure(text="Select an element on the canvas or in Layers")
            self.lbl_coords_status.configure(text="No selection")

        # Image specific controls
        is_image = bool(el and el["type"] == "image")
        img_state = "normal" if is_image else "disabled"
        self.slider_scale.configure(state=img_state)
        self.btn_reset_scale.configure(state=img_state)

        # Text specific controls
        is_text = bool(el and el["type"] == "text")
        txt_state = "normal" if is_text else "disabled"
        if not is_text:
            self._close_font_picker()
        for widget in (
            self.btn_font_picker,
            self.slider_fontsize,
            self.entry_edit_text,
            self.btn_update_text,
            self.align_seg,
        ):
            widget.configure(state=txt_state)

        # Shape specific controls
        is_shape = bool(el and el["type"] == "shape")
        shp_state = "normal" if is_shape else "disabled"
        self.slider_stroke.configure(state=shp_state)
        is_box = bool(is_shape and el.get("shape") == "rect")
        self.chk_shape_fill.configure(state="normal" if is_box else "disabled")

    # ------------------------------------------------------------------
    # Property Callbacks
    # ------------------------------------------------------------------
    def on_pos_change(self, _value):
        if self._syncing_controls or not self.selected_element_id:
            return
        x = int(self.slider_x.get())
        y = int(self.slider_y.get())
        self.designer.update_element_position(self.selected_element_id, x, y)
        self.label_val_x.configure(text=f"X: {x} px")
        self.label_val_y.configure(text=f"Y: {y} px")
        self.lbl_coords_status.configure(text=f"X: {x} px, Y: {y} px")
        self.update_preview()
        self._set_dirty(True)

    def center_selected(self, horizontal=True, vertical=True):
        if not self.selected_element_id:
            return
        prev = self._capture_history_state()
        self.designer.center_element(self.selected_element_id, horizontal=horizontal, vertical=vertical)
        el = self.designer.get_element(self.selected_element_id)
        if el:
            self._sync_position_widgets(el["x"], el["y"])
            self.update_preview()
            self._commit_history_step(prev, mark_dirty=True)
            self.set_status("Centered element")

    def on_scale_change(self, value, sync_slider=False):
        if self._syncing_controls or not self.selected_element_id:
            return
        scale = float(value)
        if sync_slider:
            prev = self._capture_history_state()
            self._syncing_controls = True
            self.slider_scale.set(scale)
            self._syncing_controls = False
        self.lbl_scale_val.configure(text=f"{int(scale * 100)}%")
        self.designer.update_element_scale(self.selected_element_id, scale)
        self.update_preview()
        if sync_slider:
            self._commit_history_step(prev, mark_dirty=True)
        else:
            self._set_dirty(True)

    @staticmethod
    def parse_rotation(value):
        text = str(value)
        if "Left" in text or "90" in text:
            return 90
        if "Down" in text or "180" in text:
            return 180
        if "Right" in text or "270" in text:
            return 270
        return 0

    def on_rotation_change(self, value):
        if self._syncing_controls:
            return
        logger.info(f"UI: Rotation changed to {value}")
        if self.selected_element_id:
            try:
                prev = self._capture_history_state()
                angle = self.parse_rotation(value)
                logger.info(f"UI: Applying rotation {angle} to element {self.selected_element_id}")
                self.designer.update_element_rotation(self.selected_element_id, angle)
                self.update_preview()
                self._commit_history_step(prev, mark_dirty=True)
                self.set_status(f"Rotated to {angle}°")
            except Exception as e:
                logger.error(f"Rotation parsing error: {e}")
        else:
            logger.warning("UI: Rotation changed but no element selected")

    def _get_font_display_name(self, font_ref):
        if not font_ref:
            return "Arial"
        key = str(font_ref).lower()
        if key in self.font_ref_to_name:
            return self.font_ref_to_name[key]
        base = os.path.basename(str(font_ref))
        if base.lower() in self.font_ref_to_name:
            return self.font_ref_to_name[base.lower()]
        return os.path.splitext(base)[0]

    def _set_font_picker_value(self, font_ref):
        self._current_font_ref = font_ref
        self.btn_font_picker.configure(text=f"{self._get_font_display_name(font_ref)}  ▾")

    def _sync_font_listbox_colors(self):
        is_dark = ctk.get_appearance_mode() == "Dark"
        idx = 1 if is_dark else 0
        self.font_listbox.configure(
            bg=FLUENT["card"][idx],
            fg=FLUENT["text"][idx],
            selectbackground=FLUENT["accent"][idx],
            selectforeground="#FFFFFF",
        )

    def _populate_font_listbox(self, items):
        self._filtered_fonts = list(items)
        self.font_listbox.delete(0, "end")
        if not self._filtered_fonts:
            self.font_listbox.insert("end", "No matching fonts")
            return
        for display_name, font_ref in self._filtered_fonts:
            self.font_listbox.insert("end", display_name)
            if font_ref.lower() == str(self._current_font_ref).lower():
                last_idx = self.font_listbox.size() - 1
                self.font_listbox.selection_set(last_idx)
                self.font_listbox.see(last_idx)

    def _filter_font_list(self):
        query = self.entry_font_filter.get().strip().lower()
        if not query:
            matches = self.font_catalog
        else:
            matches = [
                (name, ref)
                for name, ref in self.font_catalog
                if query in name.lower() or query in os.path.basename(ref).lower()
            ]
        self._populate_font_listbox(matches)

    def _clear_font_filter(self):
        self.entry_font_filter.delete(0, "end")
        self._populate_font_listbox(self.font_catalog)
        self.entry_font_filter.focus_set()

    def _focus_font_listbox(self, _event=None):
        if self._filtered_fonts:
            self.font_listbox.focus_set()
            if not self.font_listbox.curselection():
                self.font_listbox.selection_set(0)
            self.font_listbox.activate(0)
        return "break"

    def _on_font_list_mousewheel(self, event):
        step = -int(event.delta / 120)
        if step == 0:
            step = -1 if event.delta > 0 else 1
        self.font_listbox.yview_scroll(step, "units")
        return "break"

    def _is_descendant_of(self, widget, ancestor):
        while widget is not None:
            if widget == ancestor:
                return True
            widget = getattr(widget, "master", None)
        return False

    def _on_global_click(self, event):
        if not self._font_picker_open:
            return
        if self._is_descendant_of(event.widget, self.font_picker_drawer):
            return
        if self._is_descendant_of(event.widget, self.btn_font_picker):
            return
        self._close_font_picker()

    def _on_global_mousewheel(self, event):
        if self._font_picker_open and not self._is_descendant_of(event.widget, self.font_picker_drawer):
            self._close_font_picker()

    def toggle_font_picker(self):
        if self._font_picker_open:
            self._close_font_picker()
        else:
            self._open_font_picker()

    def _open_font_picker(self):
        if not self.selected_element_id:
            return
        self._font_picker_open = True
        self._sync_font_listbox_colors()
        self.entry_font_filter.delete(0, "end")
        self._populate_font_listbox(self.font_catalog)

        self.update_idletasks()
        scaling = ctk.ScalingTracker.get_widget_scaling(self)
        btn_x = (self.btn_font_picker.winfo_rootx() - self.winfo_rootx()) / scaling
        btn_y = (self.btn_font_picker.winfo_rooty() - self.winfo_rooty()) / scaling
        btn_w = max(220, int(self.btn_font_picker.winfo_width() / scaling))
        btn_h = self.btn_font_picker.winfo_height() / scaling
        win_w = self.winfo_width() / scaling
        win_h = self.winfo_height() / scaling

        popup_w = btn_w
        popup_h = self._font_popup_height
        self.font_picker_drawer.configure(width=popup_w, height=popup_h)

        popup_x = max(8, min(btn_x, win_w - popup_w - 8))
        popup_y = btn_y + btn_h + 4
        if popup_y + popup_h > win_h - 32:
            popup_y = max(8, btn_y - popup_h - 4)

        self.font_picker_drawer.place(x=popup_x, y=popup_y)
        self.font_picker_drawer.lift()
        self.entry_font_filter.focus_set()

    def _close_font_picker(self):
        if self._font_picker_open:
            self._font_picker_open = False
            self.font_picker_drawer.place_forget()

    def _select_font_from_listbox(self):
        if not self._filtered_fonts:
            return
        sel = self.font_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._filtered_fonts):
            display_name, font_ref = self._filtered_fonts[idx]
            self.on_font_change(font_ref, display_name=display_name)
            self._close_font_picker()

    def _apply_highlighted_or_first_font(self):
        if not self._filtered_fonts:
            return
        sel = self.font_listbox.curselection()
        idx = sel[0] if sel else 0
        if 0 <= idx < len(self._filtered_fonts):
            display_name, font_ref = self._filtered_fonts[idx]
            self.on_font_change(font_ref, display_name=display_name)
            self._close_font_picker()

    def on_font_change(self, value, display_name=None):
        if self._syncing_controls or not self.selected_element_id:
            return
        prev = self._capture_history_state()
        self._set_font_picker_value(value)
        self.designer.update_element_font(self.selected_element_id, value)
        self.update_preview()
        self._commit_history_step(prev, mark_dirty=True)
        shown = display_name or self._get_font_display_name(value)
        self.set_status(f"Font changed to {shown}")

    def on_text_content_change(self, _event=None):
        if self._syncing_controls or not self.selected_element_id:
            return
        new_text = self.entry_edit_text.get("1.0", "end-1c")
        self.designer.update_element_content(self.selected_element_id, new_text)
        self.update_preview()
        self.update_layer_list()
        self._set_dirty(True)

    def on_fontsize_change(self, value):
        if self._syncing_controls or not self.selected_element_id:
            return
        size = int(value)
        self.lbl_fontsize_val.configure(text=f"{size} pt")
        self.designer.update_element_font_size(self.selected_element_id, size)
        self.update_preview()
        self._set_dirty(True)

    def on_align_change(self, value):
        if self._syncing_controls or not self.selected_element_id:
            return
        prev = self._capture_history_state()
        align_val = str(value).lower()
        self.designer.update_element_align(self.selected_element_id, align_val)
        self.update_preview()
        self._commit_history_step(prev, mark_dirty=True)
        self.set_status(f"Text align: {value}")

    def on_shape_stroke_change(self, value):
        if self._syncing_controls or not self.selected_element_id:
            return
        thickness = int(round(float(value)))
        self.lbl_stroke_val.configure(text=f"{thickness} px")
        self.designer.update_shape_properties(self.selected_element_id, stroke_width=thickness)
        self.update_preview()
        self._set_dirty(True)

    def on_shape_fill_change(self):
        if self._syncing_controls or not self.selected_element_id:
            return
        prev = self._capture_history_state()
        filled = bool(self.chk_shape_fill.get())
        self.designer.update_shape_properties(self.selected_element_id, filled=filled)
        self.update_preview()
        self._commit_history_step(prev, mark_dirty=True)

    # ------------------------------------------------------------------
    # Element & Layer Actions
    # ------------------------------------------------------------------
    def _quick_add_or_focus_text(self):
        if self.entry_text.get("1.0", "end-1c").strip():
            self.add_text_to_label()
        else:
            self.entry_text.focus_set()
            self.set_status("Type text on the left (Enter = new line), then click Add Text")

    def add_text_to_label(self):
        text = self.entry_text.get("1.0", "end-1c")
        if text:
            prev = self._capture_history_state()
            el = self.designer.add_text(text)
            self.entry_text.delete("1.0", "end")
            logger.info(f"UI: Added text: {text}")
            self.select_element(el["id"])
            self._commit_history_step(prev, mark_dirty=True)
            self.set_status(f"Added text: {el['name']}")

    def add_box_shape(self):
        prev = self._capture_history_state()
        el = self.designer.add_shape("rect")
        self.select_element(el["id"])
        self._commit_history_step(prev, mark_dirty=True)
        self.set_status(f"Added {el['name']}")

    def add_line_shape(self):
        prev = self._capture_history_state()
        el = self.designer.add_shape("line")
        self.select_element(el["id"])
        self._commit_history_step(prev, mark_dirty=True)
        self.set_status(f"Added {el['name']}")

    def upload_image(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.jpg;*.jpeg;*.png;*.bmp;*.webp")]
        )
        if file_path:
            prev = self._capture_history_state()
            el = self.designer.add_image(file_path)
            if el:
                logger.info(f"UI: Added image from {file_path}")
                self.select_element(el["id"])
                self._commit_history_step(prev, mark_dirty=True)
                self.set_status(f"Added image: {os.path.basename(file_path)}")

    def move_selected_layer(self, direction):
        if not self.selected_element_id:
            return
        prev = self._capture_history_state()
        if self.designer.move_element_order(self.selected_element_id, direction):
            self.update_layer_list()
            self.update_preview()
            self._commit_history_step(prev, mark_dirty=True)
            self.set_status("Updated layer order")

    def duplicate_element_action(self):
        if self.selected_element_id:
            prev = self._capture_history_state()
            source_id = self.selected_element_id
            new_el = self.designer.duplicate_element(source_id)
            if new_el:
                self.select_element(new_el["id"])
                self._commit_history_step(prev, mark_dirty=True)
                logger.info(f"UI: Duplicated element {source_id} -> {new_el['id']}")
                self.set_status(f"Duplicated element #{source_id}")

    def delete_element(self):
        self._close_inline_text_editor(commit=False)
        if self.selected_element_id:
            prev = self._capture_history_state()
            removed_id = self.selected_element_id
            self.designer.remove_element(removed_id)
            self.selected_element_id = None
            self.update_preview()
            self.update_layer_list()
            self.update_control_state()
            self._commit_history_step(prev, mark_dirty=True)
            self.set_status(f"Deleted element #{removed_id}")

    def clear_label(self):
        if not self._confirm_discard_changes():
            return
        self._close_inline_text_editor(commit=False)
        self.designer.clear()
        self.selected_element_id = None
        self._set_current_project(None)
        self._clear_autosave_draft()
        self._reset_history()
        self.update_preview()
        self.update_layer_list()
        self.update_control_state()
        self.set_status("Cleared canvas")

    # ------------------------------------------------------------------
    # Windows File Context Menu & Recent Files
    # ------------------------------------------------------------------
    @staticmethod
    def _default_recent_store_path():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "LabelPrinterStudio", "recent_files.json")

    @staticmethod
    def _default_autosave_draft_path():
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "LabelPrinterStudio", "autosave_draft.json")

    def _load_recent_files(self):
        try:
            if os.path.exists(self._recent_store_path):
                with open(self._recent_store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [os.path.normpath(p) for p in data if isinstance(p, str)][:10]
        except Exception as e:
            logger.warning(f"Failed to load recent files: {e}")
        return []

    def _save_recent_files(self):
        try:
            os.makedirs(os.path.dirname(self._recent_store_path), exist_ok=True)
            with open(self._recent_store_path, "w", encoding="utf-8") as f:
                json.dump(self.recent_files[:10], f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Failed to save recent files: {e}")

    def _add_recent_file(self, file_path):
        norm = os.path.normpath(file_path)
        norm_key = os.path.normcase(norm)
        self.recent_files = [norm] + [
            p for p in self.recent_files if os.path.normcase(os.path.normpath(p)) != norm_key
        ]
        self.recent_files = self.recent_files[:10]
        self._save_recent_files()

    def _remove_recent_file(self, file_path):
        norm_key = os.path.normcase(os.path.normpath(file_path))
        self.recent_files = [
            p for p in self.recent_files if os.path.normcase(os.path.normpath(p)) != norm_key
        ]
        self._save_recent_files()

    def _clear_recent_files(self):
        self.recent_files = []
        self._save_recent_files()
        self.set_status("Cleared recent files list")

    def _build_file_menu(self):
        self.file_menu = Menu(self, tearoff=0)
        self.recent_menu = Menu(self.file_menu, tearoff=0)

        self.file_menu.add_command(label="New", accelerator="Ctrl+N", command=self.clear_label)
        self.file_menu.add_command(label="Open...", accelerator="Ctrl+O", command=self.load_project_action)
        self.file_menu.add_cascade(label="Open Recent", menu=self.recent_menu)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_project_action)
        self.file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_project_as_action)
        self.file_menu.add_checkbutton(label="Autosave", variable=self.autosave_var, command=self.on_autosave_toggle)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Print...", accelerator="Ctrl+P", command=self.print_label)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", accelerator="Alt+F4", command=self.on_closing)

    def _rebuild_recent_menu(self):
        self.recent_menu.delete(0, "end")
        if not self.recent_files:
            self.recent_menu.add_command(label="(No recent files)", state="disabled")
            return
        for idx, path in enumerate(self.recent_files, start=1):
            name = os.path.basename(path)
            folder = os.path.dirname(path)
            label = f"{idx}. {name}  —  {folder}"
            self.recent_menu.add_command(
                label=label,
                command=lambda p=path: self._open_recent_file(p),
            )
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Clear Recent List", command=self._clear_recent_files)

    def show_file_menu(self):
        self._close_font_picker()
        self._close_inline_text_editor(commit=True)
        self._rebuild_recent_menu()
        x = self.btn_file_menu.winfo_rootx()
        y = self.btn_file_menu.winfo_rooty() + self.btn_file_menu.winfo_height() + 2
        try:
            self.file_menu.tk_popup(x, y)
        finally:
            self.file_menu.grab_release()

    def _open_recent_file(self, file_path):
        if not os.path.exists(file_path):
            messagebox.showwarning(
                "File Not Found",
                f"The file no longer exists:\n{file_path}\n\nIt will be removed from Recent Files.",
            )
            self._remove_recent_file(file_path)
            return
        if not self._confirm_discard_changes():
            return
        self._load_project_from_path(file_path)

    # ------------------------------------------------------------------
    # Project & Printing
    # ------------------------------------------------------------------
    def _set_current_project(self, file_path):
        if file_path:
            norm_path = os.path.normpath(file_path)
            self.current_project_path = norm_path
            folder = os.path.dirname(norm_path)
            filename = os.path.basename(norm_path)
            self.lbl_project_path.configure(text=f"Saved in: {folder}  ({filename})")
        else:
            self.current_project_path = None
            self.lbl_project_path.configure(text="Location: Not saved yet")
        self._refresh_window_title()

    def _step_copies(self, delta):
        try:
            current = int(self.entry_copies.get())
        except ValueError:
            current = 1
        new_val = max(1, current + delta)
        self.entry_copies.delete(0, "end")
        self.entry_copies.insert(0, str(new_val))

    def refresh_printers(self):
        detected = printer_utils.list_printers()
        self.printers = detected if detected else ["No Printers Found"]
        self.printer_dropdown.configure(values=self.printers)
        if self.printer_var.get() not in self.printers:
            self.printer_var.set(self.printers[0])
        self.set_status(f"Found {len(detected)} printer(s)")

    def _write_project_to_path(self, file_path):
        if self.designer.save_project(file_path):
            self._set_current_project(file_path)
            norm_path = self.current_project_path
            self._add_recent_file(norm_path)
            self._clear_autosave_draft()
            self._set_dirty(False)
            self._last_snapshot = self._capture_history_state()
            logger.info(f"UI: Saved project to {norm_path}")
            self.set_status(f"Saved: {norm_path}")
            return True
        messagebox.showerror("Save Failed", "Could not save project file.")
        return False

    def save_project_action(self):
        if self.current_project_path:
            self._write_project_to_path(self.current_project_path)
        else:
            self.save_project_as_action()

    def save_project_as_action(self):
        dialog_kwargs = {
            "defaultextension": ".json",
            "filetypes": [("JSON Files", "*.json")],
        }
        if self.current_project_path:
            dialog_kwargs["initialdir"] = os.path.dirname(self.current_project_path)
            dialog_kwargs["initialfile"] = os.path.basename(self.current_project_path)
        file_path = filedialog.asksaveasfilename(**dialog_kwargs)
        if file_path:
            self._write_project_to_path(file_path)

    def _load_project_from_path(self, file_path):
        self._close_inline_text_editor(commit=False)
        valid = self.designer.load_project(file_path)
        if valid:
            self.selected_element_id = None
            self._set_current_project(file_path)
            self._add_recent_file(self.current_project_path)
            self.slider_x.configure(to=self.designer.width_px)
            self.slider_y.configure(to=self.designer.height_px)
            self.lbl_canvas_spec.configure(
                text=f"Label Canvas  •  {self.designer.width_mm} × {self.designer.height_mm} mm ({self.designer.width_px}×{self.designer.height_px} px)"
            )
            self.update_layer_list()
            self.update_preview()
            self.update_control_state()
            self._reset_history()
            logger.info(f"UI: Loaded project from {file_path}")
            self.set_status(f"Opened: {self.current_project_path}")
            return True
        messagebox.showerror("Load Failed", "Could not load project file.")
        return False

    def load_project_action(self):
        if not self._confirm_discard_changes():
            return
        dialog_kwargs = {"filetypes": [("JSON Files", "*.json")]}
        if self.current_project_path:
            dialog_kwargs["initialdir"] = os.path.dirname(self.current_project_path)
        file_path = filedialog.askopenfilename(**dialog_kwargs)
        if file_path:
            self._load_project_from_path(file_path)

    def print_label(self):
        selected_printer = self.printer_var.get()
        if selected_printer == "No Printers Found" or not selected_printer:
            logger.warning("UI: Print Attempted (No printer selected)")
            self.set_status("No printer selected")
            messagebox.showwarning("Printer Required", "No printer is selected or available.")
            return

        try:
            copies = int(self.entry_copies.get())
        except ValueError:
            copies = 1
        if copies < 1:
            logger.warning(f"UI: Invalid copies '{copies}', defaulting to 1")
            copies = 1
            self.entry_copies.delete(0, "end")
            self.entry_copies.insert(0, "1")

        # Snapshot pure canvas (without selection outline) on the UI thread
        image_snapshot = self.designer.image.copy()

        self.btn_print.configure(state="disabled", text="Printing...")
        self.set_status(f"Sending {copies} copy(ies) to {selected_printer}...")

        def run_print():
            temp_path = None
            success = False
            error_msg = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    temp_path = tmp.name

                image_snapshot.save(temp_path)
                success = printer_utils.print_image(temp_path, selected_printer, copies=copies)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"UI: Print Error: {e}", exc_info=True)
            finally:
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass

                def finish_ui():
                    self.btn_print.configure(state="normal", text="Print Label")
                    if success:
                        logger.info(f"UI: Print Success: {selected_printer} ({copies} copies)")
                        self.set_status(f"Printed {copies} copy(ies) to {selected_printer}")
                    else:
                        logger.error("UI: Print Failed")
                        self.set_status("Print failed — check printer connection")
                        messagebox.showerror(
                            "Print Failed",
                            error_msg or f"Failed to print to '{selected_printer}'. Check app.log for details.",
                        )

                self.after(0, finish_ui)

        threading.Thread(target=run_print, daemon=True).start()


if __name__ == "__main__":
    app = LabelApp()
    app.mainloop()
