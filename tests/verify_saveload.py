import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.label_designer import LabelDesigner


def test_save_load_duplicate(tmp_path=None):
    designer = LabelDesigner(width_mm=60.0, height_mm=40.0)

    # 1. Add Element with emoji (verifies UTF-8 save/load on Windows)
    txt = designer.add_text("ORIGINAL 🐔")
    txt_id = txt["id"]

    # 2. Duplicate
    dup = designer.duplicate_element(txt_id)
    assert dup is not None
    assert dup["id"] != txt_id
    assert dup["x"] == txt["x"] + 20
    assert dup["y"] == txt["y"] + 20

    # 3. Save
    if tmp_path is None:
        tmp_dir = tempfile.TemporaryDirectory()
        save_path = os.path.join(tmp_dir.name, "test_project.json")
    else:
        tmp_dir = None
        save_path = str(tmp_path / "test_project.json")

    try:
        assert designer.save_project(save_path) is True

        # 4. Clear and Load into fresh designer
        reloaded = LabelDesigner()
        assert reloaded.load_project(save_path) is True
        assert len(reloaded.elements) == 2
        assert reloaded.elements[0]["content"] == "ORIGINAL 🐔"
        assert reloaded.width_mm == 60.0
        assert reloaded.height_mm == 40.0
        assert reloaded.next_id > dup["id"]
    finally:
        if tmp_dir is not None:
            tmp_dir.cleanup()


if __name__ == "__main__":
    test_save_load_duplicate()
    print("Save/Load/Duplicate tests passed!")
