"use client";

import type { Cl1DeviceState, FeedbackType } from "@/lib/simulator/types";
import { Cl1ChannelHeatmap } from "@/components/cl1/cl1-channel-heatmap";
import { Cl1ControlPlaneLog, type ControlPlaneLogEntry } from "@/components/cl1/cl1-control-plane-log";
import { Cl1DeviceTiming } from "@/components/cl1/cl1-device-timing";
import { Cl1FeedbackBar } from "@/components/cl1/cl1-feedback-bar";
import { Cl1RecordingBar } from "@/components/cl1/cl1-recording-bar";
import { Cl1SafetyLimits } from "@/components/cl1/cl1-safety-limits";
import { Cl1SfeRounds } from "@/components/cl1/cl1-sfe-rounds";
import { Cl1TransportLanes } from "@/components/cl1/cl1-transport-lanes";

export type { ControlPlaneLogEntry };

export type Cl1BridgeDeckProps = {
  running: boolean;
  tick: number;
  deviceTimestampUs: number;
  pendingStim: number;
  feedbackPending: number;
  totalSpikes: number;
  stimDeliveries: number;
  dataStreamNames: number;
  cl1: Cl1DeviceState;
  recordingSession: string;
  recordingActive: boolean;
  recordingFrameCount: number;
  busy: boolean;
  onRecordingSessionChange: (v: string) => void;
  onRecordingStart: () => void;
  onRecordingStop: () => void;
  onRecordingStopExport: () => void;
  onFeedbackSend: (payload: {
    feedbackType: FeedbackType;
    channels: number[];
    frequencyHz: number;
    amplitudeUa: number;
    pulses: number;
    unpredictable: boolean;
    eventName: string;
  }) => Promise<void>;
  controlLog: ControlPlaneLogEntry[];
};

export function Cl1BridgeDeck({
  running,
  tick,
  deviceTimestampUs,
  pendingStim,
  feedbackPending,
  totalSpikes,
  stimDeliveries,
  dataStreamNames,
  cl1,
  recordingSession,
  recordingActive,
  recordingFrameCount,
  busy,
  onRecordingSessionChange,
  onRecordingStart,
  onRecordingStop,
  onRecordingStopExport,
  onFeedbackSend,
  controlLog
}: Cl1BridgeDeckProps) {
  return (
    <div className="cl1-bridge">
      <header className="cl1-bridge__head">
        <div>
          <span className="cl1-bridge__kicker">CL1 · bridge mock</span>
          <h2 className="cl1-bridge__title">Ops / transport / readout</h2>
          <p className="cl1-bridge__lede">
            Multi-port lanes, timing reference, dead-channel strip, recording shell — aligned with in-repo CL1 docs.
          </p>
        </div>
        <a
          className="ui-button ui-button--outline ui-button--sm"
          href="/api/simulator/device"
          target="_blank"
          rel="noreferrer"
        >
          Device JSON
        </a>
      </header>

      <div className="cl1-bridge__grid">
        <div className="cl1-bridge__col">
          <Cl1TransportLanes
            running={running}
            tick={tick}
            deviceTimestampUs={deviceTimestampUs}
            pendingStim={pendingStim}
            feedbackPending={feedbackPending}
            totalSpikes={totalSpikes}
            stimDeliveries={stimDeliveries}
            dataStreamNames={dataStreamNames}
          />
          <Cl1DeviceTiming />
          <Cl1SafetyLimits />
        </div>

        <div className="cl1-bridge__col">
          <Cl1ChannelHeatmap cl1={cl1} />
          <Cl1SfeRounds />
          <div className="cl1-bootstrap">
            <span className="cl1-bootstrap__title">Startup order (ref.)</span>
            <ol className="cl1-bootstrap__ol">
              <li>CL1 interface ready</li>
              <li>Ports / paths verified</li>
              <li>Control process · this dashboard</li>
              <li>Explicit shutdown + stop record</li>
            </ol>
          </div>
        </div>

        <div className="cl1-bridge__col">
          <Cl1FeedbackBar busy={busy} onSend={onFeedbackSend} />
          <Cl1RecordingBar
            session={recordingSession}
            active={recordingActive}
            frameCount={recordingFrameCount}
            disabled={busy}
            onSessionChange={onRecordingSessionChange}
            onStart={onRecordingStart}
            onStop={onRecordingStop}
            onStopExport={onRecordingStopExport}
          />
          <Cl1ControlPlaneLog entries={controlLog} />
        </div>
      </div>
    </div>
  );
}
