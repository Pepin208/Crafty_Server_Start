# Tests for `mc_gateway`

This test suite covers the logic of the `mc_gateway` application without requiring any real network requests, subprocess launches, or actual Minecraft/Crafty setups.

## Running Tests

To run the full suite:

```bash
pytest
```

If you installed the dev dependencies, you should be able to run `pytest` directly, and it should run all files starting with `test_` within this directory.

## Testing Strategy

- **Mocking External Resources**: External API requests (`requests`) and raw socket manipulation (`socket`) are mocked. We use `unittest.mock` for sockets and `responses` to mock HTTP calls to the simulated Crafty server. Subprocesses are mocked out utilizing pytest-mock (`mocker`).
- **Timing and State Machines**: Features such as the idle loop that depend on `time.sleep` are tested by injecting fake sleep functions to rapidly execute state machine transitions and assert outcomes.
- **Config Initialization**: Config parsing ignores external factors by overriding environment variables specifically for a given test context.
