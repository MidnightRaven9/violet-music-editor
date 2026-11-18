// Violet Music Editor — player UI (styled after Song Player)

const API = "";
const state = {
  file: null,
  originalUrl: null,
  effects: {},
  effect: "nightcore",
  jobId: null,
  isPlaying: false,
  duration: 0,
  volume: 1,
  muted: false,
  tempo: 1,
  resultUrl: null,       // generated remix URL (when ready)
  trimStart: 0,          // trim boundaries in original-file seconds
  trimEnd: 0,
  peaks: [],
};

const $ = (id) => document.getElementById(id);

let audio, ctx, source, analyser, masterGain, rafId;

const MUSICAL_KEYS = [
  'Original', 'C Major', 'C Minor', 'C# Major', 'C# Minor',
  'D Major', 'D Minor', 'D# Major', 'D# Minor', 'E Major', 'E Minor',
  'F Major', 'F Minor', 'F# Major', 'F# Minor', 'G Major', 'G Minor',
  'G# Major', 'G# Minor', 'A Major', 'A Minor', 'A# Major', 'A# Minor',
  'B Major', 'B Minor'
];

const EFFECT_COLORS = {
  original:       ['#a855f7', '#c084fc', '#e879f9', '#a855f7'],
  nightcore:      ['#DE25F4', '#9332A5', '#813DB0', '#153CB4'],
  slowed_reverb:  ['#4A91F2', '#8874A3', '#3D1E6D', '#2E003E'],
  bass_boost:     ['#FF003C', '#3D0066', '#0A0A0C', '#222226'],
  echo:           ['#8B5CF6', '#6D28D9', '#4C1D95', '#1E1B4B'],
  reverb:         ['#38BDF8', '#6366F1', '#7C3AED', '#312E81'],
  chroma:         ['#34D399', '#10B981', '#047857', '#064E3B'],
  distortion:     ['#F97316', '#DC2626', '#7F1D1D', '#1C1917'],
  phaser:         ['#22D3EE', '#0EA5E9', '#4338CA', '#1E1B4B'],
  bitcrush:       ['#FACC15', '#F59E0B', '#B45309', '#451A03'],
  glitchcore:     ['#F472B6', '#A855F7', '#6366F1', '#0F172A'],
  house:          ['#FBBF24', '#F59E0B', '#B45309', '#1C1917'],
  techno:         ['#EF4444', '#991B1B', '#450A0A', '#0A0A0A'],
  trance:         ['#38BDF8', '#818CF8', '#C084FC', '#312E81'],
  dubstep:        ['#F43F5E', '#BE123C', '#6B21A8', '#0F172A'],
  trap:           ['#A78BFA', '#7C3AED', '#4C1D95', '#0A0A0A'],
  drum_and_bass:  ['#FACC15', '#F97316', '#DC2626', '#450A0A'],
  future_bass:    ['#F9A8D4', '#C084FC', '#818CF8', '#312E81'],
  custom:         ['#a855f7', '#c084fc', '#e879f9', '#a855f7'],
};

function hexToRgb(hex) {
  const r = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return r ? { r: parseInt(r[1], 16), g: parseInt(r[2], 16), b: parseInt(r[3], 16) } : { r: 0, g: 0, b: 0 };
}
function interpolate(a, b, f) {
  const c1 = hexToRgb(a), c2 = hexToRgb(b);
  return `rgb(${Math.round(c1.r + f*(c2.r-c1.r))}, ${Math.round(c1.g + f*(c2.g-c1.g))}, ${Math.round(c1.b + f*(c2.b-c1.b))})`;
}

async function init() {
  audio = $("audio");
  try {
    const r = await fetch(`${API}/api/effects`);
    state.effects = await r.json();
    state.effect = state.effects.nightcore ? "nightcore" : Object.keys(state.effects)[0];
  } catch (e) { console.warn("effects load failed", e); }

  buildPills();
  const keySel = $("musicalKey");
  MUSICAL_KEYS.forEach(k => {
    const o = document.createElement("option");
    o.value = k; o.textContent = k; keySel.appendChild(o);
  });

  wireEvents();
  aiStatus();
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch(() => {});
  }
}

function buildPills() {
  const wrap = $("pills");
  wrap.innerHTML = "";
  const names = ["original", ...Object.keys(state.effects)];
  names.forEach((id) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pill" + (id === state.effect ? " active" : "");
    btn.dataset.effect = id;
    const label = id === "original" ? "Original" : (state.effects[id]?.label || id);
    btn.textContent = label;
    btn.addEventListener("click", () => selectEffect(id));
    wrap.appendChild(btn);
  });
}

