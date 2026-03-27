"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";

/** Same Frame Encoding (SFE) — optional multi-view rounds; UI mock only here. */

export function Cl1SfeRounds() {
  const [rounds, setRounds] = useState({ full: true, spatial: false, color: false });

  return (
    <div className="cl1-sfe" aria-label="Same Frame Encoding mock">
      <span className="cl1-sfe__title">SFE rounds</span>
      <div className="cl1-sfe__toggles">
        {(
          [
            ["full", "Full"],
            ["spatial", "Spatial"],
            ["color", "Color"]
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`cl1-sfe__chip${rounds[key] ? " cl1-sfe__chip--on" : ""}`}
            onClick={() => setRounds((r) => ({ ...r, [key]: !r[key] }))}
          >
            {label}
          </button>
        ))}
      </div>
      <Badge variant="outline" style={{ fontSize: "0.55rem" }}>
        mock · one policy head / round on hardware
      </Badge>
    </div>
  );
}
