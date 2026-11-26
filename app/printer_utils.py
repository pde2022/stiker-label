import win32print
import win32ui
import win32con
from PIL import Image, ImageWin
import logging

logger = logging.getLogger(__name__)

def list_printers():
    """Returns a list of available printers."""
    try:
        printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
        printer_names = [p[2] for p in printers]
        logger.debug(f"Available printers: {printer_names}")
        return printer_names
    except Exception as e:
        logger.error(f"Failed to list printers: {e}", exc_info=True)
        return []

def print_image(image_path, printer_name, copies=1):
    """Prints the image to the specified printer."""
    copies = max(1, int(copies))
    logger.info(f"Attempting to print '{image_path}' to '{printer_name}' with {copies} copies.")
    hPrinter = None
    hDC = None
    try:
        # Open Printer
        hPrinter = win32print.OpenPrinter(printer_name)
        # Create Device Context
        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(printer_name)

        img = Image.open(image_path)
        logger.debug(f"Image loaded. Size: {img.size}")

        # Get printable area
        printable_area = hDC.GetDeviceCaps(win32con.HORZRES), hDC.GetDeviceCaps(win32con.VERTRES)
        printer_size = printable_area

        dib = ImageWin.Dib(img)
        hDC.StartDoc("Label Print Job")
        try:
            for _ in range(copies):
                hDC.StartPage()
                dib.draw(hDC.GetHandleOutput(), (0, 0, printer_size[0], printer_size[1]))
                hDC.EndPage()
        finally:
            hDC.EndDoc()

        logger.info("Print job sent successfully.")
        return True
    except Exception as e:
        logger.error(f"Error printing: {e}", exc_info=True)
        return False
    finally:
        if hDC is not None:
            try:
                hDC.DeleteDC()
            except Exception:
                pass
        if hPrinter is not None:
            try:
                win32print.ClosePrinter(hPrinter)
            except Exception:
                pass
