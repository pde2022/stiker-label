# Label Printer Application

A simple desktop application for designing and printing labels, built with Python (CustomTkinter) and Pillow.

## Features
- **Design Labels**: Add text (with emojis) and images to a 50.8mm x 31mm canvas.
- **Customization**:
    - Change fonts and font sizes.
    - Scale images.
    - **Rotate** elements (`0°`, `90°`, `180°`, `270°`).
    - Drag and drop positioning directly on the canvas, arrow-key nudging, X/Y sliders, and one-click centering.
    - Layer reordering (`↑` / `↓`), zoom presets (`1x`–`2.5x`), and Light/Dark/System Windows 11 theme.
- **Project Management**:
    - **Save** designs to `.json` project files.
    - **Load** existing projects.
    - **Duplicate** elements for quick layout changes.
- **Printing**: Direct printing to installed Windows printers.

## Installation

1.  Clone the repository:
    ```bash
    git clone git@github.com:pde2022/stiker-label.git
    cd stiker-label
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Run the application:
```bash
python run.py
```
Or double-click `run.bat` on Windows to launch without building.

### Building the Executable (Windows)

To create a standalone `.exe` file:
```bash
python build_exe.py
```
The executable will be located in the `dist/` folder.

## License
MIT
