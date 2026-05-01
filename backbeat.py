# BackBeat — Music Video Batch Processor
# Reads a CSV and downloads + processes each video with the correct settings.
# Missing tools (yt-dlp, ffmpeg) are downloaded automatically on first run.

import subprocess, os, glob, sys, csv, re, shutil, tempfile, zipfile
import urllib.request
from urllib.parse import urlparse
import tkinter as tk
import tkinter.messagebox as _mb
from tkinter import ttk

# ── Config ────────────────────────────────────────────────────────────────────
FOLDER         = os.path.dirname(os.path.abspath(__file__))
_BIN_DIR       = os.path.join(FOLDER, 'bin')

YTDLP   = None
FFMPEG  = None
FFPROBE = None

def _find(name):
    """Return the path to a tool from ./bin/ or PATH, or None."""
    exe = name + ('.exe' if sys.platform == 'win32' else '')
    local = os.path.join(_BIN_DIR, exe)
    if os.path.isfile(local):
        return local
    return shutil.which(name)  # None if not in PATH

def _has_js_runtime():
    """Return True if a supported JS runtime is available for yt-dlp."""
    names = ['node', 'deno', 'bun']
    ext = '.exe' if sys.platform == 'win32' else ''
    for n in names:
        if os.path.isfile(os.path.join(_BIN_DIR, n + ext)):
            return True
        if shutil.which(n):
            return True
    return False

def _download_tools(missing):
    """Download yt-dlp and/or ffmpeg into ./bin/ with a Tkinter progress window."""
    os.makedirs(_BIN_DIR, exist_ok=True)

    win = tk.Tk()
    win.title('BackBeat — Downloading tools')
    win.resizable(False, False)
    frame = ttk.Frame(win, padding=20)
    frame.pack()
    status_var = tk.StringVar(value='Starting...')
    ttk.Label(frame, textvariable=status_var, width=52).pack(pady=(0, 8))
    bar = ttk.Progressbar(frame, length=420, mode='determinate', maximum=100)
    bar.pack(pady=(0, 6))
    detail_var = tk.StringVar(value='')
    ttk.Label(frame, textvariable=detail_var, foreground='gray').pack()
    win.update()

    def _fetch(url, dest, label, bar_start, bar_end):
        def _hook(count, block, total):
            if total > 0:
                frac = min(count * block / total, 1.0)
                bar['value'] = bar_start + frac * (bar_end - bar_start)
                if total > 1_000_000:
                    detail_var.set(f'{count * block / 1_048_576:.1f} MB / {total / 1_048_576:.1f} MB')
                else:
                    detail_var.set(f'{count * block // 1024} KB / {total // 1024} KB')
            win.update()
        status_var.set(label)
        win.update()
        urllib.request.urlretrieve(url, dest, _hook)

    is_win = sys.platform == 'win32'
    ytdlp_path   = os.path.join(_BIN_DIR, 'yt-dlp.exe'   if is_win else 'yt-dlp')
    ffmpeg_path  = os.path.join(_BIN_DIR, 'ffmpeg.exe'   if is_win else 'ffmpeg')
    ffprobe_path = os.path.join(_BIN_DIR, 'ffprobe.exe'  if is_win else 'ffprobe')
    deno_path    = os.path.join(_BIN_DIR, 'deno.exe'     if is_win else 'deno')

    need_ytdlp  = 'yt-dlp'  in missing
    need_ffmpeg = 'ffmpeg'  in missing or 'ffprobe' in missing

    if need_ytdlp and need_ffmpeg:
        ytdlp_end, ffmpeg_start, ffmpeg_end = 10, 10, 95
    elif need_ytdlp:
        ytdlp_end, ffmpeg_start, ffmpeg_end = 100, 0, 0
    else:
        ytdlp_end, ffmpeg_start, ffmpeg_end = 0, 0, 95

    try:
        if need_ytdlp:
            _fetch(
                'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe',
                ytdlp_path,
                'Downloading yt-dlp...',
                0, ytdlp_end,
            )

        if need_ffmpeg:
            zip_tmp = os.path.join(tempfile.gettempdir(), 'ffmpeg-btbn.zip')
            _fetch(
                'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip',
                zip_tmp,
                'Downloading ffmpeg (~130 MB)...',
                ffmpeg_start, ffmpeg_end,
            )
            status_var.set('Extracting ffmpeg...')
            detail_var.set('')
            bar['value'] = 97
            win.update()
            with zipfile.ZipFile(zip_tmp) as zf:
                for entry in zf.namelist():
                    if entry.endswith('/bin/ffmpeg.exe') or entry.endswith('/bin/ffmpeg'):
                        with zf.open(entry) as src, open(ffmpeg_path, 'wb') as dst:
                            dst.write(src.read())
                    elif entry.endswith('/bin/ffprobe.exe') or entry.endswith('/bin/ffprobe'):
                        with zf.open(entry) as src, open(ffprobe_path, 'wb') as dst:
                            dst.write(src.read())
            os.remove(zip_tmp)

        # Optional helper for yt-dlp on fresh Windows machines.
        if is_win and need_ytdlp and not _has_js_runtime():
            add_deno = _mb.askyesno(
                'Optional JavaScript runtime',
                'yt-dlp may show a warning about missing JavaScript runtimes on some YouTube videos.\n\n'
                'Install optional Deno now into .\\bin\\ to reduce extraction issues?',
                parent=win,
            )
            if add_deno:
                try:
                    deno_zip = os.path.join(tempfile.gettempdir(), 'deno-backbeat.zip')
                    _fetch(
                        'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip',
                        deno_zip,
                        'Downloading optional Deno runtime...',
                        95, 99,
                    )
                    status_var.set('Extracting Deno...')
                    detail_var.set('')
                    win.update()
                    with zipfile.ZipFile(deno_zip) as zf:
                        for entry in zf.namelist():
                            if entry.endswith('/deno.exe') or entry == 'deno.exe':
                                with zf.open(entry) as src, open(deno_path, 'wb') as dst:
                                    dst.write(src.read())
                                break
                        else:
                            raise RuntimeError('deno.exe was not found in archive')
                    os.remove(deno_zip)
                except Exception as deno_exc:
                    _mb.showwarning(
                        'Deno install skipped',
                        f'Could not install optional Deno runtime:\n{deno_exc}\n\n'
                        'BackBeat will still work; yt-dlp may continue to show JS runtime warnings.',
                        parent=win,
                    )

        bar['value'] = 100
        status_var.set('Done!')
        detail_var.set('All tools downloaded successfully.')
        win.update()
        win.after(1400, win.destroy)
        win.mainloop()

    except Exception as exc:
        win.destroy()
        sys.exit(f'ERROR downloading tools: {exc}')


