"use client";

import { Badge } from "@/components/ui/badge";

export type Cl1TransportLanesProps = {
  running: boolean;
  tick: number;
  deviceTimestampUs: number;
  pendingStim: number;
  feedbackPending: number;
  totalSpikes: number;
  stimDeliveries: number;
  dataStreamNames: number;
};

export function Cl1TransportLanes({
  running,
  tick,
  deviceTimestampUs,
  pendingStim,
  feedbackPending,
  totalSpikes,
  stimDeliveries,
  dataStreamNames
}: Cl1TransportLanesProps) {
  const live = running ? "cl1-lane cl1-lane--live" : "cl1-lane";

  return (
    <div className="cl1-transport-lanes" role="list" aria-label="Multi-port transport mock">
      <div className={live} role="listitem">
        <span className="cl1-lane__tag">STIM</span>
        <span className="cl1-lane__meta">pending {pendingStim}</span>
        <Badge variant={running ? "success" : "outline"} style={{ fontSize: "0.58rem" }}>
          {running ? "data plane" : "idle"}
        </Badge>
      </div>
      <div className={live} role="listitem">
        <span className="cl1-lane__tag">SPIKE</span>
        <span className="cl1-lane__meta">{totalSpikes} stored</span>
        <Badge variant="outline" style={{ fontSize: "0.58rem" }}>
          t={tick}
        </Badge>
      </div>
      <div className="cl1-lane" role="listitem">
        <span className="cl1-lane__tag">FDBK</span>
        <span className="cl1-lane__meta">queued {feedbackPending}</span>
        <Badge variant="outline" style={{ fontSize: "0.58rem" }}>
          next tick
        </Badge>
      </div>
      <div className="cl1-lane" role="listitem">
        <span className="cl1-lane__tag">EVENT</span>
        <span className="cl1-lane__meta">{dataStreamNames} streams</span>
        <Badge variant="outline" style={{ fontSize: "0.58rem" }}>
          JSON IO
        </Badge>
      </div>
      <div className="cl1-lane" role="listitem">
        <span className="cl1-lane__tag">CTRL</span>
        <span className="cl1-lane__meta mono">
          {deviceTimestampUs} µs · stim deliveries {stimDeliveries}
        </span>
      </div>
    </div>
  );
}
