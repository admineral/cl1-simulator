"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FeedbackType } from "@/lib/simulator/types";

export type Cl1FeedbackBarProps = {
  busy: boolean;
  onSend: (payload: {
    feedbackType: FeedbackType;
    channels: number[];
    frequencyHz: number;
    amplitudeUa: number;
    pulses: number;
    unpredictable: boolean;
    eventName: string;
  }) => Promise<void>;
};

const parseCh = (value: string) =>
  value
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map(Number)
    .filter((n) => Number.isInteger(n));

export function Cl1FeedbackBar({ busy, onSend }: Cl1FeedbackBarProps) {
  const [type, setType] = useState<FeedbackType>("reward");
  const [channelsStr, setChannelsStr] = useState("2,3");
  const [frequencyHz, setFrequencyHz] = useState(20);
  const [amplitudeUa, setAmplitudeUa] = useState(0.8);
  const [pulses, setPulses] = useState(1);
  const [unpredictable, setUnpredictable] = useState(false);
  const [eventName, setEventName] = useState("");

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const channels = parseCh(channelsStr);
    await onSend({
      feedbackType: type,
      channels,
      frequencyHz,
      amplitudeUa,
      pulses,
      unpredictable,
      eventName
    });
  };

  return (
    <form className="cl1-feedback" onSubmit={(e) => void submit(e)}>
      <div className="cl1-feedback__head">
        <span className="cl1-feedback__title">Feedback port</span>
        <span className="cl1-feedback__hint">Separate control path · merged on next tick · interrupt clears stim queue</span>
      </div>
      <div className="cl1-feedback__row">
        <label className="cl1-feedback__field">
          <span>Type</span>
          <select
            className="cl1-feedback__select"
            value={type}
            onChange={(e) => setType(e.target.value as FeedbackType)}
            disabled={busy}
          >
            <option value="reward">reward</option>
            <option value="event">event</option>
            <option value="interrupt">interrupt</option>
          </select>
        </label>
        <label className="cl1-feedback__field cl1-feedback__field--grow">
          <span>Channels</span>
          <Input
            className="ctl-input ctl-input--sm"
            value={channelsStr}
            onChange={(e) => setChannelsStr(e.target.value)}
            disabled={busy}
            placeholder="1,2"
          />
        </label>
      </div>
      <div className="cl1-feedback__row">
        <label className="cl1-feedback__field">
          <span>f (Hz)</span>
          <Input
            type="number"
            min={1}
            max={200}
            className="ctl-input ctl-input--xs"
            value={frequencyHz}
            onChange={(e) => setFrequencyHz(Number(e.target.value))}
            disabled={busy}
          />
        </label>
        <label className="cl1-feedback__field">
          <span>I (µA)</span>
          <Input
            type="number"
            min={0}
            max={3}
            step={0.1}
            className="ctl-input ctl-input--xs"
            value={amplitudeUa}
            onChange={(e) => setAmplitudeUa(Number(e.target.value))}
            disabled={busy}
          />
        </label>
        <label className="cl1-feedback__field">
          <span>Pulses</span>
          <Input
            type="number"
            min={1}
            max={999}
            className="ctl-input ctl-input--xs"
            value={pulses}
            onChange={(e) => setPulses(Number(e.target.value))}
            disabled={busy}
          />
        </label>
      </div>
      <label className="cl1-feedback__field cl1-feedback__field--grow">
        <span>Event name (opt.)</span>
        <Input
          className="ctl-input ctl-input--sm"
          value={eventName}
          onChange={(e) => setEventName(e.target.value)}
          disabled={busy}
        />
      </label>
      <label className="cl1-feedback__check">
        <input
          type="checkbox"
          checked={unpredictable}
          onChange={(e) => setUnpredictable(e.target.checked)}
          disabled={busy}
        />
        <span>Unpredictable pattern (metadata)</span>
      </label>
      <Button size="sm" type="submit" disabled={busy}>
        Enqueue feedback
      </Button>
    </form>
  );
}
