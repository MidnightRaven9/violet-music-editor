// EDM Remix Maker — frontend logic

const API = ""; // same origin
const state = {
  jobId: null,
  selectedFile: null,
  selectedEffect: "nightcore",
  rate: 1.3,
  pitch: 7,
  reverb: 0.3,
};

const els = {
  fileInput: document.getElementById("fileInput"),
  uploadArea: document.getElementById("uploadArea"),
  fileName: document.getElementById("fileName"),
  effectBtns: document.querySelectorAll(".effect-btn"),
  processBtn: document.getElementById("processBtn"),
  status: document.getElementById("status"),
  statusText: document.getElementById("statusText"),
  customControls: document.getElementById("customControls"),
  rateInput: document.getElementById("rateInput"),
  rateVal: document.getElementById("rateVal"),
  pitchInput: document.getElementById("pitchInput"),
  pitchVal: document.getElementById("pitchVal"),
  reverbInput: document.getElementById("reverbInput"),
  reverbVal: document.getElementById("reverbVal"),
  resultSection: document.getElementById("resultSection"),
  originalAudio: document.getElementById("originalAudio"),
  remixAudio: document.getElementById("remixAudio"),
  downloadBtn: document.getElementById("downloadBtn"),
};

function $(id) { return document.getElementById(id); }

async function init() {
  // Load available effects and set defaults
  try {
    const res = await fetch(`${API}/api/effects`);
    const effects = await res.json();
    // wire effect buttons
    els.effectBtns.forEach((btn) => {
      const effect = btn.dataset.effect;
      btn.addEventListener("click", () => selectEffect(effect, effects[effect]));
    });
  } catch (e) {
    console.warn("Could not load effects", e);
  }

  // File input
  els.fileInput.addEventListener("change", (e) => {
    if (e.target.files.length) handleFile(e.target.files[0]);
  });

  // Drag & drop
  els.uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault();
    els.uploadArea.classList.add("dragover");
  });
  els.uploadArea.addEventListener("dragleave", () => {
    els.uploadArea.classList.remove("dragover");
  });
  els.uploadArea.addEventListener("drop", (e) => {
    e.preventDefault();
    els.uploadArea.classList.remove("dragover");
    if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
  });
  els.uploadArea.addEventListener("click", () => els.fileInput.click());

  // Process
  els.processBtn.addEventListener("click", processFile);

  // Sliders
  els.rateInput.addEventListener("input", () => {
    state.rate = parseFloat(els.rateInput.value);
    els.rateVal.textContent = state.rate.toFixed(2) + "×";
  });
  els.pitchInput.addEventListener("input", () => {
    state.pitch = parseFloat(els.pitchInput.value);
    els.pitchVal.textContent = state.pitch + " semitones";
  });
  els.reverbInput.addEventListener("input", () => {
    state.reverb = parseFloat(els.reverbInput.value);
    els.reverbVal.textContent = (state.reverb * 100).toFixed(0) + "%";
  });

  // Download
  els.downloadBtn.addEventListener("click", () => {
    if (state.jobId) location.href = `${API}/api/download/${state.jobId}`;
  });

  // PWA install prompt
  let deferredInstall;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredInstall = e;
  });

  // Register service worker
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/static/sw.js").catch((err) =>
      console.warn("SW registration failed", err)
    );
  }
}

function handleFile(file) {
  if (!file.type.startsWith("audio/") && !file.name.toLowerCase().endsWith(".mp3")) {
    // still allow — backend will decode what it can
  }
  state.selectedFile = file;
  els.fileName.textContent = file.name + ` (${(file.size / 1024 / 1024).toFixed(2)} MB)`;
  els.originalAudio.src = URL.createObjectURL(file);
  els.originalAudio.hidden = false;
  state.jobId = null;
  els.resultSection.hidden = true;
  els.status.classList.remove("visible");
  els.downloadBtn.disabled = true;
  // Auto-select an effect if none chosen
  if (!state.selectedEffect) selectEffect("nightcore");
}

function selectEffect(effect, meta) {
  state.selectedEffect = effect;
  els.effectBtns.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.effect === effect);
  });
  const isCustom = effect === "custom";
  els.customControls.classList.toggle("visible", isCustom);

  if (meta) {
    state.rate = meta.rate;
    state.pitch = meta.pitch;
    state.reverb = meta.reverb;
    els.rateInput.value = state.rate;
    els.pitchInput.value = state.pitch;
    els.reverbInput.value = state.reverb;
    els.rateVal.textContent = state.rate.toFixed(2) + "×";
    els.pitchVal.textContent = state.pitch + " semitones";
    els.reverbVal.textContent = (state.reverb * 100).toFixed(0) + "%";
  }
  els.processBtn.disabled = !state.selectedFile;
}

async function processFile() {
  if (!state.selectedFile) return;

  const form = new FormData();
  form.append("file", state.selectedFile);
  form.append("effect", state.selectedEffect);
  form.append("rate", String(state.rate));
  form.append("pitch", String(state.pitch));
  form.append("reverb", String(state.reverb));

  els.status.classList.add("visible");
  els.status.classList.remove("error");
  els.statusText.textContent = "Uploading…";
  els.processBtn.disabled = true;
  els.resultSection.hidden = true;
  els.downloadBtn.disabled = true;

  try {
    const res = await fetch(`${API}/api/upload`, { method: "POST", body: form });
    if (!res.ok) throw new Error("Upload failed");
    const data = await res.json();
    state.jobId = data.job_id;
    pollJob();
  } catch (err) {
    els.statusText.textContent = err.message || "Upload failed";
    els.status.classList.add("error");
    els.processBtn.disabled = false;
  }
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const res = await fetch(`${API}/api/jobs/${state.jobId}`);
    const job = await res.json();

    if (job.status === "processing") {
      els.statusText.textContent = `${job.message} (${job.progress}%)`;
      setTimeout(pollJob, 1200);
      return;
    }

    if (job.status === "done") {
      els.statusText.textContent = job.message;
      els.status.classList.add("visible");
      // Rebuild remix audio URL (with cache bust)
      const remixUrl = `${API}/api/download/${state.jobId}?t=${Date.now()}`;
      els.remixAudio.src = remixUrl;
      els.remixAudio.hidden = false;
      els.resultSection.hidden = false;
      els.downloadBtn.disabled = false;
      els.processBtn.disabled = false;
      return;
    }

    if (job.status === "error") {
      els.statusText.textContent = `Error: ${job.message}`;
      els.status.classList.add("visible", "error");
      els.processBtn.disabled = false;
      return;
    }

    // uploaded state
    els.statusText.textContent = job.message || "Processing…";
    setTimeout(pollJob, 1200);
  } catch (err) {
    els.statusText.textContent = "Error checking status";
    els.status.classList.add("visible", "error");
    els.processBtn.disabled = false;
  }
}

init();
