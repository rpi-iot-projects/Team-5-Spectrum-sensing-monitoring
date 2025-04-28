#!/usr/bin/env python3
import threading
import time
import adi
import numpy as np
import requests
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# rolling buffer for spectrogram columns
spec_buffer = []
# FFT params
SPEC_NFFT     = 256
SPEC_MAXCOLS  = 200
SPEC_HOP      = SPEC_NFFT // 2

# ——— Defaults & Globals ———
DEFAULT_URI        = "usb:1.23.5"
DEFAULT_LO_FREQ    = 2.440e9
DEFAULT_BUF_SIZE   = 1024
DEFAULT_SR         = 2e6    # fallback if sdr.sample_rate missing
DEFAULT_INTERVAL   = 0.1
DEFAULT_JAMMER_AMP = 1000.0
WEBHOOK_URL        = "https://iq-data-plotter.duckdns.org/api/webhook"
HEADERS            = {"Content-Type": "application/json"}

sdr       = None
run_flag  = threading.Event()
dt        = 1.0 / DEFAULT_SR

def compute_spectrogram_column(iq_block, n_fft=SPEC_NFFT):
    """
    Compute one column of an STFT spectrogram from complex IQ samples
    by using a full FFT (not rfft), then center the spectrum.
    """
    # 1) Cast & ensure contiguous complex64
    frame = np.ascontiguousarray(np.asarray(iq_block, dtype=np.complex64))

    # 2) Pad or trim
    if frame.size < n_fft:
        pad = np.zeros(n_fft - frame.size, dtype=np.complex64)
        frame = np.concatenate([pad, frame])
    else:
        frame = frame[-n_fft:]
    frame = np.ascontiguousarray(frame)

    # 3) Apply real Hann window
    window = np.hanning(n_fft).astype(np.float32)
    windowed = frame * window

    # 4) Full complex FFT & shift
    spectrum = np.fft.fft(windowed, n=n_fft)
    spectrum = np.fft.fftshift(spectrum)

    # 5) Return magnitudes (float64)
    return np.abs(spectrum)

def update_spectrogram_buffer(buffer, new_column, max_columns=SPEC_MAXCOLS):
    """
    Maintain a rolling buffer of spectrogram columns.
    Ensures each column is a proper float array.
    """
    # Cast the new column to float (in case it’s complex or int)
    col = np.asarray(new_column, dtype=float)
    buffer.append(col)
    if len(buffer) > max_columns:
        buffer.pop(0)
    return buffer

def compute_full_spectrogram(iq_signal, n_fft=256, hop_length=None, window_fn=np.hanning):
    """
    Compute a full spectrogram matrix from a long IQ stream.

    Parameters
    ----------
    iq_signal : 1D np.ndarray of complex
        Entire continuous IQ sequence.
    n_fft : int
        FFT size.
    hop_length : int or None
        Number of samples to step between successive frames.  
        If None, defaults to n_fft//2 (50% overlap).
    window_fn : callable
        Window function (default: Hann).

    Returns
    -------
    S : 2D np.ndarray float
        Spectrogram with shape (n_fft//2 + 1, num_frames).
    """
    if hop_length is None:
        hop_length = n_fft // 2

    window = window_fn(n_fft)
    num_frames = 1 + (len(iq_signal) - n_fft) // hop_length
    S = np.empty((n_fft//2 + 1, num_frames), dtype=float)

    for i in range(num_frames):
        start = i * hop_length
        frame = iq_signal[start : start + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)), mode='constant')
        windowed = frame * window
        spectrum = np.fft.rfft(windowed, n_fft)
        S[:, i] = np.abs(spectrum)

    return S

