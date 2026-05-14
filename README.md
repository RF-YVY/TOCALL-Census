# TOCALL Census

Standalone APRS-IS TOCALL monitor for tracking deployment and usage of APRS applications, radios, and software.

## Features

- Connects directly to APRS-IS raw packet feeds.
- Extracts the destination TOCALL from the raw packet header between `>` and the first `,` or `:`.
- Tracks live counts, recent packets, unique source stations, and RF-via-IGate activity.
- Stores packet events in SQLite at `data/tocall_monitor.sqlite3`.
- Downloads the APRS Foundation APRS Device Identification Database for TOCALL lookup labels.
- Displays recent position packets on a Leaflet/OpenStreetMap dashboard.
- Includes light and dark display modes.
- Includes an in-app how-to guide.
- Clears the current session when switching TOCALL targets.
- Exports reports as PDF, JSON, or CSV.
- Shows a Found in scoreboard for US states and countries using unique located packets.
- Checks GitHub for newer releases or tags from `RF-YVY/TOCALL-Census`.
- Exposes JSON counts at `/api/counts`.

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 14502
```

Open <http://127.0.0.1:14502>.

## Portable Windows EXE

Build a portable EXE with PyInstaller:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pyinstaller --clean --noconfirm --name "TOCALL-Census" --add-data "static;static" run_tocall_census.py
```

The portable build is created at `dist\TOCALL-Census\TOCALL-Census.exe`.

Run it from that folder:

```powershell
.\dist\TOCALL-Census\TOCALL-Census.exe
```

The EXE opens TOCALL Census at <http://127.0.0.1:14502>. Packet storage and the TOCALL registry cache are written to a `data` folder beside the EXE, keeping the build portable.

## How To Use

1. Enter a TOCALL such as `APDW16` to track one application or radio, or leave the field blank to count all traffic matching the APRS-IS filter.
2. Set an APRS-IS filter. Regional filters such as `r/34/-89/250` are easier on the network and make the census more meaningful; `r/0/0/9999` requests worldwide traffic.
3. Click Connect and watch the live counts, packet list, and map update. Callsign and APRS-IS passcode are optional because TOCALL Census only receives and decodes APRS-IS traffic.
4. Open Advanced APRS-IS identity only if you want to identify the client with your callsign in APRS-IS server logs.
5. Use Clear Session before tracking a new TOCALL if you want to disconnect and empty counts, packet history, and map points.
6. Review Found in to see which US states and countries had unique located packets for the selected TOCALL.
7. Use Export PDF, Export JSON, or Export CSV to save the current report.
8. Use Refresh Registry whenever you want the latest APRS device/software lookup labels.
9. Use the How To button in the app for the quick operating guide, and the theme button to switch light/dark modes.

## Version Checks

The app exposes `/api/version`, which checks:

1. the latest GitHub release at <https://github.com/RF-YVY/TOCALL-Census/releases>
2. the latest tag if no release exists
3. the repository URL if release metadata is unavailable

## APRS-IS Notes

The dashboard defaults to:

- server: `rotate.aprs2.net`
- port: `14580`
- optional callsign: `N0CALL`
- optional passcode: `-1`
- filter: `r/0/0/9999`

For receive-only monitoring, you do not need to enter an APRS-IS callsign/passcode. The default `N0CALL` and `-1` values identify the app as an unverified receive-only client. Use your own amateur radio callsign and APRS-IS passcode only if you want APRS-IS servers to log your client under your callsign. A narrow APRS-IS filter is strongly recommended because the full APRS-IS firehose is unnecessary for TOCALL deployment monitoring.

Useful filters:

```text
r/34/-89/250
t/p
r/34/-89/250 t/p
```

## Registry Source

The app refreshes from the APRS Foundation-hosted database:

<https://aprs-deviceid.aprsfoundation.org/tocalls.pretty.json>

The upstream registry is maintained at:

<https://github.com/aprsorg/aprs-deviceid>
