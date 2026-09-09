# FLP Note Converter

Converts native FL Studio 21 `.fsc` score files and `.flp` projects to Standard MIDI. The GUI uses Python and does not require Rust, Cargo, Visual Studio, or `link.exe`.

## Run it

Open PowerShell:



1. Click **Browse...** beside **Input FSC/FLP**.
2. Select your native `.fsc` score or `.flp` project.
3. Choose an output `.mid` path.
4. Click **Convert notes**.
5. Import the MIDI in FL Studio 21 with **File > Import > MIDI file**.

The GUI parses the native FL Studio event stream in Python, extracts piano-roll notes, splits very large note sets across multiple MIDI tracks, and writes the MIDI file directly.

## Command line

```powershell
python flp_to_midi.py "Pattern 1 - ????.fsc" --output output.mid
```

No Rust build step is needed.

## Large note sets

Large source files are automatically split across MIDI tracks so FL Studio does not receive more than 16,000 notes in one track. Notes are not discarded because of the 32,769-note importer limit.

## What is converted

- Native FL Studio pattern notes
- Note position and duration
- Pitch, velocity, and MIDI channel
- Source PPQ/timebase

The converter does not recreate plugins, samples, automation, or the complete Playlist arrangement. It exports discovered piano-roll notes to MIDI. Native `.flp` input is read for its embedded pattern notes; it is not rewritten as a new `.flp`.

## Optional Rust backend

The `rust-midi` folder contains an optional Rust writer. It is not needed for normal use. Building it on Windows requires Visual Studio Build Tools with **Desktop development with C++**, but the Python GUI and command-line converter work without it.


