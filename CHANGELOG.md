# Changelog

## [2.0.1] - 2026-11-26
### Added
- **Autosave & Draft Recovery**: Automatically saves every change immediately to the active `.json` project (with `250 ms` debounce during live typing/slider motion), or to a recovery draft in `%APPDATA%\LabelPrinterStudio\autosave_draft.json` before the first manual save.
- **Autosave Toggle**: Added `Autosave` checkbutton in the `File` menu and `Autosaved` status indicator in the status bar.

## [2.0.0] - 2026-11-26
### Added
- **Windows 11 Fluent Design UI**: Redesigned 3-panel studio layout (Add/Layers, Interactive Canvas, Properties Inspector) with Light/Dark/System theme switching and native Windows 11 titlebar styling.
- **File Menu & Open Recent**: Unified `File` dropdown menu (`New`, `Open`, `Open Recent` up to 10 persistent projects, `Save`, `Save As`, `Print`, `Exit`) and status bar file location indicator; repeated `Save` overwrites the active file without re-prompting.
- **Interactive Canvas**: Direct mouse drag-and-drop positioning, `Fit` / `1x` / `1.5x` / `2x` zoom presets, `tkinter.Canvas` corner resize handles for images and shapes, and inline multi-line text editing on double-click.
- **Shapes (`Box` & `Line`)**: Add rotatable rectangle borders/filled boxes and lines with adjustable thickness (`1–20 px`) and canvas corner resizing.
- **Multi-line Text & Alignment**: Support multi-line text input/editing and `Left` / `Center` / `Right` text alignment.
- **Snap Guide Lines**: Automatic snapping with visual dashed guide lines to canvas center and other elements while dragging.
- **Undo / Redo & Unsaved Changes Guard**: Up to 50-step Undo/Redo (`Ctrl+Z` / `Ctrl+Y`), dirty state `*` indicator in window title, and save confirmation on `New`, `Open`, `Exit`, or window close.
- **Filterable Font Picker**: Floating Windows 11-styled font picker reading clean font names from the Windows Registry with real-time search filtering and isolated mouse-wheel scrolling.
- **Launcher & Shortcuts**: Added `run.bat` to launch without building, layer z-order controls (`↑`/`↓`), one-click alignment centering, printer refresh, copies stepper, and keyboard shortcuts.
- **Project Structure**: Codebase reorganized into `/app` package with `run.py` entry point.

### Changed
- Moved source code files to `/app` and updated `README.md` to match current features and launch options.
- Consolidated multi-copy printing into a single GDI print document (`StartDoc` with per-copy `StartPage`/`EndPage`) and guarded image snapshots on the UI thread.

### Fixed
- **UTF-8 Support**: Added `encoding="utf-8"` to JSON project save/load and logging handlers for reliable emoji support on Windows.
- **Empty Text & Rotation**: Prevented `0x0` image crash on empty text rendering and unified `parse_rotation` handling.
- **Font Scanning**: Removed arbitrary 50-font limit and added `.otf` font support.
- **Duplicate Logging & Sliders**: Fixed duplicate element ID logging and synced position slider bounds to `LabelDesigner` dimensions.
- **Test Suite**: Fixed broken `app.*` imports across `tests/` and expanded unit tests for rendering, shapes, snapshots, and printing.

## [1.2.0] - 2026-02-19
### Added
- **Save/Load**: Save designs to JSON files and reload them later.
- **Duplicate**: Create copies of selected elements with offset.
- **Text Editing**: Explicit "Update" button to save text changes.
- **Improved UI**: Flattened layer list scrolling for better usability.

### Fixed
- **Rotation**: Fixed bug where "Left (90°)" rotation was ignored due to string parsing error.
- **Scrolling**: Fixed nested scrollbar issue in the left panel.

## [1.1.0] - 2026-02-19
### Added
- **Rotation**: Add rotation controls (Up, Left, Down, Right) for text and images.
- **Logging**: Comprehensive application logging (`app.log`) for debugging.

### Changed
- Replaced slider with dropdown for rotation control.

## [1.0.0] - 2026-02-18
### Added
- Initial release.
- Basic text and image adding.
- Scale and position controls.
- Direct printing support via `win32print`.