function wireEvents() {
  $("fileInput").addEventListener("change", (e) => {
    if (e.target.files.length) handleFile(e.target.files[0]);
  });

  $("playBtn").addEventListener("click", togglePlay);
  audio.addEventListener("timeupdate", onTime);
  audio.addEventListener("loadedmetadata", onTime);
  audio.addEventListener("ended", () => { state.isPlaying = false; updatePlayIcon(); });

  $("seek").addEventListener("input", (e) => {
    if (audio.duration) { audio.currentTime = Number(e.target.value); }
  });

  $("volume").addEventListener("input", (e) => {
    state.volume = Number(e.target.value);
    if (state.volume > 0) state.muted = false;
    applyVolume();
  });
  $("muteBtn").addEventListener("click", () => { state.muted = !state.muted; applyVolume(); });

  $("tempo").addEventListener("input", (e) => {
    state.tempo = Number(e.target.value);
    $("tempoVal").textContent = Math.round(state.tempo * 100) + "%";
    applyPlaybackRate();
  });

  $("musicalKey").addEventListener("change", () => { /* used on generation */ });

  $("downloadBtn").addEventListener("click", generateAndDownload);
  $("trimStart").addEventListener("input", onTrimStart);
  $("trimEnd").addEventListener("input", onTrimEnd);
  $("trimReset").addEventListener("click", resetTrim);
  $("playTrim").addEventListener("click", playTrimmed);
  document.querySelectorAll("[data-quick]").forEach((b) => {
    b.addEventListener("click", () => quickTrim(b.dataset.quick));
  });
  $("aiBtn").addEventListener("click", aiRestyle);
  $("aiDuration").addEventListener("input", (e) => { $("aiDurVal").textContent = e.target.value + "s"; });
  $("differentTrack").addEventListener("click", resetTrack);
  $("editTagsBtn").addEventListener("click", openTags);
  $("saveTags").addEventListener("click", saveTags);

  document.querySelectorAll("[data-close]").forEach((b) => {
    b.addEventListener("click", () => $(b.dataset.close).classList.add("hidden"));
  });
}

function applyVolume() {
  const v = state.muted ? 0 : state.volume;
  audio.volume = v;
  if (masterGain && ctx) masterGain.gain.setTargetAtTime(v, ctx.currentTime, 0.05);
  $("volVal").textContent = state.muted || state.volume === 0 ? "Muted" : Math.round(state.volume * 100) + "%";
  const icon = state.muted || state.volume === 0 ? "i-volx" : (state.volume < 0.5 ? "i-vol1" : "i-vol2");
  $("volIcon").innerHTML = `<use href="#${icon}"/>`;
  $("volIcon").style.color = state.muted || state.volume === 0 ? "var(--danger)" : "var(--muted)";
}

function applyPlaybackRate() {
  // Live preview: the effect's speed × the user's tempo slider.
  // (The rendered MP3 uses professional time-stretch on the backend.)
  const meta = state.effects[state.effect] || { rate: 1 };
  const rate = state.resultUrl ? 1 : (meta.rate || 1);
  audio.playbackRate = Math.max(0.25, Math.min(2.5, rate * state.tempo));
}

async function extractPeaks(file, numBars) {
  try {
    const buf = await file.arrayBuffer();
    const AC = window.AudioContext || window.webkitAudioContext;
    const c = new AC();
    const decoded = await c.decodeAudioData(buf);
    c.close();
    const ch = decoded.getChannelData(0);
    const step = Math.floor(ch.length / numBars);
    const peaks = [];
    for (let i = 0; i < numBars; i++) {
      let max = 0;
      const end = Math.min(i * step + step, ch.length);
      for (let j = i * step; j < end; j += 8) {
        const v = Math.abs(ch[j] || 0);
        if (v > max) max = v;
      }
      peaks.push(max);
    }
    const m = Math.max(...peaks, 0.01);
    return peaks.map(p => Math.max(0.08, p / m));
  } catch (e) {
    return Array.from({ length: numBars }, (_, i) =>
      Math.max(0.1, 0.2 + 0.6 * Math.abs(Math.sin(i * 0.12) * Math.cos(i * 0.05))));
  }
}

function renderPeaks() {
  const wrap = $("waveBars");
  wrap.innerHTML = "";
  state.peaks.forEach((p) => {
    const bar = document.createElement("div");
    bar.className = "wave-bar";
    bar.style.height = Math.max(8, p * 88) + "%";
    wrap.appendChild(bar);
  });
}

