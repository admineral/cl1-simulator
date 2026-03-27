"use client";

/** Reference constants from CL1 UDP / device bridge docs (training-side + device path). */

export function Cl1DeviceTiming() {
  return (
    <div className="cl1-timing-grid" aria-label="Device and training timing reference">
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">SPIKE_ARTIFACT_WAIT</span>
        <span className="cl1-timing-v">50 ms</span>
      </div>
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">UDP_TIMEOUT</span>
        <span className="cl1-timing-v">5.0 s</span>
      </div>
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">tick_rate</span>
        <span className="cl1-timing-v">1000 Hz</span>
      </div>
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">ARTIFACT_TICKS</span>
        <span className="cl1-timing-v">10</span>
      </div>
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">COLLECT_TICKS</span>
        <span className="cl1-timing-v">50</span>
      </div>
      <div className="cl1-timing-cell">
        <span className="cl1-timing-k">PHASE_WIDTH</span>
        <span className="cl1-timing-v">200 µs</span>
      </div>
    </div>
  );
}
