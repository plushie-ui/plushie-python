# Standalone Executables

This guide covers bundling a plushie application into a standalone
executable that users can run without installing Python.

All approaches require the plushie renderer binary to be bundled
alongside the Python application. Download it first:

```sh
python -m plushie download
```

The binary location is printed on success. You can also find it at:
- Linux/macOS: `~/.local/share/plushie/bin/plushie-{os}-{arch}`
- Windows: `%LOCALAPPDATA%\plushie\bin\plushie-windows-x86_64.exe`


## PyInstaller (recommended)

PyInstaller is the most straightforward option. Use `--add-binary`
to bundle the plushie renderer alongside the executable.

```sh
pip install pyinstaller

pyinstaller --onefile \
    --add-binary "$HOME/.local/share/plushie/bin/plushie-linux-x86_64:." \
    myapp.py
```

At runtime, PyInstaller extracts bundled files to a temporary
directory stored in `sys._MEIPASS`. The plushie SDK checks this
location automatically during binary resolution -- no configuration
needed.

If you need explicit control, set the environment variable:

```python
import sys
import os

if hasattr(sys, "_MEIPASS"):
    os.environ["PLUSHIE_BINARY_PATH"] = os.path.join(
        sys._MEIPASS, "plushie-linux-x86_64"
    )
```

### macOS .app bundle

```sh
pyinstaller --windowed --onedir \
    --add-binary "path/to/plushie-darwin-aarch64:." \
    --name MyApp \
    myapp.py
```

### Windows .exe

```sh
pyinstaller --onefile ^
    --add-binary "path\to\plushie-windows-x86_64.exe;." ^
    myapp.py
```

Note: Windows uses `;` instead of `:` as the path separator in
`--add-binary`.


## Nuitka (advanced)

Nuitka compiles Python to C and produces faster executables. Use
`--include-data-files` to bundle the renderer.

```sh
pip install nuitka

python -m nuitka \
    --standalone \
    --include-data-files="path/to/plushie-linux-x86_64=plushie" \
    myapp.py
```

Nuitka places data files relative to the compiled binary. The SDK
checks adjacent to `__file__` and `sys.executable` automatically.

For onefile mode:

```sh
python -m nuitka \
    --onefile \
    --include-data-files="path/to/plushie-linux-x86_64=plushie" \
    myapp.py
```


## Briefcase (native packages)

Briefcase produces native application packages (.app, .msi,
AppImage, .deb) using platform packaging conventions.

```sh
pip install briefcase
briefcase new
```

Add the plushie binary as a resource in `pyproject.toml`:

```toml
[tool.briefcase.app.myapp]
sources = ["src/myapp"]
resources = ["resources"]
```

Place the plushie binary in `resources/` and reference it at
runtime:

```python
from importlib.resources import files

binary_path = str(files("myapp").joinpath("resources", "plushie-linux-x86_64"))
os.environ["PLUSHIE_BINARY_PATH"] = binary_path
```

Or let the SDK auto-detect it by placing the binary adjacent to
the package directory.

### Platform-specific builds

```sh
briefcase build linux appimage   # Linux AppImage
briefcase build macOS app        # macOS .app
briefcase build windows          # Windows .msi
```


## Resolution order

The SDK resolves the plushie binary in this order:

1. `PLUSHIE_BINARY_PATH` environment variable (fail-fast)
2. Custom extension build in `build/*/target/`
3. Downloaded binary in the standard location
4. Bundled binary (PyInstaller `sys._MEIPASS`, adjacent to
   `__file__`, adjacent to `sys.executable`)
5. `plushie` on system PATH

For most bundling tools, step 4 handles resolution automatically.
Set `PLUSHIE_BINARY_PATH` explicitly if automatic resolution does
not find the binary in your specific packaging setup.


## WASM renderer

For web-based deployment, bundle the WASM renderer instead:

```sh
python -m plushie download --wasm
```

This downloads `plushie_wasm.js` and `plushie_wasm_bg.wasm` to
the standard WASM directory. See `plushie.binary.resolve_wasm()`
for programmatic resolution.
