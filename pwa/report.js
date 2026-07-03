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

// Gap records ({ kind: 'gap', start, end }) are written when the tab was backgrounded
// or locked and could not monitor. They are coverage holes, not loud events, so every
// aggregation and export filters them out of the event set (and surfaces them apart).
const isGap = (r) => r && r.kind === "gap";
const onlyEvents = (records) => records.filter((r) => !isGap(r));
const onlyGaps = (records) => records.filter(isGap);

export function summarize(records, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const events = onlyEvents(records);
  const gaps = onlyGaps(records);
  let gapSeconds = 0;
  for (const g of gaps) gapSeconds += Math.max(0, (g.end || 0) - (g.start || 0));
  const byHour = {};
  for (let h = 0; h < 24; h++) byHour[h] = 0;
  const byDay = {};
  const byTag = {};
  const byDayHour = {}; // date -> {hour -> count}: the calendar heatmap grid (counts only)
  let totalLoud = 0;
  let quietCount = 0;
  let quietLoud = 0;
  let outsideLoud = 0;
  let loudestPeak = -Infinity;
  let peakSum = 0;
  let longest = 0;
  for (const ev of events) {
    const { hour, date } = partsInTz(ev.start * 1000, tz);
    byHour[hour] += 1;
    byDay[date] = (byDay[date] || 0) + 1;
    if (!byDayHour[date]) {
      byDayHour[date] = {};
      for (let h = 0; h < 24; h++) byDayHour[date][h] = 0;
    }
    byDayHour[date][hour] += 1;
    if (ev.coarse_tag) byTag[ev.coarse_tag] = (byTag[ev.coarse_tag] || 0) + 1;
    totalLoud += ev.duration;
    peakSum += ev.peak_level;
    loudestPeak = Math.max(loudestPeak, ev.peak_level);
    longest = Math.max(longest, ev.duration);
    if (inQuietHours(hour, startHour, endHour)) {
      quietCount += 1;
      quietLoud += ev.duration;
    } else {
      outsideLoud += ev.duration;
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
    byDayHour,
    quietCount,
    quietLoud,
    outsideCount: events.length - quietCount,
    outsideLoud,
    gapCount: gaps.length,
    gapSeconds,
    gaps,
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

// Calendar heatmap as an accessible HTML table: rows are days, columns are hours 0..23.
// Cells are shaded by intensity AND print their count, so meaning never depends on color
// alone; the table itself is the data-table equivalent. Counts only — never audio.
function heatTable(byDayHour) {
  const days = Object.keys(byDayHour).sort();
  let max = 0;
  for (const d of days) for (let h = 0; h < 24; h++) max = Math.max(max, byDayHour[d][h] || 0);
  const head = Array.from({ length: 24 }, (_, h) => `<th scope="col">${String(h).padStart(2, "0")}</th>`).join("");
  const rows = days
    .map((d) => {
      let rowTotal = 0;
      const cells = Array.from({ length: 24 }, (_, h) => {
        const v = byDayHour[d][h] || 0;
        rowTotal += v;
        const ratio = max ? v / max : 0;
        const ch = Math.round(255 - (255 - 59) * ratio);
        const cg = Math.round(255 - (255 - 110) * ratio);
        const cb = Math.round(255 - (255 - 165) * ratio);
        const bg = v === 0 ? "#f5f5f5" : `rgb(${ch},${cg},${cb})`;
        const fg = ratio >= 0.55 ? "#fff" : "#111";
        return `<td style="background:${bg};color:${fg};text-align:center" title="${esc(d)} ${String(h).padStart(2, "0")}:00 — ${v} events">${v}</td>`;
      }).join("");
      return `<tr><th scope="row">${esc(d)}</th>${cells}<td>${rowTotal}</td></tr>`;
    })
    .join("");
  return `<table><caption>Events by day and hour — darker cells saw more events; counts are printed in every cell</caption><thead><tr><th scope="col">Day</th>${head}<th scope="col">Total</th></tr></thead><tbody>${rows}</tbody></table>`;
}

export function buildReportHtml(summary, { generatedAt, tz = "UTC", startHour = 22, endHour = 8 }) {
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const hourRows = Object.entries(summary.byHour).map(([h, c]) => [`${String(h).padStart(2, "0")}`, c]);
  const dayRows = Object.entries(summary.byDay).sort();
  const tagRows = Object.entries(summary.byTag).sort();
  const tagsSection = tagRows.length
    ? `<h2>Event types (coarse hint)</h2><p>A crude, on-device hint, not a fact; it cannot identify a source.</p>${table("Events by coarse type", ["Type", "Events"], tagRows)}`
    : "";
  const gapRows = (summary.gaps || []).map((g) => [
    new Date(g.start * 1000).toISOString(),
    `${new Date(g.end * 1000).toISOString()} (${Math.round((g.end - g.start))}s)`,
  ]);
  const gapsSection = gapRows.length
    ? `<h2>Monitoring gaps</h2><p>The browser cannot monitor while the tab is backgrounded or the device is locked. During ${summary.gapCount} such gap(s), totalling ${Math.round(summary.gapSeconds)}s, no events could be detected. These periods are absences of data, not silence.</p>${table("Monitoring gaps (no data collected)", ["Gap start", "Gap end"], gapRows)}`
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
<h2>Calendar heatmap</h2>
${dayRows.length ? `<p>Each cell is the number of events that began in that hour, by day and hour of day. Darker cells saw more events; the count is printed in every cell, so the pattern does not depend on color.</p>${heatTable(summary.byDayHour)}` : "<p>No events have been logged yet, so there is no calendar to show.</p>"}
${tagsSection}
${gapsSection}
<h2>Quiet hours</h2>
<p>Window <strong>${window}</strong> in time zone <strong>${esc(tz)}</strong>. Of ${summary.count} events, <strong>${summary.quietCount}</strong> began within quiet hours and <strong>${summary.outsideCount}</strong> outside them. An event counts as within quiet hours by its start time; this flags a level threshold being crossed, not the source of a sound.</p>
<h2>Methodology</h2>
<p>Each audio frame is reduced in memory to one RMS level in dBFS and then discarded. An event is recorded when the level stays above the threshold for at least the minimum duration; brief dips shorter than the debounce do not split it. Only six numbers per event are stored — never audio.</p>
<h2>Limitations</h2>
<p>${esc(RELATIVE_DBFS_NOTE)}</p>
<p>${esc(NO_SOURCE_NOTE)}</p>
</main></body></html>`;
}

export function eventsToCsv(records, tz = "UTC") {
  const events = onlyEvents(records);
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

// Honest quiet-hours export: every event, flagged within/outside the window by its start
// time (in the given tz). Lists all events, never a cherry-picked subset. Counts only.
export function violationsToCsv(records, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const events = onlyEvents(records);
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const header = [
    "start_unix", "start_iso", "end_iso", "hour_local",
    "duration_s", "peak_dbfs", "avg_dbfs", "within_quiet_hours", "quiet_window", "coarse_tag",
  ];
  const iso = (s) => new Date(s * 1000).toISOString();
  const lines = [header.join(",")];
  for (const ev of events) {
    const { hour } = partsInTz(ev.start * 1000, tz);
    const within = inQuietHours(hour, startHour, endHour);
    lines.push([
      ev.start.toFixed(3),
      iso(ev.start),
      iso(ev.end),
      String(hour).padStart(2, "0"),
      ev.duration.toFixed(3),
      ev.peak_level.toFixed(1),
      ev.avg_level.toFixed(1),
      within ? "yes" : "no",
      window,
      ev.coarse_tag || "",
    ].join(","));
  }
  return lines.join("\n");
}
