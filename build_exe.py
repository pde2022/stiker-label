import PyInstaller.__main__
import os
import shutil

def build_exe():
    print("Building Executable...")

    # Cleanup previous builds
    if os.path.exists('dist'):
        shutil.rmtree('dist')
    if os.path.exists('build'):
        shutil.rmtree('build')

    # Run PyInstaller
    PyInstaller.__main__.run([
        'run.py',
        '--name=LabelPrinter',
        '--onefile',
        '--windowed',  # No console window
        '--collect-all=customtkinter', # Essential for CustomTkinter themes/icons
        '--hidden-import=PIL',
        '--hidden-import=win32print',
        '--hidden-import=win32ui', 
        '--clean',
        '--noconfirm',
    ])

    print("Build Complete! Check the 'dist' folder.")

if __name__ == "__main__":
    build_exe()
