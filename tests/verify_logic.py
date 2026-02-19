from label_designer import LabelDesigner
import printer_utils
import os

def test_app_logic():
    print("Testing Label Logic...")
    designer = LabelDesigner()
    
    # Test 1: Add Text with Font Size
    print("Adding Text Element with Custom Font Size...")
    el_text = designer.add_text("Chicken Style 🐔", font_size=50)
    print(f"Added Text ID: {el_text['id']} (Size: {el_text['font_size']})")
    
    print("Updating Font Size to 80...")
    designer.update_element_font_size(el_text['id'], 80)
    print(f"New Size: {designer.get_element(el_text['id'])['font_size']}")
    
    # Test 2: Scale Image with Caching
    sample_img = "label-sample.jpg"
    if os.path.exists(sample_img):
        print(f"Loading {sample_img}...")
        el_img = designer.add_image(sample_img)
        
        # Verify caching key
        if 'img_object' in el_img:
            print("Success: Image object cached in memory.")
        else:
            print("Error: Image object NOT cached.")
            
        print("Scaling Image to 1.5x...")
        designer.update_element_scale(el_img['id'], 1.5)
        new_el = designer.get_element(el_img['id'])
        print(f"New Scale: {new_el['scale']}")
    else:
        print(f"Warning: {sample_img} not found, skipping image test.")

    # Test 3: Print Copies (Mock)
    print("Testing Print Copies Logic (Mock)...")
    try:
        # We perform a dummy checking of the printer utility argument
        # Just checking if function exists and signature allows copies
        import inspect
        sig = inspect.signature(printer_utils.print_image)
        if 'copies' in sig.parameters:
            print("Success: print_image accepts 'copies' parameter.")
        else:
            print("Error: print_image missing 'copies' parameter.")
    except Exception as e:
        print(f"Verification Error: {e}")

    print("Verification Complete.")

if __name__ == "__main__":
    test_app_logic()
