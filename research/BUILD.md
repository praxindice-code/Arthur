# Building the earlier research prototype

Work from this `research/` directory. Python 3.10+ runs the offline experiments and tests with no packages to install:

```powershell
python -m unittest discover -s tests -q
python -m bayesguard demo
python -m pilot.analyze pilot/example-output.log
```

The Rust and Zig paths are **optional experiments**, not part of the current Roblox pilot. For a native rebuild on Windows, install a Rust toolchain and Zig 0.14.1 for your PC's architecture, then run:

```powershell
cargo test --manifest-path rust-detector/Cargo.toml
zig test zig-normalizer/window.zig
New-Item -ItemType Directory -Force bin | Out-Null
zig build-exe zig-normalizer/main.zig -O ReleaseSafe -femit-bin=bin/normalizer.exe
cargo build --release --manifest-path rust-detector/Cargo.toml
Copy-Item rust-detector/target/release/bayesguard-detector.exe bin/
Copy-Item rust-detector/target/release/live.exe bin/bayesguard-live.exe
python -m unittest discover -s tests -q
```

This builds the Rust live service with its built-in feature counter. To link the Zig `window.zig` counter into Rust instead, compile `window.zig` to an object and build Cargo with `--features zig-window` and that object as a linker argument. The preserved `build-native.ps1` documents the original ARM64 workspace's linker workaround; its toolchain paths are **not portable** and should not be run unchanged on a different PC. Some GNU Rust targets also require their runtime DLL beside the executable.

The `bayesguard run` command and native-parity tests require `bin/normalizer.exe` and `bin/bayesguard-detector.exe`. Without those binaries, the Python-only tests still run, and the checked-in HTML viewers remain viewable offline. None of these synthetic experiments verifies cheat detection on real players.