def _init_tools():
    """Locate all required tools; offer to download them if any are missing."""
    global YTDLP, FFMPEG, FFPROBE
    tool_names = ['yt-dlp', 'ffmpeg', 'ffprobe']
    paths = {n: _find(n) for n in tool_names}
    missing = [n for n, p in paths.items() if p is None]

    if missing:
        if sys.platform == 'win32':
            _root = tk.Tk()
            _root.withdraw()
            answer = _mb.askyesno(
                'Missing tools',
                f'Required tool(s) not found: {", ".join(missing)}\n\n'
                'Download them now automatically?\n'
                '(No admin rights required — files go into .\\bin\\)',
            )
            _root.destroy()
            if not answer:
                sys.exit('Cancelled — required tools were not installed.')
            _download_tools(missing)
            paths = {n: _find(n) for n in tool_names}
            still_missing = [n for n, p in paths.items() if p is None]
            if still_missing:
                sys.exit(f'ERROR: Still missing after download: {", ".join(still_missing)}')
        else:
            sys.exit(
                f'ERROR: Missing required tools: {", ".join(missing)}\n'
                'Install yt-dlp and ffmpeg via your package manager.'
            )

    YTDLP   = paths['yt-dlp']
    FFMPEG  = paths['ffmpeg']
    FFPROBE = paths['ffprobe']

_init_tools()
BROWSER        = 'firefox'          # cookies source
QUALITY        = 'bestvideo/best'   # video-only, best quality
FMT            = 'mp4'
CRF            = '18'
PRESET         = 'fast'
ENCODE_PROFILE = 'Auto'
CROPDETECT_FRAMES = 200
BROWSER_CHOICES = {
    'None': None,
    'Firefox': 'firefox',
    'Chrome': 'chrome',
    'Chromium': 'chromium',
    'Edge': 'edge',
    'Safari': 'safari',
    'Opera': 'opera',
    'Vivaldi': 'vivaldi',
    'Brave': 'brave',
    'Whale': 'whale',
}

def detect_default_browser_choice():
    """Return settings dialog browser label based on system default browser."""
    if sys.platform != 'win32':
        return 'None'

    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice',
        ) as key:
            prog_id, _ = winreg.QueryValueEx(key, 'ProgId')
    except Exception:
        return 'Firefox'

    prog_id = prog_id.lower()
    token_to_choice = [
        ('firefox', 'Firefox'),
        ('chrome', 'Chrome'),
        ('msedge', 'Edge'),
        ('brave', 'Brave'),
        ('vivaldi', 'Vivaldi'),
        ('opera', 'Opera'),
        ('chromium', 'Chromium'),
        ('safari', 'Safari'),
        ('naverwhale', 'Whale'),
        ('whale', 'Whale'),
    ]
    for token, choice in token_to_choice:
        if token in prog_id:
            return choice
    return 'Firefox'

