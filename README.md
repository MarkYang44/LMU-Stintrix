English | [简体中文](README.zh-CN.md)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="src/branding/stx-menu.png">
  <img src="src/branding/stx-menu-light.png" alt="STINTRIX logo" width="220">
</picture>

# LMU Stintrix

A local telemetry HUD and lap analysis toolkit for **Le Mans Ultimate**.

See your inputs while driving. Compare braking, throttle application, and pace afterward. Keep a history of your progress.

[![Release](https://img.shields.io/github/v/release/MarkYang44/LMU-Stintrix?label=release)](https://github.com/MarkYang44/LMU-Stintrix/releases/latest)
![Windows x64](https://img.shields.io/badge/platform-Windows%20x64-0078D4)
[![MIT License](https://img.shields.io/badge/license-MIT-668B28)](LICENSE)

**[Download for Windows x64](https://github.com/MarkYang44/LMU-Stintrix/releases/latest)** · [Quick start](#quick-start) · [Documentation](#documentation)

## Overview

Stintrix brings live driving feedback, automatic recording, and post-session analysis into one desktop app. Compare complete laps by track distance to see where your inputs and lap times differ, then revisit personal records as you practice.

It reads LMU's native shared memory without DLL injection or game-file changes. English and Simplified Chinese menus, dark and light themes, and local reports are included. Your recordings stay on your computer.

## Screenshots

Real windows from the current source version, using generated sample sessions and the built-in DEMO, not actual driving results. The clean HUD uses language-neutral graphics. [Capture details](docs/screenshots/README.md).

<table>
  <tr>
    <td width="50%"><strong>Control center</strong><br><a href="docs/screenshots/en/control-center.webp"><img src="docs/screenshots/en/control-center.webp" alt="English control center with HUD controls and telemetry options" width="520"></a></td>
    <td width="50%"><strong>Personal bests and conditions</strong><br><a href="docs/screenshots/en/personal-best.webp"><img src="docs/screenshots/en/personal-best.webp" alt="English personal-best detail with car, lap time, track conditions, and tires" width="520"></a></td>
  </tr>
  <tr>
    <td><strong>Live input HUD</strong><br><a href="docs/screenshots/en/input-hud.webp"><img src="docs/screenshots/en/input-hud.webp" alt="DEMO clean HUD showing throttle, brake, steering, and pedal bars" width="520"></a></td>
    <td><strong>Session library</strong><br><a href="docs/screenshots/en/session-library.webp"><img src="docs/screenshots/en/session-library.webp" alt="English session library with generated races and lap review actions" width="520"></a></td>
  </tr>
</table>

## Core features

### See your inputs on track

- Live throttle, brake, and steering traces, with raw or game-filtered input.
- Compact layouts and optional tire, fuel, Virtual Energy, pit, stint, and weather panels.

### Keep sessions ready for review

- Automatic qualifying and race recording; practice recording is optional.
- Lossless telemetry storage, CSV export, searchable sessions, and ZIP / 7z session packages.

### Understand lap differences

- Compare valid complete laps from the same track layout, within or across sessions.
- Distance-aligned inputs, speed, time differences, and recorded trajectories.

### Give practice a focus

- Training priorities and saved practice targets based on recorded laps.
- Progress analysis that considers car, fuel, tires, weather, and available conditions.

### Follow your records

- Personal bests by layout and vehicle class, record history, and confirmed class podiums.
- Read-only game-result XML integration and locally exported achievement cards.

### Review video inputs · Experimental

- Estimated throttle and brake traces from a calibrated local video, with optional historical-lap comparison.
- Results stay separate from native records. Local FFmpeg is required; see [Video analysis](docs/VIDEO_ANALYSIS.md).

## Installation

1. Download `LMU-Stintrix-v*-windows-x64.zip` from the [latest release](https://github.com/MarkYang44/LMU-Stintrix/releases/latest).
2. Extract the entire archive into a writable folder.
3. Run **`LMU-Stintrix.exe`**.

No Python installation is required. Keep `_internal` beside the EXE; relocate the whole folder together. Preserve `data/` and your settings when updating.

<details>
<summary>Run from source</summary>

Use **Code → Download ZIP**, or clone the repository. Extract it, run `Setup.cmd`, then `Start.cmd`.

Source setup uses **Python 3.13 x64 with Tcl/Tk**. The script can install it through winget and prepares a local environment with pinned dependencies. Initial setup needs internet access. Configuration and troubleshooting: [Usage](docs/USAGE.md).

</details>

## Quick start

1. In LMU, enable **Settings → Gameplay → Enable Plugins**.
2. Open Stintrix and click **Start HUD**. Use **中文 / EN** to switch menu language.
3. Enter the track in windowed or borderless mode.
4. Drive a qualifying or race session; recording starts automatically. Practice recording is off by default; enable it under **Sampling & Telemetry** if needed.
5. Afterward, open **Session Review** to inspect the recording or compare laps.

Try **Demo Mode** or `Demo.cmd` to explore without connecting to the game.

## Compatibility and data sources

- **Target platform:** Windows 10 / 11 x64, matching [LMU's OS requirements](https://lemansultimate.com/system-requirements/). Builds and validation use Windows x64 with Python 3.13.
- **Live data:** native `LMU_Data` shared memory through the bundled [pyLMUSharedMemory SDK](THIRD_PARTY_NOTICES.md#pylmusharedmemory). No DLL injection or game-file modification.
- **Saved data:** Stintrix sessions, read-only LMU `.duckdb` import, and game-result XML where available.
- **Availability:** channels depend on the game / SDK and recording source. Position replay needs recorded coordinates; exclusive fullscreen may hide the desktop HUD.

RaceCom image generation is optional and requires your own generator. The core HUD and lap analysis do not require it.

## Project status

Under active development. The source tree and screenshots may be ahead of the latest portable release. Video extraction is experimental and produces estimates. See [release notes](docs/RELEASE_NOTES.md) for changes and [Releases](https://github.com/MarkYang44/LMU-Stintrix/releases) for packaged versions.

## Privacy

Telemetry stays on your computer, reports are generated locally, and there is no automatic telemetry upload. Exports can contain driver names and dates; review them before sharing. [Privacy and migration](docs/PRIVACY.md).

## Documentation

Detailed guides are currently primarily in Chinese.

| Document | What it covers |
| --- | --- |
| [Usage](docs/USAGE.md) | HUD operation, recording, review, and troubleshooting |
| [Architecture](docs/ARCHITECTURE.md) | Module responsibilities and development boundaries |
| [Performance](docs/PERFORMANCE.md) | Measured results, workloads, and tradeoffs |
| [Storage](docs/STORAGE_OPTIMIZATION.md) | Lossless storage, CSV recovery, and archives |
| [Data processing](docs/DATA_PROCESSING.md) | Shared analysis, training reuse, measured timings, and precision guarantees |
| [Video analysis](docs/VIDEO_ANALYSIS.md) | Calibration, tools, comparisons, and accuracy limits |
| [Privacy](docs/PRIVACY.md) | Local data, sharing, and migration |

## Development

Use **Python 3.13 x64 on Windows**, including Tcl/Tk. From a configured checkout:

```powershell
.\Setup.cmd -BuildTools
.venv\Scripts\python.exe tools/run_tests.py
.venv\Scripts\python.exe tools/build.py --no-checksums
```

Maintenance and validation: [Architecture](docs/ARCHITECTURE.md) · [Release workflow](docs/RELEASE.md).

Daily validation selects a small smoke set and checks related to pending changes. Use `--plan` to inspect the scope, `--tests <case>` for a precise check, and `--full` only when the complete historical suite is needed. See [Testing policy](docs/TESTING.md). Build the portable ZIP when preparing a release.

## License and credits

[MIT](LICENSE). Third-party code and artwork: [Third-party notices](THIRD_PARTY_NOTICES.md).

An independent community project, not affiliated with or endorsed by Studio 397 or Motorsport Games. Le Mans Ultimate and other referenced names belong to their respective owners.
