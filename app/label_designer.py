from PIL import Image, ImageDraw, ImageFont
import math
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

    def _render_element_image(self, el):
        """Renders a single element into an RGBA image (with rotation applied)."""
        rotation = el.get('rotation', 0)

        if el['type'] == 'text':
            content = el.get('content', '')
            if not content:
                return None

            try:
                font_name = el.get('font', 'arial.ttf')
                font = ImageFont.truetype(font_name, el['font_size'])
            except IOError:
                font = ImageFont.load_default()

            align = el.get('align', 'left')
            dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            bbox = dummy_draw.multiline_textbbox((0, 0), content, font=font, align=align)
            text_w = int(math.ceil(bbox[2] - bbox[0]))
            text_h = int(math.ceil(bbox[3] - bbox[1]))
            if text_w <= 0 or text_h <= 0:
                return None

            txt_img = Image.new("RGBA", (text_w, text_h), (255, 255, 255, 0))
            d = ImageDraw.Draw(txt_img)
            d.multiline_text((-bbox[0], -bbox[1]), content, fill="black", font=font, align=align)

            if rotation != 0:
                txt_img = txt_img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
            return txt_img

        if el['type'] == 'shape':
            shape_kind = el.get('shape', 'rect')
            w = max(2, int(el.get('width', 120)))
            stroke = max(1, int(el.get('stroke_width', 3)))
            if shape_kind == 'line':
                h = max(2, int(el.get('height', stroke)))
            else:
                h = max(2, int(el.get('height', 60)))

            shp_img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            d = ImageDraw.Draw(shp_img)
            if shape_kind == 'line':
                d.rectangle((0, 0, w - 1, h - 1), fill="black")
            else:
                fill_color = "black" if el.get('filled', False) else None
                d.rectangle((0, 0, w - 1, h - 1), fill=fill_color, outline="black", width=stroke)

            if rotation != 0:
                shp_img = shp_img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
            return shp_img

        if el['type'] == 'image':
            if 'img_object' in el:
                img = el['img_object'].copy()
            else:
                img = Image.open(el['path']).convert("RGBA")
                el['img_object'] = img.copy()

            scale = el.get('scale', 1.0)
            if 'base_width' not in el or 'base_height' not in el:
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
            if final_w <= 0 or final_h <= 0:
                return None

            img = img.resize((final_w, final_h), Image.Resampling.LANCZOS)
            if rotation != 0:
                img = img.rotate(rotation, expand=True, resample=Image.Resampling.BICUBIC)
            return img

        return None

    def render(self):
        """Re-draws all elements onto the canvas."""
        self.image = Image.new("RGB", (self.width_px, self.height_px), "white")
        self.draw = ImageDraw.Draw(self.image)

        for el in self.elements:
            try:
                el_img = self._render_element_image(el)
                if el_img is not None:
                    self.image.paste(el_img, (el['x'], el['y']), el_img)
            except Exception as e:
                logger.error(f"Error rendering element {el.get('id', '?')}: {e}", exc_info=True)

    @staticmethod
    def _make_text_name(element_id, text):
        single_line = " ".join(str(text).splitlines()).strip()
        preview = single_line[:12] + ("..." if len(single_line) > 12 else "")
        return f"Text {element_id}: {preview}"

    def add_text(self, text, font_size=30, font_name="arial.ttf", align="left"):
        """Adds a new text element (supports multi-line text and alignment)."""
        try:
            font = ImageFont.truetype(font_name, font_size)
        except Exception:
            font = ImageFont.load_default()

        dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bbox = dummy_draw.multiline_textbbox((0, 0), text, font=font, align=align)
        w = int(math.ceil(bbox[2] - bbox[0]))
        h = int(math.ceil(bbox[3] - bbox[1]))

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
            'align': align,
            'rotation': 0,
            'name': self._make_text_name(self.next_id, text),
        }
        self.elements.append(element)
        self.next_id += 1
        self.render()
        logger.info(f"Added text element: {text}")
        return element

    def add_shape(self, shape_kind="rect", width=None, height=None, stroke_width=3, filled=False):
        """Adds a rectangle ('rect') or line ('line') shape element."""
        if shape_kind == "line":
            w = int(width) if width is not None else min(240, self.width_px - 40)
            stroke = max(1, int(stroke_width))
            h = int(height) if height is not None else stroke
            label = f"Line {self.next_id}"
            is_filled = True
        else:
            shape_kind = "rect"
            w = int(width) if width is not None else min(180, self.width_px - 40)
            h = int(height) if height is not None else min(90, self.height_px - 40)
            stroke = max(1, int(stroke_width))
            label = f"Box {self.next_id}"
            is_filled = bool(filled)

        x = (self.width_px - w) // 2
        y = (self.height_px - h) // 2

        element = {
            'id': self.next_id,
            'type': 'shape',
            'shape': shape_kind,
            'x': x,
            'y': y,
            'width': w,
            'height': h,
            'stroke_width': stroke,
            'filled': is_filled,
            'rotation': 0,
            'name': label,
        }
        self.elements.append(element)
        self.next_id += 1
        self.render()
        logger.info(f"Added shape element: {shape_kind}")
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

    def update_image_transform(self, element_id, scale, x=None, y=None):
        """Updates an image element's scale and optional position in a single render."""
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'image':
                el['scale'] = float(scale)
                if x is not None:
                    el['x'] = int(x)
                if y is not None:
                    el['y'] = int(y)
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
                el['name'] = self._make_text_name(el['id'], new_content)
                break
        self.render()

    def update_element_align(self, element_id, align):
        if align not in ('left', 'center', 'right'):
            return
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'text':
                el['align'] = align
                break
        self.render()

    def update_shape_properties(self, element_id, width=None, height=None, stroke_width=None, filled=None, x=None, y=None):
        """Updates properties of a shape element in a single render."""
        for el in self.elements:
            if el['id'] == element_id and el['type'] == 'shape':
                if width is not None:
                    el['width'] = max(2, int(width))
                if stroke_width is not None:
                    el['stroke_width'] = max(1, int(stroke_width))
                    if el.get('shape') == 'line' and height is None:
                        el['height'] = el['stroke_width']
                if height is not None:
                    el['height'] = max(2, int(height))
                if filled is not None:
                    el['filled'] = bool(filled)
                if x is not None:
                    el['x'] = int(x)
                if y is not None:
                    el['y'] = int(y)
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

    def get_element_bounds(self, element_id):
        """Returns (x, y, width, height) for the rendered element, or None."""
        el = self.get_element(element_id)
        if not el:
            return None
        try:
            el_img = self._render_element_image(el)
            if el_img is None:
                return (el['x'], el['y'], 0, 0)
            return (el['x'], el['y'], el_img.width, el_img.height)
        except Exception:
            return None

    def hit_test(self, x, y):
        """Returns the topmost element ID at canvas coordinates (x, y), or None."""
        for el in reversed(self.elements):
            bounds = self.get_element_bounds(el['id'])
            if not bounds:
                continue
            bx, by, bw, bh = bounds
            if bw > 0 and bh > 0 and bx <= x <= bx + bw and by <= y <= by + bh:
                return el['id']
        return None

    def center_element(self, element_id, horizontal=True, vertical=True):
        """Centers an element horizontally and/or vertically on the canvas."""
        bounds = self.get_element_bounds(element_id)
        if not bounds:
            return
        el = self.get_element(element_id)
        _, _, bw, bh = bounds
        if horizontal:
            el['x'] = (self.width_px - bw) // 2
        if vertical:
            el['y'] = (self.height_px - bh) // 2
        self.render()

    def move_element_order(self, element_id, direction):
        """Moves an element up (+1, forward) or down (-1, backward) in z-order."""
        idx = next((i for i, el in enumerate(self.elements) if el['id'] == element_id), None)
        if idx is None:
            return False
        new_idx = idx + direction
        if 0 <= new_idx < len(self.elements):
            self.elements[idx], self.elements[new_idx] = self.elements[new_idx], self.elements[idx]
            self.render()
            return True
        return False

    def get_resize_handle_at(self, element_id, x, y, tolerance=8):
        """Returns corner handle name ('nw', 'ne', 'sw', 'se') for an image or shape element, or None."""
        el = self.get_element(element_id)
        if not el or el['type'] not in ('image', 'shape'):
            return None
        bounds = self.get_element_bounds(element_id)
        if not bounds:
            return None
        bx, by, bw, bh = bounds
        if bw <= 0 or bh <= 0:
            return None
        corners = {
            'nw': (bx, by),
            'ne': (bx + bw, by),
            'sw': (bx, by + bh),
            'se': (bx + bw, by + bh),
        }
        best_handle = None
        best_dist = tolerance + 1
        for name, (hx, hy) in corners.items():
            dist = max(abs(x - hx), abs(y - hy))
            if dist <= tolerance and dist < best_dist:
                best_dist = dist
                best_handle = name
        return best_handle

    def get_preview_image(self, selected_id=None):
        """Returns a copy of the canvas with an optional selection outline for UI preview."""
        preview = self.image.copy()
        if selected_id is not None:
            el = self.get_element(selected_id)
            bounds = self.get_element_bounds(selected_id)
            if bounds:
                bx, by, bw, bh = bounds
                if bw > 0 and bh > 0:
                    draw = ImageDraw.Draw(preview)
                    x0 = max(0, bx - 2)
                    y0 = max(0, by - 2)
                    x1 = min(self.width_px - 1, bx + bw + 1)
                    y1 = min(self.height_px - 1, by + bh + 1)
                    draw.rectangle((x0, y0, x1, y1), outline="#0067C0", width=2)

                    if el and el['type'] in ('image', 'shape'):
                        r = 4
                        for hx, hy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
                            cx0 = max(0, hx - r)
                            cy0 = max(0, hy - r)
                            cx1 = min(self.width_px - 1, hx + r)
                            cy1 = min(self.height_px - 1, hy + r)
                            draw.rectangle((cx0, cy0, cx1, cy1), fill="#FFFFFF", outline="#0067C0", width=2)
        return preview

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
            new_el['name'] = self._make_text_name(new_el['id'], new_el['content'])
        elif new_el['type'] == 'shape':
            kind = "Box" if new_el.get('shape') == 'rect' else "Line"
            new_el['name'] = f"{kind} {new_el['id']}"
        elif new_el['type'] == 'image':
            new_el['name'] = f"Image {new_el['id']}"
            # Ensure image object is copied if it exists
            if 'img_object' in new_el:
                new_el['img_object'] = original['img_object'].copy()

        self.elements.append(new_el)
        self.render()
        logger.info(f"Duplicated element {element_id} -> {new_el['id']}")
        return new_el

    def snapshot_state(self):
        """Creates a lightweight snapshot of the designer state for Undo/Redo."""
        copied_elements = []
        for el in self.elements:
            el_copy = el.copy()
            # img_object is never mutated in-place, so sharing reference is safe & fast
            copied_elements.append(el_copy)
        return {
            'width_mm': self.width_mm,
            'height_mm': self.height_mm,
            'elements': copied_elements,
            'next_id': self.next_id,
        }

    def restore_state(self, snapshot):
        """Restores designer state from a previously captured snapshot."""
        self.width_mm = float(snapshot['width_mm'])
        self.height_mm = float(snapshot['height_mm'])
        self.width_px = int(self.width_mm * (self.dpi / 25.4))
        self.height_px = int(self.height_mm * (self.dpi / 25.4))
        self.elements = [el.copy() for el in snapshot['elements']]
        self.next_id = int(snapshot['next_id'])
        self.render()

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
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            logger.info(f"Project saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project: {e}")
            return False

    def load_project(self, file_path):
        """Loads elements from a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'width_mm' in data and 'height_mm' in data:
                self.width_mm = float(data['width_mm'])
                self.height_mm = float(data['height_mm'])
                self.width_px = int(self.width_mm * (self.dpi / 25.4))
                self.height_px = int(self.height_mm * (self.dpi / 25.4))

            # Clear current
            self.elements = []
            max_id = 0

            # Reconstruct elements
            for el_data in data.get('elements', []):
                max_id = max(max_id, int(el_data.get('id', 0)))
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

            self.next_id = max(int(data.get('next_id', 1)), max_id + 1)
            self.render()
            logger.info(f"Project loaded from {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load project: {e}")
            return False

    def load_image(self, path):
        return self.add_image(path)