function updateTrimUI() {
  const dur = state.duration || 0;
  const end = state.trimEnd > 0 ? state.trimEnd : dur;
  const startPct = dur ? (state.trimStart / dur) * 100 : 0;
  const endPct = dur ? (end / dur) * 100 : 100;
  const playPct = dur ? Math.min(100, (audio.currentTime / dur) * 100) : 0;

  $("waveDimLeft").style.width = startPct + "%";
  $("waveDimRight").style.width = (100 - endPct) + "%";
  const sel = $("waveSelect");
  sel.style.left = startPct + "%";
  sel.style.width = Math.max(0, endPct - startPct) + "%";
  $("wavePlayhead").style.left = playPct + "%";

  // Color bars by selection/played state
  const bars = $("waveBars").children;
  for (let i = 0; i < bars.length; i++) {
    const pos = (i / bars.length) * 100;
    const selected = pos >= startPct && pos <= endPct;
    const played = pos <= playPct;
    bars[i].className = "wave-bar" + (selected ? (played ? " played" : " sel") : "");
  }

  $("trimStartTime").textContent = fmt(state.trimStart);
  $("trimEndTime").textContent = fmt(end);
  $("trimRange").textContent = `Range: ${fmt(state.trimStart)} - ${fmt(end)} (${fmt(Math.max(0, end - state.trimStart))})`;
  $("trimReset").classList.toggle("hidden", state.trimStart <= 0 && end >= dur);
}

function onTrimStart(e) {
  const dur = state.duration || 0;
  const end = state.trimEnd > 0 ? state.trimEnd : dur;
  state.trimStart = Math.min(Number(e.target.value), end - 0.5);
  if (state.trimStart < 0) state.trimStart = 0;
  $("trimStart").value = state.trimStart;
  updateTrimUI();
}

function onTrimEnd(e) {
  const dur = state.duration || 0;
  state.trimEnd = Math.max(Number(e.target.value), state.trimStart + 0.5);
  if (state.trimEnd > dur) state.trimEnd = dur;
  $("trimEnd").value = state.trimEnd;
  updateTrimUI();
}

function resetTrim() {
  state.trimStart = 0;
  state.trimEnd = 0;
  $("trimStart").value = 0;
  $("trimEnd").value = state.duration || 100;
  updateTrimUI();
}

function quickTrim(type) {
  const dur = state.duration || 0;
  if (type === "first30") { state.trimStart = 0; state.trimEnd = Math.min(30, dur); }
  else if (type === "last30") { state.trimStart = Math.max(0, dur - 30); state.trimEnd = dur; }
  else if (type === "middle") { const h = dur / 2; state.trimStart = Math.max(0, h - 15); state.trimEnd = Math.min(dur, h + 15); }
  $("trimStart").value = state.trimStart;
  $("trimEnd").value = state.trimEnd;
  updateTrimUI();
}

function playTrimmed() {
  initAudioGraph();
  if (ctx && ctx.state === "suspended") ctx.resume();
  if (audio) {
    audio.currentTime = state.trimStart;
    if (!state.isPlaying) togglePlay();
  }
}

async function handleFile(file) {
  state.file = file;
  if (state.originalUrl) URL.revokeObjectURL(state.originalUrl);
  state.originalUrl = URL.createObjectURL(file);
  state.jobId = null;
  state.resultUrl = null;
  state.duration = 0;
  state.tempo = 1;
  state.trimStart = 0;
  state.trimEnd = 0;
  $("tempo").value = 1;
  $("tempoVal").textContent = "100%";

  audio.src = state.originalUrl;
  audio.load();
  state.isPlaying = false;
  updatePlayIcon();

  const name = file.name.replace(/\.[^/.]+$/, "");
  let title = name, artist = "Unknown Artist", album = "";
  const dash = name.split(" - ");
  if (dash.length >= 2) { artist = dash[0].trim(); title = dash.slice(1).join(" - ").trim(); }
  state.title = title; state.artist = artist; state.album = album;
  $("fileName").textContent = file.name;
  $("trackTitle").textContent = title;
  $("artistName").textContent = artist;
  $("albumName").textContent = album;

  $("uploadArea").classList.add("hidden");
  $("player").classList.remove("hidden");
  $("trimmer").classList.remove("hidden");
  setStatus("", false);
  buildPills();
  applyPlaybackRate();

  // Extract waveform peaks for the trimmer
  state.peaks = await extractPeaks(file, 90);
  renderPeaks();
  $("trimStart").max = 100;
  $("trimEnd").max = 100;
  $("trimEnd").value = 100;
}

