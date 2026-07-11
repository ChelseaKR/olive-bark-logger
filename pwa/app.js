// PWA glue: microphone -> in-memory level -> detector -> IndexedDB events -> report/CSV.
// AUDIO IS NEVER STORED. We read time-domain samples from an AnalyserNode into a reused
// buffer, reduce each frame to a dBFS number, and drop it. Only event metadata persists.

import { computeAnchor, toEpochSeconds } from "./clock.js";
import { Detector } from "./detector.js";
import { dbfs } from "./level.js";
import { buildReportHtml, eventsToCsv, summarize, violationsToCsv } from "./report.js";

const $ = (id) => document.getElementById(id);
const cfg = () => ({
  threshold: parseFloat($("threshold").value),
  minDuration: parseFloat($("minDuration").value),
  debounce: parseFloat($("debounce").value),
  startHour: parseInt($("startHour").value, 10),
  endHour: parseInt($("endHour").value, 10),
  tz: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
});

// --- IndexedDB (events only) ---
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open("olive", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("events", { autoIncrement: true });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function addEvent(ev) {
  const db = await openDb();
  await new Promise((res, rej) => {
    const tx = db.transaction("events", "readwrite");
    tx.objectStore("events").add(ev);
    tx.oncomplete = res;
    tx.onerror = () => rej(tx.error);
  });
}
async function allEvents() {
  const db = await openDb();
  return new Promise((res, rej) => {
    const req = db.transaction("events", "readonly").objectStore("events").getAll();
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}
async function clearEvents() {
  const db = await openDb();
  await new Promise((res, rej) => {
    const tx = db.transaction("events", "readwrite");
    tx.objectStore("events").clear();
    tx.oncomplete = res;
    tx.onerror = () => rej(tx.error);
  });
}

const STATUS_LISTENING =
  "Listening. Audio is processed in memory and never stored. Keep this tab open and " +
  "in the foreground: a backgrounded or locked tab cannot monitor reliably, and any " +
  "such interruptions are recorded as monitoring gaps.";
const SAMPLE_INTERVAL_MS = 100; // steady clock, not tied to rAF (which throttles in the background)
const GAP_THRESHOLD_S = 2; // background interruptions longer than this are logged as gaps

let audioCtx = null;
let stream = null;
let sampler = 0; // setInterval id; rAF throttles to ~0 in a backgrounded tab
let detector = null;
let anchor = 0; // epoch-seconds value that audioCtx.currentTime 0 maps to
let gapStart = 0; // epoch-seconds when the tab was last hidden, 0 when visible/idle

// Persist a coverage hole so the report can be honest about time we could not monitor.
async function recordGap(start, end) {
  if (end - start < GAP_THRESHOLD_S) return;
  await addEvent({ kind: "gap", start, end });
  await refresh();
}

async function onVisibilityChange() {
  if (!audioCtx) return;
  if (document.visibilityState === "hidden") {
    gapStart = toEpochSeconds(audioCtx.currentTime, anchor);
  } else if (gapStart) {
    const end = toEpochSeconds(audioCtx.currentTime, anchor);
    const start = gapStart;
    gapStart = 0;
    await recordGap(start, end);
  }
}

async function start() {
  const c = cfg();
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioCtx = new AudioContext();
  // Anchor context-time to wall-clock once, so stored events carry unix-epoch seconds
  // (report.js/CSV do new Date(ev.start * 1000)), not seconds-since-context-created.
  anchor = computeAnchor(Date.now(), audioCtx.currentTime);
  gapStart = 0;
  const src = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  src.connect(analyser);
  const buf = new Float32Array(analyser.fftSize); // reused buffer; audio never kept
  detector = new Detector(c.threshold, c.minDuration, c.debounce);

  $("start").disabled = true;
  $("stop").disabled = false;
  $("status").textContent = STATUS_LISTENING;
  document.addEventListener("visibilitychange", onVisibilityChange);

  const tick = async () => {
    analyser.getFloatTimeDomainData(buf);
    const t = toEpochSeconds(audioCtx.currentTime, anchor);
    const level = dbfs(buf);
    $("meter").value = Math.max(0, Math.min(100, ((level + 60) / 60) * 100));
    $("level").textContent = `${level.toFixed(1)} dBFS`;
    const ev = detector.push(t, level);
    if (ev) {
      await addEvent(ev);
      await refresh();
    }
  };
  sampler = setInterval(tick, SAMPLE_INTERVAL_MS);
}

async function stop() {
  clearInterval(sampler);
  sampler = 0;
  document.removeEventListener("visibilitychange", onVisibilityChange);
  if (gapStart && audioCtx) {
    const end = toEpochSeconds(audioCtx.currentTime, anchor);
    const start = gapStart;
    gapStart = 0;
    await recordGap(start, end);
  }
  // Finalize any in-progress event so a trailing bark is not lost on stop.
  if (detector) {
    const ev = detector.flush();
    detector = null;
    if (ev) {
      await addEvent(ev);
      await refresh();
    }
  }
  if (stream) stream.getTracks().forEach((tr) => tr.stop());
  if (audioCtx) audioCtx.close();
  audioCtx = null;
  $("start").disabled = false;
  $("stop").disabled = true;
  $("status").textContent = "Stopped.";
}

function download(name, text, type) {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function refresh() {
  const events = await allEvents();
  $("count").textContent = String(events.length);
}

async function downloadReport() {
  const c = cfg();
  const events = await allEvents();
  const summary = summarize(events, c);
  const html = buildReportHtml(summary, { generatedAt: new Date().toLocaleString(), ...c });
  download("report.html", html, "text/html");
}
async function downloadCsv() {
  download("events.csv", eventsToCsv(await allEvents()), "text/csv");
}
async function downloadViolations() {
  download("quiet-hours.csv", violationsToCsv(await allEvents(), cfg()), "text/csv");
}

window.addEventListener("DOMContentLoaded", () => {
  $("start").addEventListener("click", () => start().catch((e) => ($("status").textContent = e.message)));
  $("stop").addEventListener("click", stop);
  $("report").addEventListener("click", downloadReport);
  $("csv").addEventListener("click", downloadCsv);
  $("violations").addEventListener("click", downloadViolations);
  $("clear").addEventListener("click", () => clearEvents().then(refresh));
  refresh();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => {});
});
