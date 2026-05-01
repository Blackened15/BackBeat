# BackBeat

BackBeat batch-downloads and post-processes YouTube music videos for use as background videos in rhythm games such as YARG.

It reads one or more CSV playlists, lets you choose what to process in a small Tkinter setup window, then downloads video-only sources with yt-dlp and converts them into game-friendly output files.

## What BackBeat Does

Given a CSV playlist, BackBeat can:

- download the selected YouTube video
- strip audio so the output is video-only
- optionally remove black bars with `cropdetect`
- apply a start delay or a black pre-roll pad
- apply playback speed correction
- pad the final result to a 16:9 canvas without scaling the original image
- encode to `webm` or `mp4`
- skip rows that were already processed with identical CSV parameters

The included `backbeat.csv` covers a large Rock Band music-video set, so a full run can take a long time depending on connection speed and CPU performance.

## Sync Accuracy

BackBeat's timing values are practical approximations, not guarantees. Official music videos often use different edits, mixes, intros, or lengths than the in-game stems they are meant to accompany.

If you find a better source video, a more accurate delay or speed value, or an incorrect mapping, open an issue.

## Requirements

- Python 3.10 or newer
- Tkinter available in your Python install
- Windows is the primary supported workflow for automatic tool download

BackBeat requires these external tools:

- `yt-dlp`
- `ffmpeg`
- `ffprobe`

If those tools are not found on `PATH` or in `./bin`, BackBeat offers to download them automatically into the local `bin/` folder on Windows. No admin rights are required.

On some fresh Windows systems, yt-dlp may also benefit from an optional JavaScript runtime. BackBeat can offer to install `Deno` into `./bin` for that case.

## Quick Start

1. Install Python if needed. Download it from https://www.python.org/downloads/ and make sure `Add python.exe to PATH` is enabled during setup.
2. Put your CSV file in the same folder as `backbeat.py`, or use the included `backbeat.csv`.
3. Run:

```bash
python backbeat.py
```

4. If required tools are missing, allow BackBeat to download them.
5. In the setup window, choose your encoding settings and CSV selection.
6. Click `Start`.

BackBeat writes output into subfolders named after the CSV `Source` value, such as `RB1/`, `RB2/`, or `Unknown_Source/`.

## Setup Window

Current versions use a single combined startup window called `BackBeat Setup`.

The left side contains encoding settings:

- `Browser cookies`
- `Quality`
- `Output format`
- `WebM encode profile`

The right side contains CSV selection controls:

- `CSV file`
- `Source`
- `Ignore save file`
- `Mark all as processed`
- `Choose songs...`
- a live row count showing `X row(s) in source, Y to process`

`Choose songs...` opens a checkbox list built from the current CSV and Source selection. Only songs with valid URLs are shown. Songs already found in `backbeat_processed.csv` stay visible but start unchecked so you can manually re-run them.

Hover tooltips are available on the labeled controls and checkboxes.

### Encoding Settings

| Setting | Description |
|---|---|
| `Browser cookies` | Lets yt-dlp borrow cookies from your browser session. Useful for age-restricted videos, members-only videos, and Premium-only higher bitrate streams. On Windows, BackBeat tries to preselect your default browser. |
| `Quality` | `Best available`, `1080p max`, `720p max`, `480p max`, or `Smallest file`. |
| `Output format` | `webm` or `mp4`. `webm` is the default and generally the preferred option for rhythm-game video backgrounds. |
| `WebM encode profile` | Applies only to `webm`. `Auto` selects a profile by source height. Manual options are `Fast / Small`, `Medium / Medium`, and `Slow / Big`. |

### WebM Profiles

| Profile | CRF | Target Bitrate | Max Bitrate | CPU Used |
|---|---:|---:|---:|---:|
| `Fast / Small` | 10 | 4M | 6M | 4 |
| `Medium / Medium` | 6 | 6M | 9M | 2 |
| `Slow / Big` | 4 | 8M | 12M | 0 |

When `Auto` is selected, BackBeat chooses:

- `Fast / Small` for sources up to 480p
- `Medium / Medium` for sources up to 1080p
- `Slow / Big` for sources above 1080p

## CSV Selection And Filtering

BackBeat lists every `.csv` file in the script folder except `backbeat_processed.csv`. If `backbeat.csv` exists, it is listed first.

`Source` filtering is case-insensitive when choosing what to process. `All` processes every matching row in the selected CSV.

Rows with missing or invalid `Youtube` URLs are ignored entirely. They do not count toward the live row total and they are never processed.

## CSV Format

Use this header layout:

```csv
Source,Filename,Youtube,Delay,Speed,Remove Black Bar
RB1,my_video,https://www.youtube.com/watch?v=...,0,100,yes
RB2,another_song,https://youtu.be/...,500,98.5,no
```

| Column | Description |
|---|---|
| `Source` | Group or setlist name used for filtering and output folders. |
| `Filename` | Output file name without extension. Invalid filename characters are stripped automatically. |
| `Youtube` | Full `http` or `https` URL to the source video. |
| `Delay` | Milliseconds to adjust the start. Positive values trim from the start. Negative values add black video at the front. Blank is treated as `0`. |
| `Speed` | Playback speed percentage. `100` means unchanged. Blank is treated as `100`. |
| `Remove Black Bar` | Enables crop detection when set to `yes`, `true`, or `1`. |

## Processing Cache

BackBeat stores prior successful rows in `backbeat_processed.csv`.

This cache is based on the CSV input row, not on the chosen startup settings. A row is considered the same if these CSV fields match:

- `Source`
- `Filename`
- `Youtube`
- `Remove Black Bar`
- `Delay` with blank treated as `0`
- `Speed` with blank treated as `100`

That means changing format, quality, browser cookies, or WebM profile does not invalidate the cache by itself. If you want to re-encode the same rows with new startup settings, use `Ignore save file`.

### Ignore Save File

If checked, BackBeat processes all selected rows even if they already exist in `backbeat_processed.csv`.

### Mark All As Processed

If checked, BackBeat adds all selected rows to `backbeat_processed.csv` without downloading or encoding anything, then exits.

Use this only when those rows were already handled elsewhere and you want future runs to skip them.

## Output Behavior

- output files are written to a folder named after `Source`
- if `Source` is empty, output goes to `Unknown_Source/`
- the output extension matches your chosen format: `webm` or `mp4`
- audio is removed from the output
- if no processing is needed for a row, BackBeat may simply rename the downloaded file into place

At the end of the run, BackBeat prints a summary showing which rows succeeded, failed, or were skipped as already processed.

## CON File Compatibility And Nautilus Naming

The generated filenames are intended to line up with CON-format song sets that were batch-renamed with Nautilus using the `The Artist - Song` style shown below:

![Nautilus batch rename settings](docs/nautilus-rename.png)

When using Nautilus, make sure `Ignore Xbox file system limitations` is enabled so long or Unicode-safe names are not truncated unexpectedly.

## Third-Party Tools

BackBeat can download these tools into `./bin/` when needed:

| Tool | License | Source |
|---|---|---|
| `yt-dlp` | The Unlicense | https://github.com/yt-dlp/yt-dlp |
| `ffmpeg` | GPL v2+ | https://github.com/BtbN/FFmpeg-Builds |
| `Deno` | MIT | https://github.com/denoland/deno |

BackBeat itself is not affiliated with YARG, Rock Band, Nautilus, or any other rhythm-game project.

## Project Note

This project was built with heavy AI assistance. Most of the saved effort went into curating and syncing the included CSV dataset, which is the time-consuming part of a project like this.
