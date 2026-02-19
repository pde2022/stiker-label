from PIL import Image, ImageDraw, ImageFont
import os
import logging
import json

logger = logging.getLogger(__name__)

class LabelDesigner:
    def __init__(self, width_mm=50.8, height_mm=31, dpi=203):
        self.width_mm = width_mm
        self.height_mm = height_mm
        self.dpi = dpi
        self.width_px = int(self.width_mm * (self.dpi / 25.4))
        self.height_px = int(self.height_mm * (self.dpi / 25.4))
        
        self.elements = []
        self.next_id = 1
        self.render()
        logger.info(f"LabelDesigner initialized. Dimensions: {self.width_px}x{self.height_px} px")

    def render(self):
        """Re-draws all elements onto the canvas."""
        self.image = Image.new("RGB", (self.width_px, self.height_px), "white")
        self.draw = ImageDraw.Draw(self.image)
        
        for el in self.elements:
            try:
                # Common rotation
                rotation = el.get('rotation', 0)

                if el['type'] == 'text':
                    try:
                        font_name = el.get('font', 'arial.ttf')
                        font = ImageFont.truetype(font_name, el['font_size'])
                    except IOError:
                        font = ImageFont.load_default()
                    
                    # Create mask image for text
                    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))
                    bbox = dummy_draw.textbbox((0, 0), el['content'], font=font)
                    text_w = bbox[2] - bbox[0]
                    text_h = bbox[3] - bbox[1]
                    
                    # Create RGBA image to hold text
                    # Use exact bounding box dimensions (bbox[1] can be negative, so we must shift by -bbox[1])
                    txt_img = Image.new("RGBA", (text_w, text_h), (255, 255, 255, 0))
                    d = ImageDraw.Draw(txt_img)
                    # Draw text in black, shifted so top-left of ink is at (0,0)
                    d.text((-bbox[0], -bbox[1]), el['content'], fill="black", font=font)
                    
                    # Rotate
                    if rotation != 0:
                        txt_img = txt_img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
                    
                    # Paste using alpha channel as mask
                    self.image.paste(txt_img, (el['x'], el['y']), txt_img)
                
                elif el['type'] == 'image':
                    # Use cached image object if available, otherwise load (shouldn't happen if added correctly)
                    if 'img_object' in el:
                        img = el['img_object'].copy()
                    else:
                        img = Image.open(el['path']).convert("RGBA")
                        el['img_object'] = img.copy() # Cache it
                    
                    # Apply scaling
                    scale = el.get('scale', 1.0)
                    
                    # Base resize (fit to label height logic from before)
                    if 'base_width' not in el or 'base_height' not in el:
                        # Calculate base dimensions if not stored
                        img_ratio = img.width / img.height
                        target_h = self.height_px
                        target_w = int(target_h * img_ratio)
                        if target_w > self.width_px:
                            target_w = self.width_px
                            target_h = int(target_w / img_ratio)
                        el['base_width'] = target_w
                        el['base_height'] = target_h

                    final_w = int(el['base_width'] * scale)
                    final_h = int(el['base_height'] * scale)
                    
                    if final_w > 0 and final_h > 0:
                        img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
                        
                        # Rotate
                        if rotation != 0:
                            img = img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)

                        # Paste with mask for transparency
                        self.image.paste(img, (el['x'], el['y']), img)
            except Exception as e:
                logger.error(f"Error rendering element {el.get('id', '?')}: {e}", exc_info=True)

    def add_text(self, text, font_size=30, font_name="arial.ttf"):
        """Adds a new text element."""
        try:
             font = ImageFont.truetype(font_name, font_size)
        except:
             font = ImageFont.load_default()
             
        dummy_draw = ImageDraw.Draw(Image.new("RGB", (1,1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        
        x = (self.width_px - w) // 2
        y = (self.height_px - h) // 2
        
        element = {
            'id': self.next_id,
            'type': 'text',
            'content': text,
            'x': x,
            'y': y,
            'font_size': font_size,
            'font': font_name,
            'rotation': 0,
            'name': f"Text {self.next_id}: {text[:10]}..."
        }
        self.elements.append(element)
        self.next_id += 1
        self.render()
        logger.info(f"Added text element: {text}")
        return element
        
    def add_image(self, image_path):
        """Adds a new image element."""
        try:
            # Load and cache immediately
            img_head = Image.open(image_path).convert("RGBA")
            
            img_ratio = img_head.width / img_head.height
            target_h = self.height_px
            target_w = int(target_h * img_ratio)
            
            if target_w > self.width_px:
                target_w = self.width_px
                target_h = int(target_w / img_ratio)
            
            x = (self.width_px - target_w) // 2
            y = (self.height_px - target_h) // 2
            
            element = {
                'id': self.next_id,
                'type': 'image',
                'path': image_path,
                'img_object': img_head, # CACHED HERE
                'x': x,
                'y': y,
                'base_width': target_w,
                'base_height': target_h,
                'scale': 1.0,
                'rotation': 0,
                'name': f"Image {self.next_id}"
            }
            self.elements.append(element)
            self.next_id += 1
            self.render()
            logger.info(f"Added image element from: {image_path}")
            return element
        except Exception as e:
            logger.error(f"Error loading image: {e}", exc_info=True)
            return None

    def update_element_position(self, element_id, x, y):
        for el in self.elements:
            if el['id'] == element_id:
                el['x'] = int(x)
                el['y'] = int(y)
                break
        self.render()
        
    def update_element_scale(self, element_id, scale):
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'image':
                el['scale'] = float(scale)
                break
        self.render()

    def update_element_rotation(self, element_id, rotation):
        for el in self.elements:
            if el['id'] == element_id:
                el['rotation'] = int(rotation)
                break
        self.render()

    def update_element_content(self, element_id, new_content):
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'text':
                el['content'] = new_content
                # Update name for layer list
                el['name'] = f"Text {el['id']}: {new_content[:10]}..."
                break
        self.render()

    def update_element_font(self, element_id, font_name):
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'text':
                el['font'] = font_name
                break
        self.render()
        
    def update_element_font_size(self, element_id, font_size):
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'text':
                el['font_size'] = int(font_size)
                break
        self.render()

    def get_element(self, element_id):
        for el in self.elements:
            if el['id'] == element_id:
                return el
        return None

    def remove_element(self, element_id):
        self.elements = [el for el in self.elements if el['id'] != element_id]
        self.render()
        logger.info(f"Removed element {element_id}")

    def clear(self):
        self.elements = []
        self.render()
        logger.info("Cleared all elements")

    def save_image(self, path):
        self.image.save(path)
        logger.info(f"Saved image to {path}")

    def get_image(self):
        return self.image
    
    # Deprecated methods for compatibility
    def duplicate_element(self, element_id):
        """Duplicates an existing element."""
        original = self.get_element(element_id)
        if not original:
            return None
        
        # Create deep copy manually to avoid issues with non-serializable objects if any
        new_el = original.copy()
        new_el['id'] = self.next_id
        self.next_id += 1
        
        # Offset position
        new_el['x'] += 20
        new_el['y'] += 20
        
        # Update name
        if new_el['type'] == 'text':
             new_el['name'] = f"Text {new_el['id']}: {new_el['content'][:10]}..."
        elif new_el['type'] == 'image':
             new_el['name'] = f"Image {new_el['id']}"
             # Ensure image object is copied if it exists
             if 'img_object' in new_el:
                 new_el['img_object'] = original['img_object'].copy()

        self.elements.append(new_el)
        self.render()
        logger.info(f"Duplicated element {element_id} -> {new_el['id']}")
        return new_el

    def save_project(self, file_path):
        """Saves current elements to a JSON file."""
        try:
            # Prepare serializable list
            serialized_elements = []
            for el in self.elements:
                el_copy = el.copy()
                # Remove non-serializable image objects
                if 'img_object' in el_copy:
                    del el_copy['img_object']
                serialized_elements.append(el_copy)
            
            data = {
                'width_mm': self.width_mm,
                'height_mm': self.height_mm,
                'elements': serialized_elements,
                'next_id': self.next_id
            }
            
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            logger.info(f"Project saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False

    def load_project(self, file_path):
        """Loads elements from a JSON file."""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Clear current
            self.elements = []
            self.next_id = data.get('next_id', 1)
            
            # Reconstruct elements
            for el_data in data.get('elements', []):
                # Reload images
                if el_data['type'] == 'image':
                    try:
                        img_path = el_data.get('path')
                        if img_path and os.path.exists(img_path):
                            img = Image.open(img_path).convert("RGBA")
                            el_data['img_object'] = img # Cache it
                        else:
                            logger.warning(f"Image not found at {img_path}, skipping image load for element {el_data['id']}")
                            # We keep the element data but it won't render the image
                    except Exception as e:
                        logger.error(f"Error reloading image for element {el_data['id']}: {e}")

                self.elements.append(el_data)
                
            self.render()
            logger.info(f"Project loaded from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return False

    def load_image(self, path):
        return self.add_image(path)
