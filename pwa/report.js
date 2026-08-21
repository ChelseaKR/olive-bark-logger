// Aggregation, accessible-report HTML, and CSV for the PWA. Parallels report/*.py:
// same honest methodology + limitations, same "no audio" guarantee, data tables for a11y.
//
// The caveats are not optional and they are not the Python side's alone. This is the
// zero-hardware route into the same task — no Raspberry Pi, no install, no command line —
// and it exports the same kind of file to hand to a landlord. The path with the lowest
// barrier to reaching for it must not be the path that ships without its limits. Every
// export path below therefore carries the "what this can and cannot prove" cover block, and
// anything that reports a quiet-hours count also carries the no-verdict line. The exact
// strings live in spec/report/cover.json and are replayed against both implementations
// (pwa/report.test.mjs here, tests/test_export_caveats.py on the Python side), the same
// way spec/detector/*.json keeps the two detectors from drifting.

export const RELATIVE_DBFS_NOTE =
  "Levels are measured in dBFS, which is relative to digital full scale, not absolute " +
  "sound pressure level (SPL) in dB. Without calibration against a reference meter, " +
  "treat the numbers as relative, not absolute.";
export const NO_SOURCE_NOTE =
  "This tool measures sound levels only. It cannot prove what made a sound or where it " +
  "came from; it does not record or identify any voice or source.";

// R1 — the plain-language cover block, verbatim from report/render.py.
export const COVER_HEADING = "What this can and cannot prove";
export const COVER_CAN = [
  "When sound at this device crossed a set loudness threshold, and for how long, with " +
    "timestamps — an honest, time-stamped record of the pattern.",
  "How that pattern lines up with a quiet-hours window you configure.",
];
export const COVER_CANNOT = [
  "What made a sound, or who caused it — no audio is recorded, so there is no source " +
    "attribution.",
  "Absolute loudness in dB SPL or dB(A): uncalibrated readings are relative dBFS, not " +
    "the units an ordinance, lease, or HOA rule is written in.",
  "That any law, lease, or rule was broken — only the relevant authority decides that, " +
    "and being within quiet hours is not the same as a violation.",
  "Anything about a place this device was not in — readings are specific to this " +
    "microphone in this spot, and change if it moves.",
];
export const COVER_PRIVACY =
  "By design no audio is ever recorded, stored, or transmitted, so there is nothing to " +
  "leak, subpoena, or misuse. This is general information, not legal advice; verify your " +
  "local rule before relying on these numbers.";

// R3 — a quiet-hours count is a measurement, never a finding.
export const NO_VERDICT_NOTE =
  "This is a measurement, not a determination. Being within quiet hours is not the same " +
  "as a violation, and only the relevant authority can decide whether a rule was broken.";

// R2 — the browser edition has no calibration step at all, so it is always uncalibrated.
export const UNCALIBRATED_HEADLINE =
  "Uncalibrated — these readings are relative, not dB(A).";
export const UNCALIBRATED_NOTE =
  "This browser edition has no calibration step, so its readings are always relative " +
  "dBFS, never absolute sound level in dB(A) or dB SPL. Do not read them as the decibel " +
  "numbers an ordinance or lease specifies; only their pattern relative to each other on " +
  "this device is meaningful.";

// The cover as plain-text lines, for the leading "#" comment preamble of a CSV export —
// the same shape report/render.py's cover_text_lines() writes, so the caveat travels
// with a file that gets downloaded and emailed on.
export function coverTextLines() {
  return [
    COVER_HEADING,
    "",
    "What it can show:",
    ...COVER_CAN.map((x) => `  - ${x}`),
    "",
    "What it cannot prove:",
    ...COVER_CANNOT.map((x) => `  - ${x}`),
    "",
    COVER_PRIVACY,
  ];
}

// Every CSV this module writes starts with the cover. Exported so a new export path
// cannot quietly skip it, and so the gate can prove each path went through here.
export function csvPreamble(extraLines = []) {
  const lines = [...coverTextLines(), ...(extraLines.length ? ["", ...extraLines] : [])];
  return lines.map((line) => (line ? `# ${line}` : "#")).join("\n");
}

