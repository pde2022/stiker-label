import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.label_designer import LabelDesigner


def test_rotation(tmp_path=None):
    designer = LabelDesigner()

    txt = designer.add_text("TEST ROTATION")
    assert txt.get("rotation") == 0

    for angle in (90, 180, 270, 0):
        designer.update_element_rotation(txt["id"], angle)
        el = designer.get_element(txt["id"])
        assert el.get("rotation") == angle

    if tmp_path is None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = os.path.join(tmp_dir, "rotated.png")
            designer.save_image(out_path)
            assert os.path.exists(out_path)
    else:
        out_path = str(tmp_path / "rotated.png")
        designer.save_image(out_path)
        assert os.path.exists(out_path)


if __name__ == "__main__":
    test_rotation()
    print("Rotation tests passed!")
