"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type Cl1RecordingBarProps = {
  session: string;
  active: boolean;
  frameCount: number;
  disabled: boolean;
  onSessionChange: (v: string) => void;
  onStart: () => void;
  onStop: () => void;
  onStopExport: () => void;
};

export function Cl1RecordingBar({
  session,
  active,
  frameCount,
  disabled,
  onSessionChange,
  onStart,
  onStop,
  onStopExport
}: Cl1RecordingBarProps) {
  return (
    <div className="cl1-recording-bar">
      <label className="cl1-recording-bar__label">
        <span>Session</span>
        <Input
          className="ctl-input ctl-input--md"
          value={session}
          onChange={(e) => onSessionChange(e.target.value)}
          disabled={disabled || active}
          spellCheck={false}
          aria-label="Recording session name"
        />
      </label>
      <div className="cl1-recording-bar__actions">
        <Button size="sm" variant="secondary" disabled={disabled || active} onClick={onStart}>
          Record
        </Button>
        <Button size="sm" variant="outline" disabled={disabled || !active} onClick={onStop}>
          Stop
        </Button>
        <Button size="sm" variant="outline" disabled={disabled || !active} onClick={onStopExport}>
          Stop &amp; export
        </Button>
      </div>
      {active ? (
        <p className="cl1-recording-bar__frames mono">
          Frames captured · {frameCount} (cap 6000)
        </p>
      ) : null}
      <p className="cl1-recording-bar__hint">
        Each tick appends 64‑ch frames to RAM. <strong>Stop &amp; export</strong> writes{" "}
        <span className="mono">recordings/*.json</span> (gitignored).
      </p>
    </div>
  );
}