function selectEffect(id) {
  state.effect = id;
  document.querySelectorAll(".pill").forEach(p => p.classList.toggle("active", p.dataset.effect === id));
  // Preview: switch back to the original source with the new effect speed.
  if (state.originalUrl) {
    state.resultUrl = null;
    audio.src = state.originalUrl;
    audio.load();
    state.isPlaying = false;
    updatePlayIcon();
  }
  applyPlaybackRate();
}

function initAudioGraph() {
  if (ctx) return;
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return;
  ctx = new AC();
  source = ctx.createMediaElementSource(audio);
  analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  masterGain = ctx.createGain();
  masterGain.gain.value = state.muted ? 0 : state.volume;
  source.connect(analyser);
  analyser.connect(masterGain);
  masterGain.connect(ctx.destination);
}

function togglePlay() {
  if (!state.file) return;
  initAudioGraph();
  if (ctx && ctx.state === "suspended") ctx.resume();
  if (state.isPlaying) {
    audio.pause();
  } else {
    audio.play().catch(() => {});
  }
  state.isPlaying = !state.isPlaying;
  updatePlayIcon();
  $("vizRing").classList.toggle("playing", state.isPlaying);
  if (state.isPlaying) drawVisualizer(); else if (rafId) cancelAnimationFrame(rafId);
}

function updatePlayIcon() {
  $("playIcon").innerHTML = `<use href="#${state.isPlaying ? "i-pause" : "i-play"}"/>`;
  $("vizRing").classList.toggle("playing", state.isPlaying);
  if (!state.isPlaying && rafId) { cancelAnimationFrame(rafId); rafId = null; }
}

function onTime() {
  if (!audio) return;
  const cur = audio.currentTime, dur = audio.duration;
  if (dur && !isNaN(dur)) {
    if (state.duration !== dur) {
      state.duration = dur;
      $("trimStart").max = dur;
      $("trimEnd").max = dur;
      if (state.trimEnd === 0 || state.trimEnd > dur) state.trimEnd = dur;
      $("trimEnd").value = state.trimEnd;
    }
    $("durTime").textContent = fmt(dur);
    $("seek").max = dur;
    $("seek").value = cur;
    // Enforce trim end boundary during playback
    const activeEnd = state.trimEnd > 0 ? state.trimEnd : dur;
    if (state.isPlaying && cur >= activeEnd) {
      audio.pause();
      audio.currentTime = state.trimStart;
      state.isPlaying = false;
      updatePlayIcon();
    }
  }
  $("curTime").textContent = fmt(cur);
  updateTrimUI();
}

