import inspect
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.label_designer import LabelDesigner
from app import font_manager, printer_utils


def test_app_logic():
    designer = LabelDesigner()

    # Test 1: Add Text with Font Size and Emoji
    el_text = designer.add_text("Chicken Style 🐔", font_size=50)
    assert el_text["font_size"] == 50

    designer.update_element_font_size(el_text["id"], 80)
    assert designer.get_element(el_text["id"])["font_size"] == 80

    # Updating to empty text must not crash rendering
    designer.update_element_content(el_text["id"], "")
    assert designer.get_image().size == (designer.width_px, designer.height_px)

    # Restore text and verify bounds, hit_test, center, layer order, and preview
    designer.update_element_content(el_text["id"], "Test")
    bounds = designer.get_element_bounds(el_text["id"])
    assert bounds is not None and bounds[2] > 0 and bounds[3] > 0
    cx = bounds[0] + bounds[2] // 2
    cy = bounds[1] + bounds[3] // 2
    assert designer.hit_test(cx, cy) == el_text["id"]

    designer.update_element_position(el_text["id"], 0, 0)
    designer.center_element(el_text["id"], horizontal=True, vertical=True)
    centered = designer.get_element(el_text["id"])
    assert centered["x"] == (designer.width_px - bounds[2]) // 2
    assert centered["y"] == (designer.height_px - bounds[3]) // 2

    el_second = designer.add_text("Second")
    assert designer.elements[-1]["id"] == el_second["id"]
    assert designer.move_element_order(el_second["id"], -1) is True
    assert designer.elements[0]["id"] == el_second["id"]

    preview = designer.get_preview_image(el_text["id"])
    assert preview.size == designer.image.size

    # Multiline text & alignment + shapes + snapshot/restore
    multi = designer.add_text("Line 1\nLine 2 Longer", align="center")
    assert multi["align"] == "center"
    designer.update_element_align(multi["id"], "right")
    assert designer.get_element(multi["id"])["align"] == "right"

    box = designer.add_shape("rect", width=100, height=50, stroke_width=3, filled=False)
    line = designer.add_shape("line", width=150, stroke_width=4)
    assert box["type"] == "shape" and line["shape"] == "line"
    snap = designer.snapshot_state()
    designer.update_shape_properties(box["id"], width=120, filled=True)
    assert designer.get_element(box["id"])["width"] == 120
    designer.restore_state(snap)
    assert designer.get_element(box["id"])["width"] == 100
    assert designer.get_element(box["id"])["filled"] is False

    # Test 2: Scale Image with Caching
    sample_img = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "label-sample.jpg")
    if os.path.exists(sample_img):
        el_img = designer.add_image(sample_img)
        assert el_img is not None
        assert "img_object" in el_img

        designer.update_element_scale(el_img["id"], 1.5)
        new_el = designer.get_element(el_img["id"])
        assert new_el["scale"] == 1.5

        # Verify resize corner handle detection & single-render transform
        bx, by, bw, bh = designer.get_element_bounds(el_img["id"])
        assert designer.get_resize_handle_at(el_img["id"], bx + bw, by + bh) == "se"
        assert designer.get_resize_handle_at(el_img["id"], bx, by) == "nw"
        designer.update_image_transform(el_img["id"], 0.8, 10, 15)
        updated_img = designer.get_element(el_img["id"])
        assert updated_img["scale"] == 0.8
        assert updated_img["x"] == 10 and updated_img["y"] == 15
        assert designer.get_preview_image(el_img["id"]).size == designer.image.size

    # Test 3: font_manager catalog and system fonts
    catalog = font_manager.get_font_catalog()
    assert len(catalog) > 0
    assert all(isinstance(name, str) and isinstance(ref, str) for name, ref in catalog)
    assert len(font_manager.get_system_fonts()) == len(catalog)

    # Test 4: print_image signature and mocked printing copies
    sig = inspect.signature(printer_utils.print_image)
    assert "copies" in sig.parameters


def test_print_image_copies_and_cleanup(tmp_path):
    img_path = tmp_path / "label.png"
    designer = LabelDesigner()
    designer.add_text("Print Test")
    designer.save_image(str(img_path))

    mock_dc = MagicMock()
    mock_dc.GetDeviceCaps.side_effect = [406, 247]

    with (
        patch("app.printer_utils.win32print.OpenPrinter", return_value="HANDLE") as mock_open,
        patch("app.printer_utils.win32print.ClosePrinter") as mock_close,
        patch("app.printer_utils.win32ui.CreateDC", return_value=mock_dc),
        patch("app.printer_utils.ImageWin.Dib") as mock_dib,
    ):
        ok = printer_utils.print_image(str(img_path), "DummyPrinter", copies=3)

    assert ok is True
    mock_open.assert_called_once_with("DummyPrinter")
    mock_dc.CreatePrinterDC.assert_called_once_with("DummyPrinter")
    mock_dc.StartDoc.assert_called_once()
    assert mock_dc.StartPage.call_count == 3
    assert mock_dc.EndPage.call_count == 3
    assert mock_dib.return_value.draw.call_count == 3
    mock_dc.EndDoc.assert_called_once()
    mock_dc.DeleteDC.assert_called_once()
    mock_close.assert_called_once_with("HANDLE")


if __name__ == "__main__":
    test_app_logic()
    print("Verification Complete.")
