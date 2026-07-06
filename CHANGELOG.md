# Changelog

## [0.1.0] - Refactoring release

This release introduces a clean, modular Python project structure, replacing the legacy monolithic script while retaining 100% behavioral compatibility.

### Added
- **Modular structure**: Separated logic into discrete responsibilities across `config`, `proxy`, `idle_monitor`, `crafty_client`, `crafty_process`, and `messages` modules.
- **TOML Config file**: Added support for standard `config.toml` config representation.
- **Comprehensive tests**: Added a `pytest` test suite that covers configuration, messaging templates, Crafty log filtering, socket parsing and mocked state transitions without requiring a real network setup.
- **Structured Logging**: Optional JSON-format logging output.

### Changed
- **SIGHUP Reload**: The hot-reloading feature using `SIGHUP` is now supported exclusively via the `config.toml` file. It no longer shells out to a bash script. If using environment variables purely, SIGHUP does not trigger a reload.
- Config keys remain the same to ease transition, but fallback resolution specifies that Environment Variables > `config.toml`.
- **Legacy Note**: The original script has been moved to `legacy/gateway.py`.
