# Installing & Running 3D SPACE — Cockpit Dogfighter

No accounts, no launchers, no installers. Just Python.

## What you need

- **Python 3.10 or newer** — get it at [python.org/downloads](https://www.python.org/downloads/).
  On Windows, tick **"Add python.exe to PATH"** during installation.
- The **3d-space.zip** file from itch.io.

## Steps

1. **Unzip** `3d-space.zip` anywhere you like. You'll get a `3d-space` folder.
2. **Open a terminal** in that folder.
   - Windows: click the address bar in File Explorer, type `cmd`, hit Enter.
   - Mac: right-click the folder → Services → New Terminal at Folder.
   - Linux: right-click → Open in Terminal.
3. **Create a virtual environment** (keeps the game's files separate from your system Python):
   ```
   python -m venv .venv
   ```
   On Mac/Linux, if `python` isn't found, use `python3 -m venv .venv`.
4. **Activate it:**
   - Windows: `.venv\Scripts\activate`
   - Mac/Linux: `source .venv/bin/activate`

   Your prompt should now start with `(.venv)` — that means it worked.
5. **Install the game's one dependency:**
   ```
   pip install -r requirements.txt
   ```
6. **Fly:**
   ```
   python main.py
   ```

That's it. You're in the cockpit.

## Controllers

- **Keyboard** works out of the box (see Controls below).
- **DualShock 4 / Xbox-style pad:** plug it in before launching and it just works.
- **TwinStick phone app:** pair the phone over Bluetooth, then run:
  ```
  python main.py --layout xpad
  ```

## Controls (keyboard)

| Key | Action |
|---|---|
| `W` / `S` | Pitch up / down |
| `A` / `D` | Roll left / right |
| `←` / `→` | Yaw left / right |
| `↑` / `↓` | Throttle up / down |
| `Space` | Fire |
| `T` | Target closest enemy |
| `Y` | Cycle target |
| `Esc` | Quit |

## Troubleshooting

- **`'python' is not recognized`** (Windows): reinstall Python and tick "Add python.exe to PATH".
- **`pip install` fails or installs to the wrong place**: make sure the virtual
  environment is activated — your terminal prompt should start with `(.venv)`.
- **Controller not detected**: plug it in / pair it *before* starting the game.
  If the game is already running, restart it.
- **Still stuck?** Open an issue at <https://github.com/Pazuzu1wish/3d_space> —
  say what OS you're on and paste the exact error message.