def get_default_pluto_uri() -> str:
    """
    Runs `iio_info -s` to list all IIO contexts, extracts URIs from
    bracketed fields, and returns the first USB URI or falls back to IP.
    """
    try:
        output = subprocess.check_output(
            ["iio_info", "-s"],
            stderr=subprocess.DEVNULL,
            text=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(
            "Failed to run `iio_info -s`. Is libiio installed and in PATH?"
        ) from e

    print("iio_info -s output:\n", output)  # for diagnostics

    uris = []
    # Find all bracketed groups like [ip:pluto.local, usb:1.24.5]
    for bracket_group in re.findall(r"\[([^\]]+)\]", output):
        # Split on commas, strip whitespace
        for token in bracket_group.split(","):
            tok = token.strip()
            # Collect ip:... or usb:... tokens
            if tok.startswith("usb:") or tok.startswith("ip:"):
                uris.append(tok)

    if not uris:
        raise RuntimeError("No IIO URIs found in iio_info output.")

    # Prefer usb:, then ip:, else first
    for uri in uris:
        if uri.startswith("usb:"):
            return uri
    for uri in uris:
        if uri.startswith("ip:"):
            return uri

    return uris[0]

# ——— SDR & JSON Helpers ———
def init_sdr(uri, lo, buf_size):
    global sdr, dt
    sdr = adi.Pluto(uri)
    sdr.rx_lo            = int(lo)
    sdr.rx_buffer_size   = int(buf_size)
    sdr.rx_enabled_channels = [0]
    SR = getattr(sdr, "sample_rate", DEFAULT_SR)
    dt = 2e6 / SR

    print(f"Initialized SDR: URI={uri}, LO={lo} Hz, BufferSize={buf_size}, SampleRate={SR} S/s")
    return SR


def add_jammer_noise(samples, amp):
    real_noise = np.random.normal(0, amp, size=samples.shape)
    imag_noise = np.random.normal(0, amp, size=samples.shape)
    return samples + real_noise + 1j * imag_noise


def iq_to_json(samples, t0, scale=25):
    return [
        {"time": t0 + i * dt,
         "real": float(s.real) / scale,
         "imaginary": float(s.imag) / scale}
        for i, s in enumerate(samples)
    ]

# ——— Capture Thread ———
def capture_loop(settings):
    run_flag.set()
    while run_flag.is_set():
        #t0 = time.time_ns() / 1e9
        t0 = -33
        try:
            #samples = sdr.rx()
            #samples = np.array(samples, dtype=np.complex64)
            raw = sdr.rx()   # may be object dtype
            # reconstruct a true complex64 array
            real = np.fromiter((float(s.real) for s in raw), dtype=np.float32, count=len(raw))
            imag = np.fromiter((float(s.imag) for s in raw), dtype=np.float32, count=len(raw))
            samples = real + 1j * imag

            # — spectrogram bookkeeping —
            col = compute_spectrogram_column(samples)
            # pass the global spec_buffer plus the new column
            update_spectrogram_buffer(spec_buffer, col)

        except Exception as e:
            print("SDR capture error:", e)
            break

        if settings["jammer_on"]:
            samples = add_jammer_noise(samples, settings["jammer_amp"])

        payload = iq_to_json(samples, t0)
        try:
            r = requests.post(WEBHOOK_URL, json=payload, headers=HEADERS, timeout=5)
            r.raise_for_status()
            print(f"[{time.strftime('%H:%M:%S')}] Sent {len(payload)} samples")
        except Exception as e:
            print("POST error:", e)

        time.sleep(settings["interval"])

def cleanup_sdr():
    global sdr
    # Destroy any existing RX buffer
    try:
        sdr._rx_destroy_buffer()
    except Exception:
        pass
    # Close the IIO context
    try:
        sdr._ctx.close()
    except Exception:
        pass
    # Remove the reference so garbage‑collection can finalize
    sdr = None

# ——— GUI Setup ———
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PlutoSDR IQ Streamer")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Settings dict for thread to read
        self.settings = {
            "uri": DEFAULT_URI,
            "lo_freq": DEFAULT_LO_FREQ,
            "buf_size": DEFAULT_BUF_SIZE,
            "interval": DEFAULT_INTERVAL,
            "jammer_on": False,
            "jammer_amp": DEFAULT_JAMMER_AMP
        }
        self.thread = None

        self._build_widgets()
        #init_sdr(self.settings["uri"],
        #         self.settings["lo_freq"],
        #         self.settings["buf_size"])

    def _build_widgets(self):
        pad = {"padx": 5, "pady": 3}

        # SDR URI
        ttk.Label(self, text="SDR URI:").grid(row=0, column=0, **pad, sticky="w")
        self.uri_var = tk.StringVar(value=self.settings["uri"])
        ttk.Entry(self, textvariable=self.uri_var, width=30).grid(row=0, column=1, **pad)

        # LO frequency
        ttk.Label(self, text="LO Frequency (Hz):").grid(row=1, column=0, **pad, sticky="w")
        self.lo_var = tk.DoubleVar(value=self.settings["lo_freq"])
        ttk.Entry(self, textvariable=self.lo_var, width=30).grid(row=1, column=1, **pad)

        # Buffer size
        ttk.Label(self, text="Buffer Size:").grid(row=2, column=0, **pad, sticky="w")
        self.buf_var = tk.IntVar(value=self.settings["buf_size"])
        ttk.Entry(self, textvariable=self.buf_var, width=30).grid(row=2, column=1, **pad)

        # Interval
        ttk.Label(self, text="Interval (s):").grid(row=3, column=0, **pad, sticky="w")
        self.int_var = tk.DoubleVar(value=self.settings["interval"])
        ttk.Entry(self, textvariable=self.int_var, width=30).grid(row=3, column=1, **pad)

        # Jammer toggle
        self.jam_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(self, text="Enable Jammer", variable=self.jam_var).grid(row=4, column=0, **pad, sticky="w")

        # Jammer amplitude
        ttk.Label(self, text="Jammer Amp:").grid(row=5, column=0, **pad, sticky="w")
        self.jam_amp_var = tk.DoubleVar(value=self.settings["jammer_amp"])
        ttk.Entry(self, textvariable=self.jam_amp_var, width=30).grid(row=5, column=1, **pad)

        # Control buttons
        self.start_btn = ttk.Button(self, text="Start Streaming", command=self.start_stream)
        self.start_btn.grid(row=6, column=0, **pad)
        self.stop_btn = ttk.Button(self, text="Stop Streaming", command=self.stop_stream, state="disabled")
        self.stop_btn.grid(row=6, column=1, **pad)

        # Spectrogram button
        self.spec_btn = ttk.Button(self, text="Show Spectrogram", command=self.show_spectrogram)
        self.spec_btn.grid(row=7, column=0, columnspan=2, **pad)

    def start_stream(self):
        # BEFORE re‑init SDR, make sure any old one is torn down
        if sdr is not None:
            cleanup_sdr()

        # apply settings & reinit
        self.settings.update({
            "uri":       self.uri_var.get(),
            "lo_freq":   self.lo_var.get(),
            "buf_size":  self.buf_var.get(),
            "interval":  self.int_var.get(),
            "jammer_on": self.jam_var.get(),
            "jammer_amp":self.jam_amp_var.get()
        })
        SR = init_sdr(
            self.settings["uri"],
            self.settings["lo_freq"],
            self.settings["buf_size"]
        )
        self.settings["sample_rate"] = SR

        # launch the thread
        self.thread = threading.Thread(
            target=capture_loop,
            args=(self.settings,),
            daemon=True
        )
        self.thread.start()
        self.start_btn["state"] = "disabled"
        self.stop_btn["state"]  = "normal"

    def stop_stream(self):
        # 1) stop capture thread
        run_flag.clear()
        if self.thread:
            self.thread.join(timeout=1)

        # 2) clean up the SDR so it frees the USB/iio device
        cleanup_sdr()

        # 3) toggle buttons
        self.start_btn["state"] = "normal"
        self.stop_btn["state"]  = "disabled"

    def on_close(self):
        if self.thread and self.thread.is_alive():
            if messagebox.askyesno("Exit", "Stop streaming and exit?"):
                self.stop_stream()
            else:
                return
        self.destroy()

    def show_spectrogram(self):
        # Create Toplevel window
        self.spec_win = tk.Toplevel(self)
        self.spec_win.title("Live Spectrogram")
        # Matplotlib Figure and Axes
        fig, ax = plt.subplots(figsize=(6, 4))

        sr = self.settings.get("sample_rate", DEFAULT_SR)
        extent = [0, SPEC_MAXCOLS * self.settings["interval"],
              -sr/2/1e6, sr/2/1e6]          # seconds , MHz

        self.spec_img = ax.imshow(
            np.zeros((SPEC_NFFT, SPEC_MAXCOLS)),   # <-- full FFT height
            cmap="viridis",          # or "plasma", "inferno", etc.
            aspect="auto",
            origin="lower",
            extent=extent
        )

        # NEW — add color‑bar
        cbar = plt.colorbar(self.spec_img, ax=ax)
        cbar.set_label("Magnitude [dB]")
        self.spec_cbar = cbar            # save handle for updates

        ax.set_xlabel("Time [s]")
        ax.set_ylabel("Frequency [MHz]")

        self.spec_ax = ax

        fig.tight_layout()

        # Embed in Tk
        canvas = FigureCanvasTkAgg(fig, master=self.spec_win)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        canvas.draw()
        # Start periodic update
        self._update_spectrogram(canvas, ax)
    
    def _update_spectrogram(self, canvas, ax):
        if getattr(self, "spec_win", None) and self.spec_win.winfo_exists():

            if spec_buffer:
                S = np.stack(spec_buffer, axis=1)            # linear mags
                S_dB = 20 * np.log10(S + 1e-12)             # convert to dB

                cols = S_dB.shape[1]
                sr   = self.settings.get("sample_rate", DEFAULT_SR)

                # 20 log10 + clim code unchanged …

                # Update extent so axes rescale
                new_extent = [0,
                              cols * self.settings["interval"],
                              -sr/2/1e6,
                              sr/2/1e6]
                self.spec_img.set_extent(new_extent)
                self.spec_ax.set_xlim(new_extent[0], new_extent[1])
                self.spec_ax.set_ylim(new_extent[2], new_extent[3])
               
                # update image
                self.spec_img.set_data(S_dB)

                # robust auto‑scaling: 5th‑95th percentile
                vmin = np.percentile(S_dB, 5)
                vmax = np.percentile(S_dB, 95)
                self.spec_img.set_clim(vmin=vmin, vmax=vmax)
                
                # tell the color‑bar to pick up the new limits
                self.spec_cbar.update_normal(self.spec_img)                # update axes

            canvas.draw_idle()
            # schedule next refresh
            self.spec_win.after(200, lambda: self._update_spectrogram(canvas, ax))

if __name__ == "__main__":
    DEFAULT_URI = get_default_pluto_uri()
    App().mainloop()

