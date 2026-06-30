// Frame -> dBFS, mirroring monitor/level.py. The frame (a Float32Array of samples in
// [-1, 1] from the AnalyserNode) is reduced to one number and then discarded — it is
// never stored or sent anywhere.

export const SILENCE_FLOOR_DBFS = -120.0;

export function rms(frame) {
  if (frame.length === 0) return 0;
  let total = 0;
  for (let i = 0; i < frame.length; i++) total += frame[i] * frame[i];
  return Math.sqrt(total / frame.length);
}

export function dbfs(frame, calibrationOffset = 0) {
  const amp = rms(frame);
  if (amp <= 0) return SILENCE_FLOOR_DBFS + calibrationOffset;
  let level = 20 * Math.log10(amp);
  if (level < SILENCE_FLOOR_DBFS) level = SILENCE_FLOOR_DBFS;
  return level + calibrationOffset;
}
