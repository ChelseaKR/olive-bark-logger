// PWA glue: microphone -> in-memory level -> detector -> IndexedDB events -> report/CSV.
// AUDIO IS NEVER STORED. We read time-domain samples from an AnalyserNode into a reused
// buffer, reduce each frame to a dBFS number, and drop it. Only event metadata persists.

import { Detector } from "./detector.js";
import { dbfs } from "./level.js";
import { buildReportHtml, eventsToCsv, summarize } from "./report.js";

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

let audioCtx = null;
let stream = null;
let raf = 0;

async function start() {
  const c = cfg();
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioCtx = new AudioContext();
  const src = audioCtx.createMediaStreamSource(stream);
  const analyser = audioCtx.createAnalyser();
  analyser.fftSize = 2048;
  src.connect(analyser);
  const buf = new Float32Array(analyser.fftSize); // reused buffer; audio never kept
  const detector = new Detector(c.threshold, c.minDuration, c.debounce);

  $("start").disabled = true;
  $("stop").disabled = false;
  $("status").textContent = "Listening. Audio is processed in memory and never stored.";

  const tick = async () => {
    analyser.getFloatTimeDomainData(buf);
    const t = audioCtx.currentTime;
    const level = dbfs(buf);
    $("meter").value = Math.max(0, Math.min(100, ((level + 60) / 60) * 100));
    $("level").textContent = `${level.toFixed(1)} dBFS`;
    const ev = detector.push(t, level);
    if (ev) {
      await addEvent(ev);
      await refresh();
    }
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
}

function stop() {
  cancelAnimationFrame(raf);
  if (stream) stream.getTracks().forEach((tr) => tr.stop());
  if (audioCtx) audioCtx.close();
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

window.addEventListener("DOMContentLoaded", () => {
  $("start").addEventListener("click", () => start().catch((e) => ($("status").textContent = e.message)));
  $("stop").addEventListener("click", stop);
  $("report").addEventListener("click", downloadReport);
  $("csv").addEventListener("click", downloadCsv);
  $("clear").addEventListener("click", () => clearEvents().then(refresh));
  refresh();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("./sw.js").catch(() => {});
});