function fmt(t) {
  if (isNaN(t)) return "0:00";
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function drawVisualizer() {
  if (!analyser) return;
  const canvas = $("viz"), c = canvas.getContext("2d");
  const buf = new Uint8Array(analyser.frequencyBinCount);
  const colors = EFFECT_COLORS[state.effect] || EFFECT_COLORS.original;
  const n = colors.length;
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2, radius = 82;

  const frame = () => {
    analyser.getByteFrequencyData(buf);
    c.clearRect(0, 0, w, h);
    let bass = 0, mid = 0;
    for (let i = 0; i < 10; i++) bass += buf[i];
    for (let i = 10; i < 50; i++) mid += buf[i];
    const offset = ((bass / 10) + (mid / 40)) / 510;
    const bars = 60, step = Math.PI * 2 / bars;
    c.lineWidth = 3;
    for (let i = 0; i < bars; i++) {
      const idx = Math.floor((i / bars) * (buf.length * 0.6));
      const barH = (buf[idx] / 255) * 28;
      const ang = i * step;
      const x1 = cx + Math.cos(ang) * radius, y1 = cy + Math.sin(ang) * radius;
      const x2 = cx + Math.cos(ang) * (radius + barH), y2 = cy + Math.sin(ang) * (radius + barH);
      const pos = (i / bars + offset) * n;
      const ci = Math.floor(pos) % n, ni = (ci + 1) % n;
      c.strokeStyle = interpolate(colors[ci], colors[ni], pos - Math.floor(pos));
      c.lineCap = "round";
      c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
    }
    if (state.isPlaying) rafId = requestAnimationFrame(frame);
  };
  frame();
}

function setStatus(text, error) {
  const el = $("status");
  if (!text) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  el.classList.toggle("error", !!error);
  $("statusText").textContent = text;
  $("statusSpin").style.display = error ? "none" : "block";
}

function keyToSemitones(key) {
  if (!key || key === "Original") return 0;
  const map = { "C":0, "C#":1, "D":2, "D#":3, "E":4, "F":5, "F#":6, "G":7, "G#":8, "A":9, "A#":10, "B":11 };
  const root = key.split(" ")[0];
  return map[root] ?? 0;
}

async function generateAndDownload() {
  if (!state.file) return;
  if (state.effect === "original") {
    openExport(state.originalUrl, state.file.name);
    return;
  }
  if (state.resultUrl) { openExport(state.resultUrl, `${state.title}_${state.effect}.mp3`); return; }

  const meta = state.effects[state.effect] || { rate: 1, pitch: 0, reverb: 0 };
  const form = new FormData();
  form.append("file", state.file);
  form.append("effect", state.effect);
  form.append("rate", String(meta.rate || 1));
  form.append("pitch", String((meta.pitch || 0) + keyToSemitones($("musicalKey").value)));
  form.append("reverb", String(meta.reverb || 0));
  form.append("trim_start", String(state.trimStart || 0));
  form.append("trim_end", String(state.trimEnd || 0));

  $("downloadBtn").disabled = true;
  setStatus("Generating professional remix…", false);
  try {
    const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.jobId = data.job_id;
    pollJob(false);
  } catch (err) {
    setStatus(err.message || "Upload failed", true);
    $("downloadBtn").disabled = false;
  }
}

async function aiRestyle() {
  if (!state.file) return;
  const form = new FormData();
  form.append("file", state.file);
  form.append("style", $("aiStyle").value);
  form.append("duration", $("aiDuration").value);
  $("aiBtn").disabled = true;
  setStatus("Sending to AI engine…", false);
  try {
    const res = await fetch(`${API}/api/ai-restyle`, { method: "POST", body: form });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    state.jobId = data.job_id;
    pollJob(true);
  } catch (err) {
    setStatus(err.message || "AI restyle failed", true);
  } finally {
    $("aiBtn").disabled = false;
  }
}

async function pollJob(isAI) {
  if (!state.jobId) return;
  try {
    const res = await fetch(`${API}/api/jobs/${state.jobId}`);
    const job = await res.json();
    if (job.status === "processing" || job.status === "uploaded") {
      setStatus(`${job.message} (${job.progress || 0}%)`, false);
      setTimeout(() => pollJob(isAI), 1200);
      return;
    }
    if (job.status === "done") {
      setStatus("", false);
      const url = `${API}/api/download/${state.jobId}?t=${Date.now()}`;
      state.resultUrl = url;
      audio.src = url;
      audio.load();
      applyPlaybackRate();
      $("downloadBtn").disabled = false;
      openExport(url, `${state.title}_${isAI ? "ai_restyle" : state.effect}.mp3`);
      return;
    }
    if (job.status === "error") {
      setStatus(`Error: ${job.message}`, true);
      $("downloadBtn").disabled = false;
      return;
    }
    setTimeout(() => pollJob(isAI), 1200);
  } catch (e) {
    setStatus("Error checking status", true);
    $("downloadBtn").disabled = false;
  }
}

function openExport(url, filename) {
  $("exportAudio").src = url;
  $("exportFile").textContent = filename;
  const a = $("saveAudio");
  a.href = url;
  a.download = filename;
  $("exportModal").classList.remove("hidden");
}

async function aiStatus() {
  try {
    const r = await fetch(`${API}/api/ai-status`);
    const s = await r.json();
    $("aiHint").textContent = s.connected ? "🟢 Engine connected." : "⚪ Engine not connected — set AI_ENGINE_URL on the app server.";
  } catch (e) { $("aiHint").textContent = "⚪ Engine status unavailable."; }
}

function openTags() {
  $("editTitle").value = state.title || "";
  $("editArtist").value = state.artist || "";
  $("editAlbum").value = state.album || "";
  $("tagModal").classList.remove("hidden");
}
function saveTags() {
  state.title = $("editTitle").value.trim() || state.title;
  state.artist = $("editArtist").value.trim() || state.artist;
  state.album = $("editAlbum").value.trim();
  $("trackTitle").textContent = state.title;
  $("artistName").textContent = state.artist;
  $("albumName").textContent = state.album;
  $("tagModal").classList.add("hidden");
}

function resetTrack() {
  if (ctx && ctx.state === "running") ctx.suspend();
  if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  state.isPlaying = false;
  state.file = null;
  state.jobId = null;
  state.resultUrl = null;
  state.trimStart = 0;
  state.trimEnd = 0;
  if (state.originalUrl) { URL.revokeObjectURL(state.originalUrl); state.originalUrl = null; }
  audio.src = "";
  $("player").classList.add("hidden");
  $("trimmer").classList.add("hidden");
  $("uploadArea").classList.remove("hidden");
  $("exportModal").classList.add("hidden");
  $("fileInput").value = "";
}

init();
