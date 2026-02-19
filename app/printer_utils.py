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
    logger.info(f"Attempting to print '{image_path}' to '{printer_name}' with {copies} copies.")
    try:
        # Open Printer
        hPrinter = win32print.OpenPrinter(printer_name)
        try:
            # Create Device Context
            hDC = win32ui.CreateDC()
            hDC.CreatePrinterDC(printer_name)

            img = Image.open(image_path)
            logger.debug(f"Image loaded. Size: {img.size}")
            
            # Loop for copies
            for i in range(copies):
                hDC.StartDoc(f"Label Print Job {i+1}")
                hDC.StartPage()

                # Get printable area
                printable_area = hDC.GetDeviceCaps(win32con.HORZRES), hDC.GetDeviceCaps(win32con.VERTRES)
                printer_size = printable_area
                
                # Draw image (scale to fit if necessary, or 1:1)
                # For label printers, we usually want 1:1 mapping if DPI matches, 
                # or scale to page if we treat the page as the label.
                # Here we simply draw it to the DC. PIL ImageWin makes this easy.
                
                dib = ImageWin.Dib(img)
                dib.draw(hDC.GetHandleOutput(), (0, 0, printer_size[0], printer_size[1]))

                hDC.EndPage()
                hDC.EndDoc()
                
            hDC.DeleteDC()
            logger.info("Print job sent successfully.")
            return True
        finally:
            win32print.ClosePrinter(hPrinter)
            
    except Exception as e:
        logger.error(f"Error printing: {e}", exc_info=True)
        return False
