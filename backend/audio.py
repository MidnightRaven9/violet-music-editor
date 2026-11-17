"""Audio processing for the EDM Remix Maker.

Uses FFmpeg for decode/encode, librosa for time-stretch/pitch-shift,
and pedalboard (Spotify) for reverb/EQ/delay.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from pedalboard import (
    Pedalboard,
    Reverb,
    LowShelfFilter,
    Delay,
    Gain,
    Chorus,
    Distortion,
    Phaser,
    Bitcrush,
)

FFMPEG = "ffmpeg"


def run_ffmpeg(args: list[str]) -> None:
    """Run an ffmpeg command, raising on failure."""
    result = subprocess.run(
        [FFMPEG, "-y", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.strip()}")


def decode_to_wav(input_path: str, output_path: str) -> None:
    """Convert any audio file to 44.1kHz PCM WAV."""
    run_ffmpeg([
        "-i", input_path,
        "-acodec", "pcm_s16le",
        "-ar", "44100",
        output_path,
    ])


def encode_to_mp3(input_path: str, output_path: str) -> None:
    """Encode WAV to MP3 (VBR quality ~2)."""
    run_ffmpeg([
        "-i", input_path,
        "-acodec", "libmp3lame",
        "-aq", "2",
        output_path,
    ])


def _build_board(effect: str, reverb_wet: float) -> Pedalboard:
    """Build a pedalboard chain for the given effect."""
    if effect == "slowed_reverb":
        return Pedalboard([
            Reverb(room_size=0.7, damping=0.5,
                   wet_level=reverb_wet, dry_level=max(0.0, 1.0 - reverb_wet)),
        ])
    if effect == "reverb":
        return Pedalboard([
            Reverb(room_size=0.6, damping=0.5,
                   wet_level=reverb_wet, dry_level=max(0.0, 1.0 - reverb_wet)),
        ])
    if effect == "bass_boost":
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=200, gain_db=8.0),
            Gain(gain_db=2.0),
        ])
    if effect == "echo":
        return Pedalboard([
            Delay(delay_seconds=0.3, feedback=0.4, mix=0.35),
        ])
    if effect == "chroma":
        return Pedalboard([
            Chorus(modulation_frequency_hz=0.5, depth=0.3, mix=0.3),
        ])
    if effect == "distortion":
        return Pedalboard([
            Distortion(dry_wet=0.2, gain=6.0),
        ])
    if effect == "phaser":
        return Pedalboard([
            Phaser(depth=0.5, feedback=0.3, frequency=0.3, mix=0.3),
        ])
    if effect == "bitcrush":
        return Pedalboard([
            Bitcrush(bit_depth=4),
        ])
    if effect == "glitchcore":
        return Pedalboard([
            Bitcrush(bit_depth=4),
            Gain(gain_db=3.0),
            Reverb(room_size=0.5, damping=0.5, wet_level=0.2, dry_level=0.8),
        ])
    # nightcore / custom: no pedalboard chain (librosa handles speed+pitch)
    return Pedalboard([])


def apply_effects(
    y: np.ndarray,
    sr: int,
    effect: str,
    rate: float,
    pitch: float,
    reverb: float,
) -> np.ndarray:
    """Apply the effect chain to audio.

    y shape: (channels, samples) or (samples,) for mono.
    """
    # 1) Time-stretch (changes speed, preserves pitch)
    if rate != 1.0:
        y = librosa.effects.time_stretch(y, rate=rate, n_fft=1024)

    # 2) Pitch shift (changes pitch, preserves speed) — Nightcore uses this
    if pitch != 0:
        y = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch, n_fft=1024)

    # 3) Pedalboard effects (reverb / bass / echo / modulation)
    board = _build_board(effect, reverb)
    if len(board) > 0:
        y = board(y, sr)

    return y


def process_file(
    input_path: str,
    output_path: str,
    effect: str,
    rate: float,
    pitch: float,
    reverb: float,
    progress_cb=None,
) -> None:
    """Full pipeline: decode -> process -> encode -> MP3.

    progress_cb(percent, message) is called at each stage.
    """
    stem = str(Path(output_path).with_suffix(""))
    decoded_wav = f"{stem}_decoded.wav"
    processed_wav = f"{stem}_processed.wav"

    def cb(pct: int, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, msg)

    try:
        cb(10, "Decoding audio...")
        decode_to_wav(input_path, decoded_wav)

        cb(30, "Loading audio...")
        # mono=True keeps memory low on phones; shape -> (samples,)
        y, sr = librosa.load(decoded_wav, sr=None, mono=True)

        max_duration = 300  # 5 minutes
        duration = y.shape[-1] / sr
        if duration > max_duration:
            raise RuntimeError(
                f"Audio is {duration:.0f}s long. Max allowed is {max_duration}s (5 minutes)."
            )

        cb(50, f"Applying {effect.replace('_', ' ')}...")
        y = apply_effects(y, sr, effect, rate, pitch, reverb)

        cb(70, "Encoding to MP3...")
        sf.write(processed_wav, y, sr)

        encode_to_mp3(processed_wav, output_path)

        cb(100, "Done")
    finally:
        # Clean up intermediate WAVs
        for p in (decoded_wav, processed_wav):
            try:
                os.remove(p)
            except OSError:
                pass