FORMAT_OPTIONS = ['webm', 'mp4']
QUALITY_PRESETS = {
    'Best available':  'bestvideo/best',
    '1080p max':       'bestvideo[height<=1080]/best[height<=1080]',
    '720p max':        'bestvideo[height<=720]/best[height<=720]',
    '480p max':        'bestvideo[height<=480]/best[height<=480]',
    'Smallest file':   'worstvideo/worst',
}
WEBM_PROFILES = {
    'Fast / Small': {
        'crf': '10', 'bitrate': '4M', 'maxrate': '6M', 'bufsize': '12M', 'cpu_used': '4'
    },
    'Medium / Medium': {
        'crf': '6', 'bitrate': '6M', 'maxrate': '9M', 'bufsize': '18M', 'cpu_used': '2'
    },
    'Slow / Big': {
        'crf': '4', 'bitrate': '8M', 'maxrate': '12M', 'bufsize': '24M', 'cpu_used': '0'
    },
}
WEBM_PROFILE_OPTIONS = ['Auto', *WEBM_PROFILES.keys()]
# ──────────────────────────────────────────────────────────────────────────────

PID = str(os.getpid())

_summary = []   # collects (title, status) tuples for the final overview

def log(msg):
    print(f'\n\033[1;96m╔══ {msg} \033[0m\n')

def log_song(title, msg):
    print(f'\n\033[1;96m╔══ [{title}] {msg} \033[0m\n')

def sanitize(name):
    """Make a string safe to use as a filename."""
    name = re.sub(r'[\\/:*?"<>|＂＜＞]', '', name)
    name = name.strip()
    return name[:120]

def output_basename(name):
    """Normalize a CSV filename value to a safe basename."""
    return sanitize(name.strip())


class _Tooltip:
    """Simple hover tooltip for any Tkinter widget."""
    def __init__(self, widget, text):
        self._widget = widget
        self._text = text
        self._win = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, _event=None):
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        self._win = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f'+{x}+{y}')
        tk.Label(
            tw, text=self._text, justify='left',
            background='#ffffe0', relief='solid', borderwidth=1,
            wraplength=320, padx=6, pady=4,
        ).pack()

    def _hide(self, _event=None):
        if self._win:
            self._win.destroy()
            self._win = None


def open_settings_dialog():
    """Prompt for runtime settings before batch processing starts."""
    root = tk.Tk()
    root.title('BackBeat Settings')
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=16)
    frame.grid(row=0, column=0, sticky='nsew')

    browser_var = tk.StringVar(value=detect_default_browser_choice())
    quality_label_var = tk.StringVar(value='Best available')
    format_var = tk.StringVar(value='webm')
    profile_var = tk.StringVar(value=ENCODE_PROFILE)
    result = {}

    browser_lbl = ttk.Label(frame, text='Browser cookies')
    browser_lbl.grid(row=0, column=0, sticky='w', pady=(0, 4))
    browser_box = ttk.Combobox(
        frame,
        textvariable=browser_var,
        values=list(BROWSER_CHOICES.keys()),
        state='readonly',
        width=22,
    )
    browser_box.grid(row=1, column=0, sticky='ew', pady=(0, 10))
    _BROWSER_TIP = (
        'yt-dlp borrows login cookies from your browser — no credentials needed.\n\n'
        '• Unlocks age-restricted and members-only videos.\n'
        '• If your account has YouTube Premium, cookies also grant access\n'
        '  to the higher-bitrate streams that Premium provides.\n\n'
        'Pick the browser you use for YouTube, or "None" to skip.'
    )
    _Tooltip(browser_lbl, _BROWSER_TIP)
    _Tooltip(browser_box, _BROWSER_TIP)

    ttk.Label(frame, text='Quality').grid(row=2, column=0, sticky='w', pady=(0, 4))
    quality_box = ttk.Combobox(
        frame,
        textvariable=quality_label_var,
        values=list(QUALITY_PRESETS.keys()),
        state='readonly',
        width=22,
    )
    quality_box.grid(row=3, column=0, sticky='ew', pady=(0, 10))

    format_lbl = ttk.Label(frame, text='Output format')
    format_lbl.grid(row=4, column=0, sticky='w', pady=(0, 4))
    format_box = ttk.Combobox(
        frame,
        textvariable=format_var,
        values=FORMAT_OPTIONS,
        state='readonly',
        width=22,
    )
    format_box.grid(row=5, column=0, sticky='ew', pady=(0, 10))
    _FORMAT_TIP = (
        'WEBM — recommended default for Unity/YARG compatibility.\n'
        '         Usually the best choice when your game supports it.\n\n'
        'MP4  — use only if WEBM is not usable in your setup\n'
        '         or for external compatibility needs.'
    )
    _Tooltip(format_lbl, _FORMAT_TIP)
    _Tooltip(format_box, _FORMAT_TIP)

    profile_lbl = ttk.Label(frame, text='WebM encode profile')
    profile_lbl.grid(row=6, column=0, sticky='w', pady=(0, 4))
    profile_box = ttk.Combobox(
        frame,
        textvariable=profile_var,
        values=WEBM_PROFILE_OPTIONS,
        state='readonly',
        width=22,
    )
    profile_box.grid(row=7, column=0, sticky='ew', pady=(0, 10))
    _PROFILE_TIP = (
        'Applies to WebM/VP8 output only.\n\n'
        'Auto: adjusts quality by source resolution.\n'
        'Fast / Small: fastest encode, smallest files, lower detail.\n'
        'Medium / Medium: balanced quality and speed.\n'
        'Slow / Big: best detail, slowest encode, largest files.'
    )
    _Tooltip(profile_lbl, _PROFILE_TIP)
    _Tooltip(profile_box, _PROFILE_TIP)

    def submit():
        result['browser'] = BROWSER_CHOICES[browser_var.get()]
        result['quality'] = QUALITY_PRESETS[quality_label_var.get()]
        result['format'] = format_var.get()
        result['encode_profile'] = profile_var.get()
        root.destroy()

    def cancel():
        result.clear()
        root.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=8, column=0, sticky='e')
    ttk.Button(button_frame, text='Start', command=submit).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(button_frame, text='Cancel', command=cancel).grid(row=0, column=1)

    frame.columnconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    root.protocol('WM_DELETE_WINDOW', cancel)
    root.bind('<Return>', lambda _event: submit())
    root.bind('<Escape>', lambda _event: cancel())
    browser_box.focus_set()
    root.mainloop()
    return result or None

