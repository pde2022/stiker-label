import customtkinter as ctk
from tkinter import filedialog
from PIL import Image, ImageTk, ImageFont, ImageDraw
import os
import win32print
from .label_designer import LabelDesigner
import logging
from . import printer_utils
import threading
from . import font_manager  # Import the new font manager
from . import logging_config

# Setup logging immediately
logging_config.setup_logging()
logger = logging.getLogger(__name__)

class LabelApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Label Printer (50.8mm x 31mm)")
        self.geometry("1000x700")

        # Initialize Designer
        self.designer = LabelDesigner()
        self.selected_element_id = None
        
        # Available Fonts from System
        self.available_fonts = font_manager.get_system_fonts()
        if not self.available_fonts:
            self.available_fonts = ["arial.ttf"]
        
        # Layout
        self.grid_columnconfigure(0, weight=1) # Controls
        self.grid_columnconfigure(1, weight=3) # Preview
        self.grid_rowconfigure(0, weight=1)

        # === Left Panel (Controls) ===
        self.left_frame = ctk.CTkScrollableFrame(self, width=300)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # -- File Operations --
        ctk.CTkLabel(self.left_frame, text="File", font=("Arial", 14, "bold")).pack(pady=5)
        
        self.file_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.file_frame.pack(pady=0, padx=10, fill="x")
        
        self.btn_save = ctk.CTkButton(self.file_frame, text="Save", width=80, command=self.save_project_action)
        self.btn_save.pack(side="left", padx=2, expand=True, fill="x")
        
        self.btn_load = ctk.CTkButton(self.file_frame, text="Load", width=80, command=self.load_project_action)
        self.btn_load.pack(side="right", padx=2, expand=True, fill="x")

        ctk.CTkFrame(self.left_frame, height=2, fg_color="gray").pack(fill="x", pady=10)

        # -- Add New Elements --
        ctk.CTkLabel(self.left_frame, text="Add Elements", font=("Arial", 14, "bold")).pack(pady=5)
        
        self.entry_text = ctk.CTkEntry(self.left_frame, placeholder_text="Enter text (supports emoji 🐔)")
        self.entry_text.pack(pady=5, padx=10, fill="x")

        self.btn_add_text = ctk.CTkButton(self.left_frame, text="Add Text", command=self.add_text_to_label)
        self.btn_add_text.pack(pady=5, padx=10, fill="x")

        self.btn_upload_image = ctk.CTkButton(self.left_frame, text="Add Image", command=self.upload_image)
        self.btn_upload_image.pack(pady=5, padx=10, fill="x")

        ctk.CTkFrame(self.left_frame, height=2, fg_color="gray").pack(fill="x", pady=10)

        # -- Layer Controls --
        ctk.CTkLabel(self.left_frame, text="Layers", font=("Arial", 14, "bold")).pack(pady=5)
        
        # Layer List (Scrollable Frame acting as listbox)
        # Layer List (Use regular Frame inside the scrollable left_frame)
        self.layer_frame = ctk.CTkFrame(self.left_frame)
        self.layer_frame.pack(pady=5, padx=10, fill="x")
        self.layer_buttons = {} # id -> button widget

        # -- Customization Controls --
        self.style_frame = ctk.CTkFrame(self.left_frame)
        self.style_frame.pack(pady=5, padx=10, fill="x")
        
        # Font Control (For Text)
        self.lbl_font = ctk.CTkLabel(self.style_frame, text="Font:")
        self.lbl_font.grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.font_var = ctk.StringVar(value=self.available_fonts[0])
        self.font_dropdown = ctk.CTkOptionMenu(self.style_frame, variable=self.font_var, values=self.available_fonts, command=self.on_font_change)
        self.font_dropdown.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        # Font Size Control (For Text)
        self.lbl_fontsize = ctk.CTkLabel(self.style_frame, text="Size:")
        self.lbl_fontsize.grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.slider_fontsize = ctk.CTkSlider(self.style_frame, from_=10, to=100, command=self.on_fontsize_change)
        self.slider_fontsize.set(30)
        self.slider_fontsize.grid(row=1, column=1, padx=5, pady=2, sticky="ew")

        # Scale Control (For Image)
        self.lbl_scale = ctk.CTkLabel(self.style_frame, text="Scale:")
        self.lbl_scale.grid(row=2, column=0, padx=5, pady=2, sticky="w")
        
        self.slider_scale = ctk.CTkSlider(self.style_frame, from_=0.1, to=3.0, command=self.on_scale_change)
        self.slider_scale.grid(row=2, column=1, padx=5, pady=2, sticky="ew")

        # Rotation Control
        self.lbl_rotation = ctk.CTkLabel(self.style_frame, text="Rotation:")
        self.lbl_rotation.grid(row=3, column=0, padx=5, pady=2, sticky="w")
        
        self.rotation_values = ["Up (0°)", "Left (90°)", "Down (180°)", "Right (270°)"]
        self.rotation_var = ctk.StringVar(value=self.rotation_values[0])
        self.rotation_dropdown = ctk.CTkOptionMenu(self.style_frame, variable=self.rotation_var, values=self.rotation_values, command=self.on_rotation_change)
        self.rotation_dropdown.grid(row=3, column=1, padx=5, pady=2, sticky="ew")

        # Text Content Edit
        self.lbl_edit_text = ctk.CTkLabel(self.style_frame, text="Edit:")
        self.lbl_edit_text.grid(row=4, column=0, padx=5, pady=2, sticky="w")
        
        self.entry_edit_text = ctk.CTkEntry(self.style_frame)
        self.entry_edit_text.grid(row=4, column=1, padx=5, pady=2, sticky="ew")
        self.entry_edit_text.bind("<Return>", self.on_text_content_change)
        
        self.btn_update_text = ctk.CTkButton(self.style_frame, text="Update", width=60, command=self.on_text_content_change)
        self.btn_update_text.grid(row=4, column=2, padx=5, pady=2)

        # -- Position Controls --
        self.pos_frame = ctk.CTkFrame(self.left_frame)
        self.pos_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(self.pos_frame, text="Position (X, Y)").grid(row=0, column=0, columnspan=2, pady=5)
        
        self.slider_x = ctk.CTkSlider(self.pos_frame, from_=0, to=406, command=self.on_pos_change)
        self.slider_x.grid(row=1, column=0, padx=5, pady=5)
        self.label_val_x = ctk.CTkLabel(self.pos_frame, text="X: 0")
        self.label_val_x.grid(row=1, column=1, padx=5)

        self.slider_y = ctk.CTkSlider(self.pos_frame, from_=0, to=248, command=self.on_pos_change)
        self.slider_y.grid(row=2, column=0, padx=5, pady=5)
        self.label_val_y = ctk.CTkLabel(self.pos_frame, text="Y: 0")
        self.label_val_y.grid(row=2, column=1, padx=5)
        
        self.btn_duplicate_el = ctk.CTkButton(self.pos_frame, text="Duplicate", fg_color="orange", command=self.duplicate_element_action)
        self.btn_duplicate_el.grid(row=3, column=0, pady=10, data=5, sticky="ew")

        self.btn_delete_el = ctk.CTkButton(self.pos_frame, text="Delete", fg_color="red", command=self.delete_element)
        self.btn_delete_el.grid(row=3, column=1, pady=10, padx=5, sticky="ew")

        # -- Printing --
        ctk.CTkFrame(self.left_frame, height=2, fg_color="gray").pack(fill="x", pady=10)
        ctk.CTkLabel(self.left_frame, text="Printing", font=("Arial", 14, "bold")).pack(pady=5)

        self.printer_var = ctk.StringVar(value="Select Printer")
        self.printers = printer_utils.list_printers() if printer_utils.list_printers() else ["No Printers Found"]
        self.printer_dropdown = ctk.CTkOptionMenu(self.left_frame, variable=self.printer_var, values=self.printers)
        self.printer_dropdown.set(self.printers[0])
        self.printer_dropdown.pack(pady=5, padx=10, fill="x")
        
        # Copies Input
        self.copies_frame = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        self.copies_frame.pack(pady=5, padx=10, fill="x")
        
        ctk.CTkLabel(self.copies_frame, text="Copies:").pack(side="left", padx=5)
        self.entry_copies = ctk.CTkEntry(self.copies_frame, width=50)
        self.entry_copies.insert(0, "1")
        self.entry_copies.pack(side="left", padx=5)

        self.btn_print = ctk.CTkButton(self.left_frame, text="Print Label", command=self.print_label, fg_color="green")
        self.btn_print.pack(pady=5, padx=10, fill="x")
        
        self.btn_clear = ctk.CTkButton(self.left_frame, text="Clear All", fg_color="darkred", command=self.clear_label)
        self.btn_clear.pack(pady=5, padx=10, fill="x")


        # === Right Panel (Preview) ===
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.right_frame, text="Preview", font=("Arial", 16, "bold")).pack(pady=10)
        
        self.preview_image_label = ctk.CTkLabel(self.right_frame, text="") 
        self.preview_image_label.pack(pady=50, expand=True)

        self.update_preview()
        self.update_layer_list()
        self.update_control_state()

    def update_preview(self):
        pil_image = self.designer.image
        
        # Scale for display (e.g. 2x)
        display_scale = 2
        display_width = int(pil_image.width * display_scale)
        display_height = int(pil_image.height * display_scale)
        
        ctk_img = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(display_width, display_height))
        self.preview_image_label.configure(image=ctk_img)
        self.preview_image_label.image = ctk_img 

    def update_layer_list(self):
        # Clear existing buttons
        for btn in self.layer_buttons.values():
            btn.destroy()
        self.layer_buttons = {}

        for el in self.designer.elements:
            btn_text = el['name']
            if el['id'] == self.selected_element_id:
                fg_color = ["#3B8ED0", "#1F6AA5"] # Standard CTk blue
            else:
                fg_color = "transparent"
                
            btn = ctk.CTkButton(self.layer_frame, text=btn_text, fg_color=fg_color, 
                                border_width=1, border_color="gray",
                                height=30, anchor="w",
                                command=lambda eid=el['id']: self.select_element(eid))
            btn.pack(fill="x", pady=2)
            self.layer_buttons[el['id']] = btn

    def select_element(self, element_id):
        self.selected_element_id = element_id
        
        # Update layer list visually
        for eid, btn in self.layer_buttons.items():
            if eid == element_id:
                 btn.configure(fg_color=["#3B8ED0", "#1F6AA5"]) 
            else:
                 btn.configure(fg_color="transparent")

        # Update controls values
        el = self.designer.get_element(element_id)
        if el:
            self.slider_x.set(el['x'])
            self.slider_y.set(el['y'])
            self.label_val_x.configure(text=f"X: {el['x']}")
            self.label_val_y.configure(text=f"Y: {el['y']}")
            
            # Update specific controls values
            if el['type'] == 'image':
                scale = el.get('scale', 1.0)
                self.slider_scale.set(scale)
            elif el['type'] == 'text':
                self.font_dropdown.set(el.get('font', 'arial.ttf'))
                self.slider_fontsize.set(el.get('font_size', 30))
                
                # Update edit text entry
                self.entry_edit_text.delete(0, "end")
                self.entry_edit_text.insert(0, el['content'])
            
            # Update rotation
            current_rot = el.get('rotation', 0)
            # Map valid rotations to dropdown strings
            rot_map = {0: "Up (0°)", 90: "Left (90°)", 180: "Down (180°)", 270: "Right (270°)"}
            # Default to Up if custom rotation exists (or handle custom logic if needed)
            self.rotation_var.set(rot_map.get(current_rot, "Up (0°)"))
            
        self.update_control_state()

    def update_control_state(self):
        el = self.designer.get_element(self.selected_element_id) if self.selected_element_id else None
        
        # Global position controls
        state_global = "normal" if el else "disabled"
        self.slider_x.configure(state=state_global)
        self.slider_y.configure(state=state_global)
        self.btn_delete_el.configure(state=state_global)
        self.lbl_rotation.configure(state=state_global)
        self.rotation_dropdown.configure(state=state_global)
        self.btn_duplicate_el.configure(state=state_global)

        # Image specific controls - CENTRALIZED LOGIC
        if el and el['type'] == 'image':
            self.lbl_scale.configure(state="normal")
            self.slider_scale.configure(state="normal")
        else:
            self.lbl_scale.configure(state="disabled")
            self.slider_scale.configure(state="disabled")

        # Text specific controls - CENTRALIZED LOGIC
        if el and el['type'] == 'text':
            self.lbl_font.configure(state="normal")
            self.font_dropdown.configure(state="normal")
            self.lbl_fontsize.configure(state="normal")
            self.slider_fontsize.configure(state="normal")
            self.lbl_edit_text.configure(state="normal")
            self.entry_edit_text.configure(state="normal")
            self.btn_update_text.configure(state="normal")
        else:
            self.lbl_font.configure(state="disabled")
            self.font_dropdown.configure(state="disabled")
            self.lbl_fontsize.configure(state="disabled")
            self.slider_fontsize.configure(state="disabled")
            self.lbl_edit_text.configure(state="disabled")
            self.entry_edit_text.configure(state="disabled")
            self.btn_update_text.configure(state="disabled")

    def on_pos_change(self, value):
        if self.selected_element_id:
            x = int(self.slider_x.get())
            y = int(self.slider_y.get())
            self.designer.update_element_position(self.selected_element_id, x, y)
            self.label_val_x.configure(text=f"X: {x}")
            self.label_val_y.configure(text=f"Y: {y}")
            self.update_preview()
            
    def on_scale_change(self, value):
        if self.selected_element_id:
            self.designer.update_element_scale(self.selected_element_id, value)
            self.update_preview()

    def on_rotation_change(self, value):
        logger.info(f"UI: Rotation changed to {value}")
        if self.selected_element_id:
            # Parse value string to get integer
            # "Up (0°)", "Left (90°)", "Down (180°)", "Right (270°)"
            try:
                if "Left" in value: angle = 90
                elif "Down" in value: angle = 180
                elif "Right" in value: angle = 270
                else: angle = 0 # Default to Up (0)
                
                logger.info(f"UI: Applying rotation {angle} to element {self.selected_element_id}")
                self.designer.update_element_rotation(self.selected_element_id, angle)
                self.update_preview()
            except Exception as e:
                logger.error(f"Rotation parsing error: {e}")
        else:
            logger.warning("UI: Rotation changed but no element selected")

    def on_font_change(self, value):
        if self.selected_element_id:
            self.designer.update_element_font(self.selected_element_id, value)
            self.update_preview()

    def on_text_content_change(self, event=None):
        if self.selected_element_id:
            new_text = self.entry_edit_text.get()
            self.designer.update_element_content(self.selected_element_id, new_text)
            self.update_preview()
            self.update_layer_list() # Name might change

    def on_fontsize_change(self, value):
        if self.selected_element_id:
            self.designer.update_element_font_size(self.selected_element_id, value)
            self.update_preview()

    def add_text_to_label(self):
        text = self.entry_text.get()
        if text:
            el = self.designer.add_text(text)
            logger.info(f"UI: Added text: {text}")
            self.update_preview()
            self.update_layer_list()
            self.select_element(el['id'])

    def upload_image(self):
        file_path = ctk.filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.png;*.jpeg")])
        if file_path:
            el = self.designer.add_image(file_path)
            if el:
                logger.info(f"UI: Added image from {file_path}")
                self.update_preview()
                self.update_layer_list()
                self.select_element(el['id'])

    def delete_element(self):
        if self.selected_element_id:
            self.designer.remove_element(self.selected_element_id)
            self.selected_element_id = None
            self.update_preview()
            self.update_layer_list()
            self.update_control_state()

    def clear_label(self):
        self.designer.clear()
        self.selected_element_id = None
        self.update_preview()
        self.update_layer_list()
        self.update_control_state()

    def print_label(self):
        selected_printer = self.printer_var.get()
        if selected_printer == "No Printers Found" or not selected_printer:
            print("No printer selected.")
            logger.warning("UI: Print Attempted (No printer selected)")
            return

        # Disable button to prevent spamming
        self.btn_print.configure(state="disabled", text="Printing...")
        
        try:
            copies = int(self.entry_copies.get())
        except ValueError:
            copies = 1
        
        def run_print():
            try:
                # Use system temp directory to ensure we have write permissions
                # and avoid CWD issues (some environments set CWD to restricted folders)
                import tempfile
                import os
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, "temp_print_label.png")
                
                self.designer.image.save(temp_path)
                
                success = printer_utils.print_image(temp_path, selected_printer, copies=copies)
                if success:
                    print(f"Sent to printer: {selected_printer} ({copies} copies)")
                    logger.info(f"UI: Print Success: {selected_printer} ({copies} copies)")
                else:
                    print("Failed to print.")
                    logger.error("UI: Print Failed")
            except Exception as e:
                print(f"Print Error: {e}")
                logger.error(f"UI: Print Error: {e}", exc_info=True)
            finally:
                # Re-enable button
                self.after(0, lambda: self.btn_print.configure(state="normal", text="Print Label"))

        # Run in threaded mode
        threading.Thread(target=run_print, daemon=True).start()

    def duplicate_element_action(self):
        if self.selected_element_id:
            new_el = self.designer.duplicate_element(self.selected_element_id)
            if new_el:
                self.update_layer_list()
                self.select_element(new_el['id']) # Select the new duplicate
                self.update_preview()
                logger.info(f"UI: Duplicated element {self.selected_element_id} -> {new_el['id']}")

    def save_project_action(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if file_path:
            self.designer.save_project(file_path)
            logger.info(f"UI: Saved project to {file_path}")

    def load_project_action(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if file_path:
            valid = self.designer.load_project(file_path)
            if valid:
                self.selected_element_id = None
                self.update_layer_list()
                self.update_preview()
                self.update_control_state()
                logger.info(f"UI: Loaded project from {file_path}")

if __name__ == "__main__":
    app = LabelApp()
    app.mainloop()
