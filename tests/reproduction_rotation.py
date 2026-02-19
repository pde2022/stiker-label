from label_designer import LabelDesigner
import logging_config
import os

logging_config.setup_logging()

def test_rotation():
    print("Testing Rotation Logic...")
    designer = LabelDesigner()
    
    # 1. Add Text
    txt = designer.add_text("TEST ROTATION")
    print(f"Added text id: {txt['id']}, Initial Rotation: {txt.get('rotation')}")
    designer.save_image("debug_step1_initial.png")
    
    # 2. Rotate 90
    print("Rotating 90 degrees...")
    designer.update_element_rotation(txt['id'], 90)
    
    # Verify internal state
    el = designer.get_element(txt['id'])
    print(f"Post-update Rotation: {el.get('rotation')}")
    
    # Save Image
    designer.save_image("debug_step2_rotated_90.png")
    print("Saved debug_step2_rotated_90.png")
    
    # 3. Rotate 180
    print("Rotating 180 degrees...")
    designer.update_element_rotation(txt['id'], 180)
    designer.save_image("debug_step3_rotated_180.png")
    
if __name__ == "__main__":
    try:
        test_rotation()
    except Exception as e:
        import traceback
        traceback.print_exc()