def _unique_csv_values(rows, column_name):
    """Return distinct non-empty CSV values for a named column in first-seen order."""
    seen = set()
    values = []
    for row in rows:
        value = row.get(column_name, '').strip()
        folded = value.casefold()
        if value and folded not in seen:
            seen.add(folded)
            values.append(value)
    return values

def list_csv_files(folder):
    """Return CSV filenames in a folder, sorted with backbeat.csv first if present."""
    files = [name for name in os.listdir(folder) if name.lower().endswith('.csv') and name.lower() != 'backbeat_processed.csv']
    files.sort(key=lambda name: (name.casefold() != 'backbeat.csv', name.casefold()))
    return files

def load_csv_rows(csv_path):
    """Read CSV rows from disk using the existing BOM-tolerant encoding."""
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)

def load_processed_csv(processed_path):
    """Load the processed entries CSV. Returns empty list if not found."""
    if not os.path.exists(processed_path):
        return []
    try:
        return load_csv_rows(processed_path)
    except Exception:
        return []

def save_processed_csv(processed_path, rows):
    """Write processed entries to CSV."""
    if not rows:
        return
    with open(processed_path, 'w', newline='', encoding='utf-8-sig') as f:
        if rows:
            fieldnames = list(rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

def row_matches_processed(input_row, processed_row):
    """Check if input row and processed row are identical for all input columns."""
    plain_columns = ['Source', 'Filename', 'Youtube', 'Remove Black Bar']
    for col in plain_columns:
        if input_row.get(col, '').strip() != processed_row.get(col, '').strip():
            return False

    # Treat empty delay and '0' as equivalent
    def norm_delay(val):
        v = val.strip()
        return '0' if v == '' else v

    # Treat empty speed and '100' as equivalent
    def norm_speed(val):
        v = val.strip()
        return '100' if v == '' else v

    if norm_delay(input_row.get('Delay', '')) != norm_delay(processed_row.get('Delay', '')):
        return False
    if norm_speed(input_row.get('Speed', '')) != norm_speed(processed_row.get('Speed', '')):
        return False

    return True

def has_valid_video_url(row):
    """Return True when the row has a syntactically valid http/https URL."""
    raw = row.get('Youtube', '').strip()
    if not raw:
        return False
    try:
        parsed = urlparse(raw)
    except Exception:
        return False
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)

