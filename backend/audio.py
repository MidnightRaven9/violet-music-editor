"""Professional audio processing for Violet Music Editor.

Pipeline:
  FFmpeg decode -> RubberBand time-stretch/pitch-shift (studio grade)
  -> pedalboard effect chain -> mastering chain (HPF, comp, EQ, limiter)
  -> peak normalization -> FFmpeg encode MP3 (high quality VBR)

RubberBand is a phase-locked time-stretcher used in professional DAWs. It
avoids the warbling artifacts of librosa's phase vocoder, and runs as a
streaming C++ subprocess so phone memory stays low and stereo is preserved.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf
from pedalboard import (
    Pedalboard,
    Reverb,
    LowShelfFilter,
    HighShelfFilter,
    LowpassFilter,
    HighpassFilter,
    PeakFilter,
    Delay,
    Gain,
    Compressor,
    Limiter,
    Chorus,
    Distortion,
    Phaser,
    Bitcrush,
)

FFMPEG = "ffmpeg"
RUBBERBAND = "rubberband"

MAX_DURATION_SECONDS = 300  # 5 minutes


def run_command(cmd: list[str], label: str) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{label} failed: {result.stderr.strip()}")


def decode_to_wav(input_path: str, output_path: str) -> None:
    """Decode any audio file to 44.1kHz PCM WAV, preserving stereo."""
    run_command([
        FFMPEG, "-y", "-i", input_path,
        "-acodec", "pcm_s16le", "-ar", "44100",
        output_path,
    ], "decode")


def encode_to_mp3(input_path: str, output_path: str) -> None:
    """Encode WAV to high-quality VBR MP3 (~245 kbps)."""
    run_command([
        FFMPEG, "-y", "-i", input_path,
        "-c:a", "libmp3lame", "-q:a", "0",
        output_path,
    ], "encode")


def rubberband_time_pitch(input_wav: str, output_wav: str, rate: float, pitch: float) -> None:
    """Apply tempo + pitch changes with RubberBand's R2 engine.

    rate: tempo multiplier (1.3 = 30% faster, 0.8 = 20% slower)
    pitch: semitone offset (-positive = higher, classic nightcore)
    """
    cmd = [RUBBERBAND, "--crisp", "5", "--tempo", f"{rate:.4f}"]
    if pitch != 0:
        cmd += ["--pitch", f"{pitch:.2f}"]
    cmd += [input_wav, output_wav]
    run_command(cmd, "time-stretch")


def _build_effect_board(effect: str, reverb_wet: float) -> Pedalboard:
    """Effect-specific processing chain (applied before mastering)."""
    if effect == "slowed_reverb":
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=120, gain_db=3.0),
            LowpassFilter(cutoff_frequency_hz=12000),
            Reverb(room_size=0.85, damping=0.7,
                   wet_level=reverb_wet, dry_level=max(0.0, 1.0 - reverb_wet)),
        ])
    if effect == "reverb":
        return Pedalboard([
            Reverb(room_size=0.7, damping=0.6,
                   wet_level=reverb_wet, dry_level=max(0.0, 1.0 - reverb_wet)),
        ])
    if effect == "bass_boost":
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=30),
            LowShelfFilter(cutoff_frequency_hz=100, gain_db=8.0),
        ])
    if effect == "echo":
        return Pedalboard([
            Delay(delay_seconds=0.3, feedback=0.4, mix=0.35),
        ])
    if effect == "chroma":
        return Pedalboard([
            Chorus(rate_hz=0.5, depth=0.3, centre_delay_ms=7.0,
                   feedback=0.25, mix=0.3),
        ])
    if effect == "distortion":
        return Pedalboard([
            Distortion(drive_db=6.0),
            LowpassFilter(cutoff_frequency_hz=9000),
        ])
    if effect == "phaser":
        return Pedalboard([
            Phaser(rate_hz=0.3, depth=0.5, centre_frequency_hz=1300.0,
                   feedback=0.3, mix=0.3),
        ])
    if effect == "bitcrush":
        return Pedalboard([
            Bitcrush(bit_depth=6),
        ])
    if effect == "glitchcore":
        return Pedalboard([
            Bitcrush(bit_depth=6),
            Distortion(drive_db=3.0),
            Reverb(room_size=0.5, damping=0.5, wet_level=0.15, dry_level=0.85),
        ])

    # --- Song Player classics -------------------------------------------------
    if effect == "daycore":
        # Slowed + pitched down, dreamy
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=140, gain_db=3.0),
            LowpassFilter(cutoff_frequency_hz=11000),
            Reverb(room_size=0.7, damping=0.6, wet_level=0.35, dry_level=0.65),
        ])
    if effect == "vaporwave":
        # Heavy reverb, compressed, dusty lo-fi low-pass
        return Pedalboard([
            LowpassFilter(cutoff_frequency_hz=6000),
            Compressor(threshold_db=-30, ratio=6.0, attack_ms=5, release_ms=150),
            Reverb(room_size=0.9, damping=0.55, wet_level=0.6, dry_level=0.4),
        ])
    if effect == "nightcore_reverse":
        # Slowed + pitched down with a touch of space
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=160, gain_db=2.5),
            Reverb(room_size=0.55, damping=0.6, wet_level=0.3, dry_level=0.7),
        ])
    if effect == "lofi":
        # Mellow tape-like warmth: low-pass, bitcrush, gentle hiss handled via EQ
        return Pedalboard([
            LowpassFilter(cutoff_frequency_hz=2800),
            HighpassFilter(cutoff_frequency_hz=60),
            Bitcrush(bit_depth=8),
            LowShelfFilter(cutoff_frequency_hz=200, gain_db=2.0),
        ])
    # sped_up, nightcore, 8d: no extra coloring here
    # (8d gets its own panning stage in process_file)

    # --- EDM genre-inspired chains -------------------------------------------
    # These shape the uploaded song with each genre's sonic signature
    # (tempo, tonality, filters, dynamics). See main.py for rate/pitch defaults.
    if effect == "house":
        # Warm, clean, club-ready: rounded lows, gentle presence, light space
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=125, gain_db=3.0),
            PeakFilter(cutoff_frequency_hz=2500, gain_db=1.5, q=0.8),
            Reverb(room_size=0.35, damping=0.6, wet_level=0.12, dry_level=0.88),
        ])
    if effect == "techno":
        # Dark, driving, machine-like: tight low-pass, gritty mids, dry and punchy
        return Pedalboard([
            LowpassFilter(cutoff_frequency_hz=7000),
            LowShelfFilter(cutoff_frequency_hz=90, gain_db=4.0),
            Distortion(drive_db=2.0),
            Reverb(room_size=0.25, damping=0.7, wet_level=0.08, dry_level=0.92),
        ])
    if effect == "trance":
        # Uplifting and lush: bright air, wide chorus, long tail, echo
        return Pedalboard([
            HighShelfFilter(cutoff_frequency_hz=9000, gain_db=3.0),
            Chorus(rate_hz=0.25, depth=0.3, centre_delay_ms=8.0,
                   feedback=0.2, mix=0.25),
            Delay(delay_seconds=0.375, feedback=0.35, mix=0.2),
            Reverb(room_size=0.8, damping=0.4, wet_level=0.3, dry_level=0.7),
        ])
    if effect == "dubstep":
        # Half-time growl: massive sub, heavy saturation, dark low-pass
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=60, gain_db=10.0),
            Distortion(drive_db=10.0),
            LowpassFilter(cutoff_frequency_hz=5000),
            Compressor(threshold_db=-22, ratio=4.0, attack_ms=5, release_ms=100),
        ])
    if effect == "trap":
        # 808 sub-bass and crisp hats: deep lows, tidy low-end, bright top
        return Pedalboard([
            HighpassFilter(cutoff_frequency_hz=30),
            LowShelfFilter(cutoff_frequency_hz=55, gain_db=9.0),
            Distortion(drive_db=3.0),
            HighShelfFilter(cutoff_frequency_hz=10000, gain_db=2.0),
        ])
    if effect == "drum_and_bass":
        # Fast and aggressive: punchy dynamics, strong bass, bright edge
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=100, gain_db=5.0),
            Compressor(threshold_db=-16, ratio=3.5, attack_ms=5, release_ms=80),
            Distortion(drive_db=2.0),
            HighShelfFilter(cutoff_frequency_hz=9000, gain_db=2.0),
        ])
    if effect == "future_bass":
        # Big, bright, wobbling chords: supersaw width, air, spacious tail
        return Pedalboard([
            LowShelfFilter(cutoff_frequency_hz=100, gain_db=3.0),
            Chorus(rate_hz=0.4, depth=0.4, centre_delay_ms=9.0,
                   feedback=0.3, mix=0.35),
            PeakFilter(cutoff_frequency_hz=2500, gain_db=2.0, q=0.7),
            HighShelfFilter(cutoff_frequency_hz=8000, gain_db=3.0),
            Reverb(room_size=0.75, damping=0.5, wet_level=0.25, dry_level=0.75),
        ])

    if effect == "custom" and reverb_wet > 0:
        return Pedalboard([
            Reverb(room_size=0.6, damping=0.5,
                   wet_level=reverb_wet, dry_level=max(0.0, 1.0 - reverb_wet)),
        ])
    # nightcore / other: no extra coloring — mastering handles polish
    return Pedalboard([])


def _build_mastering_board() -> Pedalboard:
    """Gentle mastering chain: clean lows, glue compression, presence, air, limit."""
    return Pedalboard([
        HighpassFilter(cutoff_frequency_hz=25),          # remove rumble
        Compressor(threshold_db=-18, ratio=2.5,
                   attack_ms=10, release_ms=120),        # gentle glue
        LowShelfFilter(cutoff_frequency_hz=120, gain_db=2.0),  # warm low-end
        PeakFilter(cutoff_frequency_hz=3000, gain_db=2.0, q=1.0),  # presence
        HighShelfFilter(cutoff_frequency_hz=8000, gain_db=1.5),    # air
        Limiter(threshold_db=-1.5, release_ms=100),      # catch peaks
    ])


def _normalize_peak(audio: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """Normalize peak to target dBFS without over-amplifying quiet audio."""
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak <= 1e-6:
        return audio
    target_linear = 10 ** (target_db / 20.0)
    gain = min(target_linear / peak, 4.0)
    return audio * gain


def _apply_8d_panning(audio: np.ndarray, sr: int) -> np.ndarray:
    """Apply a slow circular stereo pan to a mono signal for the '8D' effect."""
    if audio.shape[0] < 2:
        mono = audio[0]
        n = mono.shape[-1]
        t = np.arange(n, dtype=np.float32) / sr
        # Constant-power pan, one full circle every 8 seconds
        angle = 2.0 * np.pi * (0.125 * t)
        left = np.sqrt(0.5 * (1.0 + np.cos(angle))) * mono
        right = np.sqrt(0.5 * (1.0 - np.cos(angle))) * mono
        return np.stack([left, right], axis=0)
    return audio


def process_file(
    input_path: str,
    output_path: str,
    effect: str,
    rate: float,
    pitch: float,
    reverb: float,
    trim_start: float = 0.0,
    trim_end: float = 0.0,
    progress_cb=None,
) -> None:
    """Full pipeline: decode -> trim -> RubberBand -> effects -> mastering -> MP3."""
    stem = str(Path(output_path).with_suffix(""))
    decoded_wav = f"{stem}_decoded.wav"
    trimmed_wav = f"{stem}_trimmed.wav"
    stretched_wav = f"{stem}_stretched.wav"
    processed_wav = f"{stem}_processed.wav"

    def cb(pct: int, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, msg)

    try:
        cb(5, "Decoding audio...")
        decode_to_wav(input_path, decoded_wav)

        # Trim the ORIGINAL audio first so trim times use the song's timeline,
        # then apply time-stretch/pitch to the trimmed clip.
        source = decoded_wav
        if trim_end > trim_start:
            cb(12, "Trimming selection...")
            audio, sr = sf.read(decoded_wav, dtype="float32")  # (frames, channels) or (frames,)
            s = int(trim_start * sr)
            e = int(trim_end * sr)
            if e > s:
                trimmed = audio[s:e]  # slice on frame axis; keeps channel dim
                sf.write(trimmed_wav, trimmed, sr, subtype="PCM_16")
                source = trimmed_wav

        if abs(rate - 1.0) > 1e-3 or abs(pitch) > 1e-3:
            cb(20, "Professional time-stretch & pitch shift...")
            rubberband_time_pitch(source, stretched_wav, rate, pitch)
            source = stretched_wav

        cb(40, "Loading audio...")
        audio, sr = sf.read(source, dtype="float32")  # (frames, channels)
        if audio.ndim == 1:
            audio = audio.reshape(1, -1)              # (channels, frames)
        else:
            audio = audio.T

        duration = audio.shape[-1] / sr
        if duration > MAX_DURATION_SECONDS:
            raise RuntimeError(
                f"Audio is {duration:.0f}s long. Max allowed is "
                f"{MAX_DURATION_SECONDS}s (5 minutes)."
            )

        cb(55, f"Applying {effect.replace('_', ' ')}...")
        effect_board = _build_effect_board(effect, reverb)
        if len(effect_board) > 0:
            audio = effect_board(audio, sr)

        # 8D Audio: circular stereo panning
        if effect == "8d":
            audio = _apply_8d_panning(audio, sr)

        cb(70, "Mastering (EQ, compression, limiting)...")
        mastering = _build_mastering_board()
        audio = mastering(audio, sr)
        audio = _normalize_peak(audio, -1.0)

        cb(85, "Encoding MP3...")
        if audio.shape[0] == 1:
            sf.write(processed_wav, audio[0], sr, subtype="PCM_16")
        else:
            sf.write(processed_wav, audio.T, sr, subtype="PCM_16")

        encode_to_mp3(processed_wav, output_path)
        cb(100, "Done")
    finally:
        for p in (decoded_wav, trimmed_wav, stretched_wav, processed_wav):
            try:
                os.remove(p)
            except OSError:
                pass
