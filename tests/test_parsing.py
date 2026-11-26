from app.main import LabelApp


def test_parsing():
    assert LabelApp.parse_rotation("Up (0°)") == 0
    assert LabelApp.parse_rotation("Left (90°)") == 90
    assert LabelApp.parse_rotation("Down (180°)") == 180
    assert LabelApp.parse_rotation("Right (270°)") == 270
    assert LabelApp.parse_rotation("0°") == 0
    assert LabelApp.parse_rotation("90°") == 90
    assert LabelApp.parse_rotation("180°") == 180
    assert LabelApp.parse_rotation("270°") == 270
    assert LabelApp.parse_rotation("Unknown") == 0


if __name__ == "__main__":
    test_parsing()
    print("All parsing tests passed!")