def open_csv_source_dialog(csv_folder):
    """Prompt for which CSV file and Source group to process."""
    csv_files = list_csv_files(csv_folder)
    if not csv_files:
        return None

    root = tk.Tk()
    root.title('BackBeat CSV + Source Filter')
    root.resizable(False, False)

    frame = ttk.Frame(root, padding=16)
    frame.grid(row=0, column=0, sticky='nsew')

    csv_var = tk.StringVar(value=csv_files[0])
    source_var = tk.StringVar(value='All')
    ignore_save_var = tk.BooleanVar(value=False)
    mark_processed_var = tk.BooleanVar(value=False)
    detail_var = tk.StringVar(value='')
    result = {}
    current_rows = []
    processed_csv_path = os.path.join(csv_folder, 'backbeat_processed.csv')
    processed_entries = load_processed_csv(processed_csv_path)

    csv_lbl = ttk.Label(frame, text='CSV file')
    csv_lbl.grid(row=0, column=0, sticky='w', pady=(0, 4))
    csv_box = ttk.Combobox(
        frame,
        textvariable=csv_var,
        values=csv_files,
        state='readonly',
        width=34,
    )
    csv_box.grid(row=1, column=0, sticky='ew', pady=(0, 10))
    _CSV_TIP = (
        'Choose which CSV file in the script folder to process.\n\n'
        'When you switch CSV files, the Source list below refreshes automatically '
        'from that file.'
    )
    _Tooltip(csv_lbl, _CSV_TIP)
    _Tooltip(csv_box, _CSV_TIP)

    source_lbl = ttk.Label(frame, text='Source')
    source_lbl.grid(row=2, column=0, sticky='w', pady=(0, 4))
    source_box = ttk.Combobox(
        frame,
        textvariable=source_var,
        values=['All'],
        state='readonly',
        width=34,
    )
    source_box.grid(row=3, column=0, sticky='ew', pady=(0, 6))
    _SOURCE_TIP = (
        'Choose which setlist source to process from the CSV.\n\n'
        'All processes every row.\n'
        'Any other option only processes rows where the Source column matches exactly.'
    )
    _Tooltip(source_lbl, _SOURCE_TIP)
    _Tooltip(source_box, _SOURCE_TIP)

    ignore_save_check = ttk.Checkbutton(frame, text='Ignore save file', variable=ignore_save_var)
    ignore_save_check.grid(row=4, column=0, sticky='w', pady=(0, 6))
    _IGNORE_SAVE_TIP = (
        'If checked, process all rows regardless of prior encoding history.\n\n'
        'Processed entries are still updated after encoding.'
    )
    _Tooltip(ignore_save_check, _IGNORE_SAVE_TIP)

    mark_processed_check = ttk.Checkbutton(frame, text='Mark all as processed', variable=mark_processed_var)
    mark_processed_check.grid(row=5, column=0, sticky='w', pady=(0, 6))
    _MARK_PROCESSED_TIP = (
        'If checked, add all selected rows to the processed cache without encoding.\n\n'
        'Use this if you\'ve already encoded these videos and want to skip them.\n'
        'If you don\'t know what this means, leave it OFF.'
    )
    _Tooltip(mark_processed_check, _MARK_PROCESSED_TIP)

    detail_lbl = ttk.Label(frame, textvariable=detail_var, foreground='gray')
    detail_lbl.grid(row=6, column=0, sticky='w', pady=(0, 12))

    def update_detail_display():
        """Calculate and display how many songs will be processed."""
        selected_source = source_var.get()
        ignore_save = ignore_save_var.get()
        
        # Filter rows by source if needed
        filtered_rows = current_rows
        if selected_source != 'All':
            selected_source_folded = selected_source.casefold()
            filtered_rows = [
                row for row in current_rows
                if row.get('Source', '').strip().casefold() == selected_source_folded
            ]

        # Ignore rows with missing/invalid URLs entirely.
        filtered_rows = [row for row in filtered_rows if has_valid_video_url(row)]
        
        # Count how many will actually be processed
        to_process = 0
        if ignore_save:
            to_process = len(filtered_rows)
        else:
            for row in filtered_rows:
                already_processed = False
                for proc_entry in processed_entries:
                    if row_matches_processed(row, proc_entry):
                        already_processed = True
                        break
                if not already_processed:
                    to_process += 1
        
        total = len(filtered_rows)
        detail_var.set(f'{total} row(s) in source, {to_process} to process')

    def refresh_sources(_event=None):
        nonlocal current_rows
        csv_name = csv_var.get().strip()
        csv_path = os.path.join(csv_folder, csv_name)

        try:
            current_rows = load_csv_rows(csv_path)
        except Exception as exc:
            current_rows = []
            source_box.configure(values=['All'])
            source_var.set('All')
            detail_var.set(f'Could not read {csv_name}: {exc}')
            return

        source_values = _unique_csv_values(current_rows, 'Source')
        options = ['All', *source_values]
        source_box.configure(values=options)
        if source_var.get() not in options:
            source_var.set('All')

        update_detail_display()

    def submit():
        csv_name = csv_var.get().strip()
        if not csv_name:
            return
        result['source'] = source_var.get()
        result['csv_name'] = csv_name
        result['csv_path'] = os.path.join(csv_folder, csv_name)
        result['rows'] = current_rows
        result['ignore_save_file'] = ignore_save_var.get()
        result['mark_processed'] = mark_processed_var.get()
        root.destroy()

    def cancel():
        result.clear()
        root.destroy()

    button_frame = ttk.Frame(frame)
    button_frame.grid(row=7, column=0, sticky='e')
    ttk.Button(button_frame, text='Process', command=submit).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(button_frame, text='Cancel', command=cancel).grid(row=0, column=1)

    frame.columnconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    root.protocol('WM_DELETE_WINDOW', cancel)
    root.bind('<Return>', lambda _event: submit())
    root.bind('<Escape>', lambda _event: cancel())
    csv_box.bind('<<ComboboxSelected>>', refresh_sources)
    source_var.trace_add('write', lambda *args: update_detail_display())
    ignore_save_var.trace_add('write', lambda *args: update_detail_display())
    refresh_sources()
    csv_box.focus_set()
    root.mainloop()
    return result or None

def resolve_webm_profile(width, height):
    """Pick an effective WebM profile for this source size."""
    if ENCODE_PROFILE != 'Auto':
        return ENCODE_PROFILE

    h = max(height, 1)
    if h <= 480:
        return 'Fast / Small'
    if h <= 1080:
        return 'Medium / Medium'
    return 'Slow / Big'

