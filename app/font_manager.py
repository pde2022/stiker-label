import glob
import os
import re

try:
    import winreg
except ImportError:
    winreg = None


WINDOWS_FONTS_DIR = r"C:\Windows\Fonts"


def _clean_font_display_name(raw_name):
    """Strips registry type suffixes such as '(TrueType)' from a font name."""
    cleaned = re.sub(r"\s*\((TrueType|OpenType|All res)\)\s*$", "", raw_name, flags=re.IGNORECASE)
    return cleaned.strip()


def get_font_catalog():
    """
    Returns a sorted list of (display_name, font_ref) tuples for installed TTF/OTF fonts.
    Reads human-friendly names from the Windows Registry when available and falls back
    to scanning C:\\Windows\\Fonts.
    """
    catalog = []
    seen_names = set()
    seen_refs = set()

    if winreg is not None:
        reg_locations = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"),
        ]
        for hive, subkey in reg_locations:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    idx = 0
                    while True:
                        try:
                            raw_name, value, _ = winreg.EnumValue(key, idx)
                            idx += 1
                            if not isinstance(value, str):
                                continue
                            ext = os.path.splitext(value)[1].lower()
                            if ext not in (".ttf", ".otf"):
                                continue
                            full_path = value if os.path.isabs(value) else os.path.join(WINDOWS_FONTS_DIR, value)
                            if not os.path.exists(full_path):
                                continue

                            display_name = _clean_font_display_name(raw_name)
                            font_ref = value if os.path.isabs(value) else os.path.basename(value)
                            if display_name.lower() not in seen_names and font_ref.lower() not in seen_refs:
                                seen_names.add(display_name.lower())
                                seen_refs.add(font_ref.lower())
                                catalog.append((display_name, font_ref))
                        except OSError:
                            break
            except OSError:
                continue

    if not catalog:
        try:
            all_fonts = []
            for pattern in ("*.ttf", "*.otf"):
                all_fonts.extend(glob.glob(os.path.join(WINDOWS_FONTS_DIR, pattern)))
            for path in all_fonts:
                filename = os.path.basename(path)
                if filename.lower() not in seen_refs:
                    seen_refs.add(filename.lower())
                    display_name = os.path.splitext(filename)[0]
                    catalog.append((display_name, filename))
        except Exception as e:
            print(f"Error scanning fonts: {e}")

    catalog.sort(key=lambda item: item[0].lower())
    return catalog


def get_system_fonts():
    """Returns a sorted list of available system font references (filenames or paths)."""
    return [font_ref for _, font_ref in get_font_catalog()]