// Monitoring gaps, stated in the preamble of an export. A gap removes events, so an
// unmonitored stretch would otherwise read as a quiet one. Said either way: "none
// recorded" is information, silence is not.
export function gapPreambleLines(gaps) {
  if (!gaps || !gaps.length) {
    return [
      "Monitoring gaps: none recorded. The browser cannot monitor while the tab is " +
        "backgrounded or the device is locked; interruptions it noticed are listed here. " +
        "One it never got to record cannot appear, so treat this as an upper bound on " +
        "how much was observed.",
    ];
  }
  let seconds = 0;
  for (const g of gaps) seconds += Math.max(0, (g.end || 0) - (g.start || 0));
  const lines = [
    `Monitoring gaps: ${gaps.length} recorded, totalling ${Math.round(seconds)}s, during ` +
      "which no event could be detected. These periods are absences of data, not silence: " +
      "the absence of an event in them is not evidence that no sound occurred.",
    "",
  ];
  for (const g of gaps) {
    lines.push(
      `  - ${new Date(g.start * 1000).toISOString()} to ${new Date(g.end * 1000).toISOString()} ` +
        `(${Math.round(Math.max(0, g.end - g.start))}s)`,
    );
  }
  return lines;
}

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

// The cover block as an accessible HTML section. Deterministic; restates limits that
// already hold elsewhere in the report, adds prominence, never a new claim.
function coverHtml() {
  const li = (xs) => xs.map((x) => `<li>${esc(x)}</li>`).join("");
  return `<section class="cover" aria-label="What this report can and cannot prove">
<h2>${esc(COVER_HEADING)}</h2>
<p><strong>What it can show:</strong></p>
<ul>${li(COVER_CAN)}</ul>
<p><strong>What it cannot prove:</strong></p>
<ul>${li(COVER_CANNOT)}</ul>
<p class="note">${esc(COVER_PRIVACY)}</p>
</section>`;
}

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
        // Dark count on a small white chip: WCAG AA (4.5:1) holds at every cell
        // shade. The old fg switch (white text when ratio >= 0.55) genuinely failed
        // AA on mid-intensity cells — same defect class fixed in report/charts.py
        // (see tests/test_svg_contrast.py for the exact ratios on the shared ramp).
        return `<td style="background:${bg};text-align:center" title="${esc(d)} ${String(h).padStart(2, "0")}:00 — ${v} events"><span style="background:#fff;color:#111;padding:0 3px;border-radius:2px">${v}</span></td>`;
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
<title>Olive's Bark Logger — Noise Report</title>
<style>
section.cover { border: 1px solid #bbb; padding: .5rem 1.25rem 1rem; margin: 1rem 0; }
.banner { padding: .75rem 1rem; margin: 1rem 0; border: 2px solid #b35900; }
.note { border-left: 4px solid #3b6ea5; padding: .75rem 1rem; }
</style></head><body>
<main>
<h1>Olive's Bark Logger — Noise Report</h1>
<p>Generated ${esc(generatedAt)}. Sound-level <em>events</em> only. No audio was recorded, stored, or transmitted.</p>
${coverHtml()}
<aside class="banner" role="note" aria-label="Calibration status">
<strong>${esc(UNCALIBRATED_HEADLINE)}</strong> ${esc(UNCALIBRATED_NOTE)}
</aside>
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
<div class="note"><p>${esc(NO_VERDICT_NOTE)} Compare these counts against your own local ordinance, lease, or HOA rule.</p></div>
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
  // The cover travels as a leading "#" comment preamble, the way report/export.py writes
  // it. Spreadsheets and csv parsers skip "#" lines; a person reading the file does not.
  const lines = [csvPreamble(), header.join(",")];
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
//
// This is the file a browser user downloads and emails on, so it carries the cover block
// and the no-verdict line as a "#" preamble: a bare table of timestamps and
// "within_quiet_hours,yes" with nothing attached is exactly the document that reads as a
// verdict. Recorded monitoring gaps are named too, since a gap removes events and would
// otherwise make an unmonitored stretch look like a quiet one.
export function violationsToCsv(records, { startHour = 22, endHour = 8, tz = "UTC" } = {}) {
  const events = onlyEvents(records);
  const gaps = onlyGaps(records);
  const window = `${String(startHour).padStart(2, "0")}:00–${String(endHour).padStart(2, "0")}:00`;
  const header = [
    "start_unix", "start_iso", "end_iso", "hour_local",
    "duration_s", "peak_dbfs", "avg_dbfs", "within_quiet_hours", "quiet_window", "coarse_tag",
  ];
  const iso = (s) => new Date(s * 1000).toISOString();
  const notes = [NO_VERDICT_NOTE, "", ...gapPreambleLines(gaps)];
  const lines = [csvPreamble(notes), header.join(",")];
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