def video_output_args(fmt, webm_profile=None):
    """Return ffmpeg video encoding args for the selected container."""
    if fmt == 'webm':
        # VP8 for YARG compatibility; selected profile tunes speed/quality/size trade-off.
        selected = webm_profile or ENCODE_PROFILE
        p = WEBM_PROFILES.get(selected, WEBM_PROFILES['Medium / Medium'])
        return [
            '-c:v', 'libvpx',
            '-crf', p['crf'],
            '-b:v', p['bitrate'],
            '-maxrate', p['maxrate'],
            '-bufsize', p['bufsize'],
            '-deadline', 'good',
            '-cpu-used', p['cpu_used'],
        ]
    return ['-c:v', 'libx264', '-crf', CRF, '-preset', PRESET]

def probe(src, entry):
    """ffprobe a single stream entry, return stripped string."""
    return subprocess.check_output([
        FFPROBE, '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', f'stream={entry}',
        '-of', 'csv=p=0', src
    ], text=True).strip()

def cropdetect(src):
    """Run cropdetect, return 'crop=W:H:X:Y' string or None."""
    out = subprocess.run([
        FFMPEG, '-i', src,
        '-vf', 'cropdetect=limit=24:round=2:skip=2',
        '-frames:v', str(CROPDETECT_FRAMES),
        '-f', 'null', '-'
    ], capture_output=True, text=True).stderr
    lines = [l for l in out.splitlines() if 'crop=' in l]
    if not lines:
        return None
    val = lines[-1].split('crop=')[-1].split()[0]
    return 'crop=' + val

# Pad to 16:9 without scaling content. Keeps original pixels while adding black bars.
LETTERBOX_16_9_FILTER = (
    r'pad='
    r'if(gte(iw/ih\,16/9)\,iw\,ceil(ih*16/9/2)*2)'
    r':if(gte(iw/ih\,16/9)\,ceil(iw*9/16/2)*2\,ih)'
    r':(ow-iw)/2:(oh-ih)/2:black'
    r',setsar=1'
)

def build_vf(crop_filter, speed_factor, include_letterbox=False):
    """Build the -vf filter string in the order: crop → speed → pad."""
    parts = []
    if crop_filter:
        parts.append(crop_filter)
    if abs(speed_factor - 1.0) > 1e-6:
        parts.append(f'setpts={1/speed_factor:.6f}*PTS')
    if include_letterbox:
        parts.append(LETTERBOX_16_9_FILTER)
    return ','.join(parts) if parts else None

