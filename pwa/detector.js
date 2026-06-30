// Streaming event detector — a faithful port of monitor/detector.py.
// Threshold + minimum-duration + debounce, peak/avg over loud readings only.
// Numbers and timestamps only; no audio is involved here.

export class Detector {
  constructor(thresholdDbfs, minDurationS, debounceS) {
    if (minDurationS < 0 || debounceS < 0) {
      throw new Error("minDurationS and debounceS must be non-negative");
    }
    this.threshold = thresholdDbfs;
    this.minDuration = minDurationS;
    this.debounce = debounceS;
    this._active = false;
    this._start = 0;
    this._lastAbove = 0;
    this._peak = 0;
    this._sum = 0;
    this._n = 0;
  }

  // Feed one (t, level) reading. Returns an event object if one just closed, else null.
  push(t, level) {
    const above = level >= this.threshold;
    if (!this._active) {
      if (above) this._open(t, level);
      return null;
    }
    if (above) {
      this._lastAbove = t;
      this._accumulate(level);
      return null;
    }
    if (t - this._lastAbove >= this.debounce) return this._close();
    return null;
  }

  // Close any open event at end of stream.
  flush() {
    return this._active ? this._close() : null;
  }

  _open(t, level) {
    this._active = true;
    this._start = t;
    this._lastAbove = t;
    this._peak = level;
    this._sum = level;
    this._n = 1;
  }

  _accumulate(level) {
    if (level > this._peak) this._peak = level;
    this._sum += level;
    this._n += 1;
  }

  _close() {
    const duration = this._lastAbove - this._start;
    let event = null;
    if (duration >= this.minDuration) {
      event = {
        start: this._start,
        end: this._lastAbove,
        duration,
        peak_level: this._peak,
        avg_level: this._n ? this._sum / this._n : this.threshold,
        coarse_tag: null,
      };
    }
    this._active = false;
    return event;
  }
}
