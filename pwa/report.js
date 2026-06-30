// Aggregation, accessible-report HTML, and CSV for the PWA. Parallels report/*.py:
// same honest methodology + limitations, same "no audio" guarantee, data tables for a11y.

export const RELATIVE_DBFS_NOTE =
  "Levels are measured in dBFS, which is relative to digital full scale, not absolute " +
  "sound pressure level (SPL) in dB. Without calibration against a reference meter, " +
  "treat the numbers as relative, not absolute.";
export const NO_SOURCE_NOTE =
  "This tool measures sound levels only. It cannot prove what made a sound or where it " +
  "came from; it does not record or identify any voice or source.";

function partsInTz(ms, tz) {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
  });
  const p = Object.fromEntries(fmt.formatToParts(new Date(ms)).map((x) => [x.type, x.value]));
  return { hour: parseInt(p.hour, 10) % 24, date: `${p.year}-${p.month}-${p.day}` };
}

function inQuietHours(hour, startHour, endHour) {
  if (startHour <= endHour) return hour >= startHour && hour < endHour;
  return hour >= startHour || hour < endHour; // wraps midnight
}

export function summarize(events, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const byHour = {};
  for (let h = 0; h < 24; h++) byHour[h] = 0;
  const byDay = {};
  const byTag = {};
  let totalLoud = 0;
  let quietCount = 0;
  let quietLoud = 0;
  let loudestPeak = -Infinity;
  let peakSum = 0;
  let longest = 0;
  for (const ev of events) {
    const { hour, date } = partsInTz(ev.start * 1000, tz);
    byHour[hour] += 1;
    byDay[date] = (byDay[date] || 0) + 1;
    if (ev.coarse_tag) byTag[ev.coarse_tag] = (byTag[ev.coarse_tag] || 0) + 1;
    totalLoud += ev.duration;
    peakSum += ev.peak_level;
    loudestPeak = Math.max(loudestPeak, ev.peak_level);
    longest = Math.max(longest, ev.duration);
    if (inQuietHours(hour, startHour, endHour)) {
      quietCount += 1;
      quietLoud += ev.duration;
    }
  }
  return {
    count: events.length,
    totalLoud,
    longest,
    loudestPeak: events.length ? loudestPeak : 0,
    meanPeak: events.length ? peakSum / events.length : 0,
    byHour,
    byDay,
    byTag,
    quietCount,
    quietLoud,
  };
}

const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;" })[c]);

function table(caption, headers, rows) {
  const head = headers.map((h) => `<th scope="col">${esc(h)}</th>`).join("");
  const body = rows
    .map(([k, v]) => `<tr><th scope="row">${esc(k)}</th><td>${esc(v)}</td></tr>`)
    .join("");
  return `<table><caption>${esc(caption)}</caption><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

export function buildReportHtml(summary, { generatedAt, tz = "UTC", startHour = 22, endHour = 8 }) {
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const hourRows = Object.entries(summary.byHour).map(([h, c]) => [`${String(h).padStart(2, "0")}`, c]);
  const dayRows = Object.entries(summary.byDay).sort();
  const tagRows = Object.entries(summary.byTag).sort();
  const tagsSection = tagRows.length
    ? `<h2>Event types (coarse hint)</h2><p>A crude, on-device hint, not a fact; it cannot identify a source.</p>${table("Events by coarse type", ["Type", "Events"], tagRows)}`
    : "";
  return `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Olive's Bark Logger — Noise Report</title></head><body>
<main>
<h1>Olive's Bark Logger — Noise Report</h1>
<p>Generated ${esc(generatedAt)}. Sound-level <em>events</em> only. No audio was recorded, stored, or transmitted.</p>
<h2>Summary</h2>
${table("Summary", ["Metric", "Value"], [
  ["Total events", summary.count],
  ["Total loud time (s)", summary.totalLoud.toFixed(1)],
  ["Longest event (s)", summary.longest.toFixed(1)],
  ["Loudest peak (dBFS)", summary.loudestPeak.toFixed(1)],
  ["Mean peak (dBFS)", summary.meanPeak.toFixed(1)],
  [`Events during quiet hours (${window})`, summary.quietCount],
])}
<h2>Events by hour of day</h2>
${table("Events by hour of day", ["Hour", "Events"], hourRows)}
<h2>Events by day</h2>
${dayRows.length ? table("Events by day", ["Day", "Events"], dayRows) : "<p>No events yet.</p>"}
${tagsSection}
<h2>Quiet hours</h2>
<p>Window <strong>${window}</strong> in time zone <strong>${esc(tz)}</strong>. Of ${summary.count} events, <strong>${summary.quietCount}</strong> fell within quiet hours.</p>
<h2>Methodology</h2>
<p>Each audio frame is reduced in memory to one RMS level in dBFS and then discarded. An event is recorded when the level stays above the threshold for at least the minimum duration; brief dips shorter than the debounce do not split it. Only six numbers per event are stored — never audio.</p>
<h2>Limitations</h2>
<p>${esc(RELATIVE_DBFS_NOTE)}</p>
<p>${esc(NO_SOURCE_NOTE)}</p>
</main></body></html>`;
}

export function eventsToCsv(events, tz = "UTC") {
  const header = ["start_unix", "start_iso", "end_iso", "duration_s", "peak_dbfs", "avg_dbfs", "coarse_tag"];
  const iso = (s) => new Date(s * 1000).toISOString();
  const lines = [header.join(",")];
  for (const ev of events) {
    lines.push([
      ev.start.toFixed(3),
      iso(ev.start),
      iso(ev.end),
      ev.duration.toFixed(3),
      ev.peak_level.toFixed(1),
      ev.avg_level.toFixed(1),
      ev.coarse_tag || "",
    ].join(","));
  }
  return lines.join("\n");
}