def output_canvas_size(width, height, include_letterbox):
    """Return final output frame size after optional letterbox filter."""
    if include_letterbox:
        # Mirror LETTERBOX_16_9_FILTER output sizing so concat inputs match exactly.
        if width * 9 >= height * 16:
            out_w = width
            out_h = ((width * 9 + 31) // 32) * 2
        else:
            out_w = ((height * 8 + 8) // 9) * 2
            out_h = height
        return out_w, out_h
    return width, height

def process_video(output_name, url, delay_ms, speed_pct, remove_bars, output_dir=FOLDER):
    """Download and post-process one video. Returns True on success."""
    os.makedirs(output_dir, exist_ok=True)
    speed_factor = speed_pct / 100.0
    sec          = abs(delay_ms) / 1000.0

    log_song(output_name, f'Downloading from {url}')

    # ── Step 1: Download ──────────────────────────────────────────────────────
    raw_tmpl = os.path.join(FOLDER, '%(title)s_raw_' + PID + f'.{FMT}')
    yt_dlp_cmd = [
        YTDLP,
        '-f', QUALITY,
        '--merge-output-format', FMT,
        '--postprocessor-args', 'ffmpeg:-an',
        '-o', raw_tmpl,
        '--no-playlist',
    ]
    if BROWSER:
        yt_dlp_cmd.extend(['--cookies-from-browser', BROWSER])
    yt_dlp_cmd.append(url)
    try:
        subprocess.run(yt_dlp_cmd, check=True)
    except subprocess.CalledProcessError:
        log_song(output_name, '✗ Download FAILED')
        return False

    # ── Step 2: Find downloaded file ──────────────────────────────────────────
    pattern = os.path.join(FOLDER, '*_raw_' + PID + f'.{FMT}')
    files   = glob.glob(pattern)
    if not files:
        log_song(output_name, '✗ Could not find downloaded file')
        return False

    for src in files:
        dst = os.path.join(output_dir, output_name + f'.{FMT}')

        log_song(output_name, 'Post-processing: ' + os.path.basename(src))

        # Probe dimensions
        try:
            vw  = int(probe(src, 'width'))
            vh  = int(probe(src, 'height'))
            fps = probe(src, 'avg_frame_rate')
        except Exception as e:
            log_song(output_name, f'✗ ffprobe failed: {e}')
            os.remove(src)
            return False

        log_song(output_name, f'Source: {vw}x{vh} @ {fps}')

        if abs(speed_factor - 1.0) > 1e-6:
            direction = 'slower' if speed_pct < 100 else 'faster'
            log_song(output_name, f'Speed: {speed_pct:.3f}% (playing {direction})')

        # Crop detection
        crop_filter = None
        if remove_bars:
            log_song(output_name, f'Scanning for black bars ({CROPDETECT_FRAMES} frames)...')
            crop_filter = cropdetect(src)
            if crop_filter:
                val = crop_filter.replace('crop=', '')
                cw, ch = int(val.split(':')[0]), int(val.split(':')[1])
                vw, vh = cw, ch   # use cropped dimensions for letterbox sizing
                log_song(output_name, f'Black bars detected — cropping to {cw}x{ch}')
            else:
                log_song(output_name, 'No black bars detected')

        # Preserve source resolution, and add 16:9 letterbox when needed.
        is_widescreen = (vw * 9 == vh * 16)
        use_letterbox = not is_widescreen
        if use_letterbox:
            log_song(output_name, 'Preserving resolution with 16:9 letterbox')

        active_webm_profile = resolve_webm_profile(vw, vh)
        out_w, out_h = output_canvas_size(vw, vh, use_letterbox)
        if FMT == 'webm':
            log_song(output_name, f'Encode profile: {active_webm_profile}')

        if use_letterbox:
            log_song(output_name, f'Letterboxing {vw}x{vh} → {out_w}x{out_h} (16:9)')

        # ── Step 3: ffmpeg post-process ───────────────────────────────────────
        try:
            if delay_ms < 0:
                # Prepend black frames
                black_w, black_h = out_w, out_h
                log_song(output_name, f'Prepending {abs(delay_ms)}ms black frames')

                # Build filter_complex
                vfilters = []
                if crop_filter:
                    vfilters.append(crop_filter)
                if abs(speed_factor - 1.0) > 1e-6:
                    vfilters.append(f'setpts={1/speed_factor:.6f}*PTS')
                if use_letterbox:
                    vfilters.append(LETTERBOX_16_9_FILTER)

                if vfilters:
                    fc = f'[1:v]{",".join(vfilters)}[vproc];[0:v][vproc]concat=n=2:v=1:a=0[v]'
                else:
                    fc = '[0:v][1:v]concat=n=2:v=1:a=0[v]'

                subprocess.run([
                    FFMPEG,
                    '-f', 'lavfi',
                    '-i', f'color=c=black:s={black_w}x{black_h}:r={fps}:d={sec:.6f}',
                    '-i', src,
                    '-filter_complex', fc,
                    '-map', '[v]',
                    '-an',
                    *video_output_args(FMT, active_webm_profile),
                    dst,
                ], check=True)

            elif delay_ms > 0:
                # Trim from start (after speed, measured in speed-adjusted timeline)
                log_song(output_name, f'Trimming {delay_ms}ms from start (speed-adjusted)')

                vfilters = []
                if crop_filter:
                    vfilters.append(crop_filter)
                if abs(speed_factor - 1.0) > 1e-6:
                    vfilters.append(f'setpts={1/speed_factor:.6f}*PTS')
                vfilters.append(f'trim=start={sec:.6f}')
                vfilters.append('setpts=PTS-STARTPTS')
                if use_letterbox:
                    vfilters.append(LETTERBOX_16_9_FILTER)

                subprocess.run([
                    FFMPEG,
                    '-i', src,
                    '-vf', ','.join(vfilters),
                    '-an',
                    *video_output_args(FMT, active_webm_profile),
                    dst,
                ], check=True)

            else:
                # No timing change — speed and/or crop and/or letterbox only
                vf = build_vf(crop_filter, speed_factor, use_letterbox)
                if vf:
                    subprocess.run([
                        FFMPEG, '-i', src,
                        '-vf', vf,
                        '-an',
                        *video_output_args(FMT, active_webm_profile),
                        dst,
                    ], check=True)
                else:
                    # Nothing to do — just rename
                    log_song(output_name, 'No processing needed — renaming')
                    os.rename(src, dst)
                    log_song(output_name, f'✓ Done: {os.path.basename(dst)}')
                    return True

        except subprocess.CalledProcessError as e:
            log_song(output_name, f'✗ ffmpeg FAILED')
            if os.path.exists(src): os.remove(src)
            return False

        os.remove(src)
        log_song(output_name, f'✓ Done: {os.path.basename(dst)}')

    return True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    global BROWSER, QUALITY, FMT, ENCODE_PROFILE

    settings = open_settings_dialog()
    if not settings:
        print('Startup cancelled.')
        sys.exit(0)

    BROWSER = settings['browser']
    QUALITY = settings['quality']
    FMT = settings['format']
    ENCODE_PROFILE = settings['encode_profile']

    csv_folder = os.path.dirname(os.path.abspath(__file__))
    csv_files = list_csv_files(csv_folder)
    if not csv_files:
        print(f'\033[1;91mERROR: No CSV files found in {csv_folder}\033[0m')
        print('Place one or more .csv files in the same folder as this script.')
        input('Press Enter to close...')
        sys.exit(1)

    source_selection = open_csv_source_dialog(csv_folder)
    if not source_selection:
        print('CSV/source selection cancelled.')
        sys.exit(0)

    csv_path = source_selection['csv_path']
    selected_csv = source_selection['csv_name']
    rows = source_selection['rows']
    selected_source = source_selection['source']
    ignore_save_file = source_selection.get('ignore_save_file', False)
    mark_processed = source_selection.get('mark_processed', False)
    processed_csv_path = os.path.join(csv_folder, 'backbeat_processed.csv')
    processed_entries = load_processed_csv(processed_csv_path)
    if selected_source != 'All':
        selected_source_folded = selected_source.casefold()
        rows = [
            row for row in rows
            if row.get('Source', '').strip().casefold() == selected_source_folded
        ]

    # Ignore rows with missing/invalid URLs so they do not count or process.
    rows = [row for row in rows if has_valid_video_url(row)]

    # If mark_processed flag is set, add all rows to processed cache and exit
    if mark_processed:
        for row in rows:
            # Only add if not already present
            found = False
            for proc_entry in processed_entries:
                if row_matches_processed(row, proc_entry):
                    found = True
                    break
            if not found:
                processed_entries.append(row.copy())
        save_processed_csv(processed_csv_path, processed_entries)
        print(f'\033[1;92m✓ Added {len(rows)} row(s) to processed cache\033[0m')
        input('Press Enter to close...')
        sys.exit(0)

    total = len(rows)
    log(f'BackBeat — {total} videos to process')
    log(
        f'Settings: browser={BROWSER}  quality={QUALITY}  format={FMT} '
        f'encode={ENCODE_PROFILE}  csv={selected_csv}  source={selected_source}'
    )

    if total == 0:
        print(f'No rows matched source "{selected_source}".')
        input('Press Enter to close...')
        sys.exit(0)

    results = []   # list of (title, ok, notes)

    for i, row in enumerate(rows, 1):
        filename   = output_basename(row.get('Filename', ''))
        source_name = row.get('Source', '').strip()
        url        = row.get('Youtube', '').strip()
        delay_raw  = row.get('Delay', '').strip()
        speed_raw  = row.get('Speed', '').strip()
        bar_raw    = row.get('Remove Black Bar', '').strip().upper()

        if not filename:
            log(f'[{i}/{total}] Skipping row — no filename')
            results.append(('<missing filename>', False, 'no filename'))
            continue

        delay_ms    = int(delay_raw)   if delay_raw  else 0
        speed_pct   = float(speed_raw) if speed_raw  else 100.0
        remove_bars = bar_raw in ('TRUE', '1', 'YES')

        # Check if already processed (unless ignore flag is set)
        if not ignore_save_file:
            already_processed = False
            for proc_entry in processed_entries:
                if row_matches_processed(row, proc_entry):
                    log(f'[{i}/{total}] Skipping "{filename}" — already processed with identical parameters')
                    results.append((filename, True, 'skipped (already processed)'))
                    already_processed = True
                    break
            if already_processed:
                continue

        log(f'[{i}/{total}] {filename}  |  delay={delay_ms}ms  speed={speed_pct}%  bars={remove_bars}')

        notes = []
        if delay_ms != 0:
            notes.append(f'delay {delay_ms}ms')
        if abs(speed_pct - 100.0) > 0.001:
            notes.append(f'speed {speed_pct}%')
        if remove_bars:
            notes.append('crop bars')

        output_dir = FOLDER
        source_folder_name = sanitize(source_name) if source_name else 'Unknown_Source'
        output_dir = os.path.join(FOLDER, source_folder_name)

        ok = process_video(filename, url, delay_ms, speed_pct, remove_bars, output_dir=output_dir)
        results.append((filename, ok, ', '.join(notes) if notes else 'no adjustments'))

        # Update processed CSV if encoding was successful
        if ok:
            # Check if this row already exists in processed_entries and update it
            found = False
            for proc_entry in processed_entries:
                if row_matches_processed(row, proc_entry):
                    # Already in the list with same params, no change needed
                    found = True
                    break
            if not found:
                # Add new entry to processed list
                processed_entries.append(row.copy())

    # Save processed entries CSV
    save_processed_csv(processed_csv_path, processed_entries)

    # ── Final summary ─────────────────────────────────────────────────────────
    print('\n\033[1;96m' + '═' * 70 + '\033[0m')
    print('\033[1;96m  BATCH SUMMARY\033[0m')
    print('\033[1;96m' + '═' * 70 + '\033[0m')
    ok_count   = sum(1 for _, ok, _ in results if ok)
    fail_count = total - ok_count
    for title, ok, notes in results:
        icon  = '✓' if ok else '✗'
        color = '96' if ok else '91'
        print(f'\033[1;{color}m  {icon} {title}\033[0m\033[{color}m  [{notes}]\033[0m')
    print('\033[1;96m' + '═' * 70 + '\033[0m')
    print(f'\033[1;96m  {ok_count}/{total} completed successfully'
          + (f'  |  {fail_count} failed' if fail_count else '') + '\033[0m')
    print('\033[1;96m' + '═' * 70 + '\033[0m\n')
    input('Press Enter to close...')


if __name__ == '__main__':
    main()
