"use client";

import {
  CL1_MAX_AMPLITUDE_UA,
  CL1_MAX_CHARGE_NC,
  CL1_MAX_PULSE_WIDTH_US,
  CL1_PULSE_WIDTH_STEP_US,
  CL1_SPIKE_CLAMP
} from "@/lib/simulator/cl1-constants";

export function Cl1SafetyLimits() {
  return (
    <ul className="cl1-safety-list">
      <li>
        <span className="cl1-safety-k">I</span> (0, {CL1_MAX_AMPLITUDE_UA}] µA · amp=0 silence
      </li>
      <li>
        <span className="cl1-safety-k">Pulse</span> (0, {CL1_MAX_PULSE_WIDTH_US}] µs · step {CL1_PULSE_WIDTH_STEP_US} µs
      </li>
      <li>
        <span className="cl1-safety-k">Charge</span> ≤ {CL1_MAX_CHARGE_NC} nC / pulse
      </li>
      <li>
        <span className="cl1-safety-k">Model norm</span> clamp {CL1_SPIKE_CLAMP} → ÷{CL1_SPIKE_CLAMP} (active ch)
      </li>
    </ul>
  );
}
