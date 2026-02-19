import os
import glob
from PIL import ImageFont

def get_system_fonts():
    """
    Returns a list of available system fonts (TTF/OTF).
    Focuses on standard Windows font directory.
    Differs by returns a list of dictionaries: {'name': 'Arial', 'path': '...'} or just names if standard.
    For simplicity, we return a list of paths or names that PIL can load.
    """
    font_dir = r"C:\Windows\Fonts"
    fonts = []
    
    # Common useful fonts to prioritize
    priority_fonts = ["arial.ttf", "calibri.ttf", "seguisym.ttf", "seguiemj.ttf", "times.ttf", "verdana.ttf", "tahoma.ttf"]
    
    # Check priority fonts first
    for f in priority_fonts:
        path = os.path.join(font_dir, f)
        if os.path.exists(path):
            fonts.append(f) # Just filename is often enough for PIL on Windows if installed
    
    # Scan for others (limit to avoid overwhelmed UI)
    try:
        all_ttfs = glob.glob(os.path.join(font_dir, "*.ttf"))
        for path in all_ttfs[:50]: # Limit to 50 for performance
            filename = os.path.basename(path)
            if filename not in fonts:
                fonts.append(filename)
    except Exception as e:
        print(f"Error scanning fonts: {e}")
        
    return sorted(fonts)
