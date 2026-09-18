# itch.io release package — 3D SPACE: Cockpit Dogfighter

Everything needed to publish the game on itch.io. Create a new project at
https://itch.io/game/new, set "Kind of project" to **Game**, and paste away.

## Title

`3D SPACE — Cockpit Dogfighter`

## Tagline

`A 3D space shooter with no GPU, no engine, and no mercy. Pure Python, pure quaternions.`

## Description

You are a pilot in a cockpit, in deep space, and things are trying to kill you.

3D SPACE is a first-person dogfighter rendered entirely in software — every
vertex is CPU-projected through a hand-rolled quaternion math engine. No GPU.
No game engine. No stacks of CUDA cores. Just Python, pygame, and a stubborn
belief that software rendering can still slap.

**What's in the cockpit:**

- True 6-DOF quaternion flight model — pitch, yaw, and roll are always relative
  to *your* cockpit, never the world
- 7 enemy types: SuicideDrone, Dogfighter, Sniper (it telegraphs with a
  charging beam — dodge or die), Corvette, Minelayer, StealthInterceptor, Carrier
- Scripted encounters (wedges, pincers, sniper nests) plus a wave director that
  keeps pressure on between set-pieces
- Full cockpit HUD: pitch ladder, heading tape, 3D sensor sphere, hull/shield,
  throttle/speed, target locking
- Dodge thrusters (hold Circle + a direction), regenerating shields
- Object pools + spatial partitioning hold 60fps on modest hardware
- Playable with keyboard, DualShock 4, Xbox-style pads — or the TwinStick
  phone-controller app over Bluetooth

**Controls (keyboard):** `WASD` pitch/roll · `←→` yaw · `↑↓` throttle ·
`Space` fire · `T` target closest · `Y` cycle target

**Controls (controller):** left stick pitch/roll · right stick yaw ·
triggers fire · `L1/R1` throttle · `Circle`+stick dodge · D-pad target

## Metadata

- **Genre:** Shooter — Space sim
- **Made with:** pygame-ce (Python)
- **Tags:** `space`, `dogfighter`, `cockpit`, `software-rendering`, `pygame`,
  `singleplayer`, `retro`
- **License:** MIT
- **Price:** Free

## Uploads

1. `docs/screenshot-cockpit.png` — cover/hero image
2. `docs/screenshot-combat.png` — second screenshot
3. Source ZIP: `git archive --format=zip -o 3d-space.zip HEAD` (players need
   Python 3 + `pip install -r requirements.txt`, then `python main.py`)

## Post-publish checklist

- [ ] Screenshots attached and ordered
- [ ] "This game is free" / name-your-price set
- [ ] Community → enable comments
- [ ] Add the repo link (https://github.com/Pazuzu1wish/3d_space) under "Links"
- [ ] Optional: devlog post — "No CUDA cores were harmed"
