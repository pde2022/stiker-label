from label_designer import LabelDesigner
import logging_config
import os

logging_config.setup_logging()

def test_features():
    print("Testing Save/Load/Duplicate...")
    designer = LabelDesigner()
    
    # 1. Add Element
    txt = designer.add_text("ORIGINAL")
    txt_id = txt['id']
    print(f"Added text {txt_id}: {txt['content']}")
    
    # 2. Duplicate
    dup = designer.duplicate_element(txt_id)
    if dup:
        print(f"Duplicated {txt_id} -> {dup['id']}")
        assert dup['id'] != txt_id
        assert dup['x'] == txt['x'] + 20
        assert dup['y'] == txt['y'] + 20
    else:
        print("Duplicate failed!")
        return

    # 3. Save
    save_path = "test_project.json"
    if designer.save_project(save_path):
        print(f"Saved to {save_path}")
    else:
        print("Save failed!")
        return
        
    # 4. Clear and Load
    designer.clear()
    print("Cleared elements.")
    assert len(designer.elements) == 0
    
    if designer.load_project(save_path):
        print(f"Loaded from {save_path}")
        assert len(designer.elements) == 2
        print("Elements loaded successfully!")
    else:
        print("Load failed!")
        
    # Cleanup
    if os.path.exists(save_path):
        os.remove(save_path)
        print("Cleaned up test file.")

if __name__ == "__main__":
    try:
        test_features()
    except Exception as e:
        import traceback
        traceback.print_exc()
