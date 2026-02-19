# Changelog

## [Unreleased]
### Added
- **Project Structure**: Codebase reorganized into `/app` package.
- **Entry Point**: `run.py` added for running the application.

### Changed
- Moved source code files to `/app`.
- Updated build script to use `run.py`.

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
