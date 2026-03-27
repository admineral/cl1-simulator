"use client";

import type { Cl1DeviceState } from "@/lib/simulator/types";

type Props = {
  cl1: Cl1DeviceState;
};

export function Cl1ChannelHeatmap({ cl1 }: Props) {
  const dead = new Set(cl1.deadChannels);

  return (
    <div className="cl1-heatmap" aria-label="Per-electrode normalized spike counts this tick">
      <div className="cl1-heatmap__head">
        <span>64‑ch</span>
        <span className="cl1-heatmap__legend dead">dead</span>
        <span className="cl1-heatmap__legend active">norm spike</span>
      </div>
      <div className="cl1-heatmap__strip" role="img" aria-label="Channel strip by index 0 to 63">
        {cl1.spikeCountsNormalized.map((n, ch) => {
          const isDead = dead.has(ch);
          const alpha = isDead ? 0.12 : Math.min(0.15 + n * 0.85, 1);
          return (
            <span
              key={ch}
              className={`cl1-heatmap__cell${isDead ? " cl1-heatmap__cell--dead" : ""}`}
              style={{
                background: isDead
                  ? "rgba(40,48,56,0.9)"
                  : `rgba(46, 228, 208, ${alpha.toFixed(3)})`,
                boxShadow: !isDead && n > 0.2 ? "inset 0 0 0 1px rgba(127,234,255,0.35)" : undefined
              }}
              title={`ch ${ch}${isDead ? " (dead)" : ""} · norm ${n.toFixed(2)} · raw ${cl1.spikeCounts[ch]?.toFixed(2) ?? 0}`}
            />
          );
        })}
      </div>
    </div>
  );
}
