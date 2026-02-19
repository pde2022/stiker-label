def parse_rotation(value):
    print(f"Testing value: '{value}'")
    if "Left" in value: angle = 90
    elif "Down" in value: angle = 180
    elif "Right" in value: angle = 270
    else: angle = 0
    print(f"  -> Result: {angle}")
    return angle

def test_parsing():
    assert parse_rotation("Up (0°)") == 0
    assert parse_rotation("Left (90°)") == 90
    assert parse_rotation("Down (180°)") == 180
    assert parse_rotation("Right (270°)") == 270
    print("All parsing tests passed!")

if __name__ == "__main__":
    test_parsing()
