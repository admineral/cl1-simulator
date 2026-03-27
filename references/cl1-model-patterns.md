# CL1 Model Patterns

## Why this pattern exists

The biological bottleneck is non-differentiable, noisy, low-bandwidth, and stateful. Small metric improvements can come from readout shortcuts rather than useful spike information. Preserve the evaluation logic before optimizing architecture details.

## Default baseline

- Use a learned stim policy on the input side.
- Use a separate readout head or task head on the spike side.
- Update the stim policy with REINFORCE or another gradient-free method.
- Update the readout head with supervised, self-supervised, or RL-style losses as appropriate.
- Keep `batch_size = 1` for live CL1 interaction.

Reasonable starting defaults:

- Reward: task-appropriate objective metrics such as `MSE`, `SSIM`, classification accuracy, task success, or other scalar objectives
- REINFORCE baseline: exponential moving average with decay `0.99`
- Spike normalization: clamp to `35.0`, then divide by `35.0`
- Stimulation intensity: start conservatively and only move toward higher amplitudes, pulse widths, or frequencies after re-checking the current official docs and validating against the published limits

## Same Frame Encoding

Use SFE when repeated presentation of the same input through different encodings may help drive richer spike structure. Do not assume it is required for every task.

Example SFE split:

- `full`: a direct view of the input
- `spatial`: an edge- or structure-focused view
- `color`: a chroma- or feature-isolated view

Important properties:

- Each round has its own policy head.
- The readout head receives concatenated spike rounds.
- A spatial readout can reshape each round into a grid that reflects the active-channel layout.

That spatial reshape is useful only when channel locality matters for the task. For non-spatial tasks, a simpler readout may be better.

## Readout design and ablations

Start with a deliberately constrained readout. For spatial tasks, one good baseline uses:

- Conv stack on spike grids
- Bilinear upsample `8 -> 16 -> 32 -> 64`
- GroupNorm instead of BatchNorm because training runs at `batch_size = 1`
- Prefer `bias=False` in readout layers unless there is a clear task-specific reason to keep bias terms
- No class conditioning by default

For non-spatial tasks, use the smallest head that can express the task without giving it easy shortcuts.

Run the noise ablation before trusting the readout:

- Replace real CL1 spikes with random noise.
- Train the readout on the same targets.
- Compare real-training metrics against the noise baseline.

Also consider:

- zero ablation: replace spikes with zeros to measure what the readout can do with no biological signal
- shuffled ablation: preserve spike statistics while breaking time or sample correspondence
- frozen-readout or frozen-stim ablations when separating where adaptation is really happening

Interpretation:

- If real CL1 training does not beat the noise ablation, the readout is likely ignoring spikes.
- If both runs are weak, the readout may be too small or the task too hard.
- If the readout is too large, it can memorize dataset structure and fake progress.

Use the smallest readout that still lets real CL1 training measurably outperform the ablation.

## Feedback channels

Feedback can be packed into the next stim message or sent over a separate control path such as a different port, depending on the system design.

Feedback can be scaled from either direct reward or surprise relative to reward.

Common options:

- Scale positive or negative feedback directly from an objective reward such as `MSE`, `SSIM`, classification accuracy, or task success.
- Scale feedback from EMA surprise to reward, where surprise is the distance between observed reward and an EMA or learned expectation.
- Use PPO or another RL method to train a value network, then scale feedback from prediction error or surprise relative to that value estimate.
- Use event-specific feedback settings when certain task events deserve different channels, pulse counts, or scaling rules.
- Use interrupt feedback when a system needs to stop or override currently active stimulation before delivering a new negative or corrective signal.

Positive feedback patterns:

- Synchronous or structured stimulation
- Frequency and amplitude scale with reward quality or positive surprise

Negative feedback patterns:

- Chaotic or heterogeneous stimulation
- Frequency and amplitude scale with error severity or negative surprise

Neutral feedback:

- Send silence or low-impact stimulation when no meaningful reinforcement signal should be delivered

Implementation guidance:

- keep reward feedback and event feedback logically separate even if they share channels
- make feedback packet types explicit instead of overloading one generic message
- log surprise magnitudes and resulting scales so tuning does not become guesswork

## Hardware-aware training heuristics

- Insert a pause between clips so cells can settle. `1.0 s` is a reasonable starting point.
- Shuffle clips, not individual frames, so clip order remains coherent inside each video.
- Preload datasets into memory if I/O jitter would contaminate timing.
- Enforce rest cycles. A practical starting point is `2.5 hr` of training followed by `1 hr` of rest.
- Save checkpoints often enough that device interruptions do not waste long runs. Every `500` steps is a reasonable starting point.
- If a training policy pushes stimulation values toward the documented limits, re-check the current official docs, validate those values online, and consider clipping or refusing them before dispatch.
- Prefer simple remote observability during long runs: packet counters, spike summaries, feedback logs, and lightweight image or state streams if the task has a visual component.

## Things that are easy for an LLM to miss

- The readout can "cheat" even when metrics look plausible.
- Biological noise and readout overfitting look similar unless you run ablations.
- Feedback is delayed by one step because it is packed into the next stim command.
- The dead-channel mask changes the true learned spike dimension from `64` to `59`.
- Preserving intra-clip order matters because the system includes inter-clip settling pauses.
- Event and feedback routing often belong on the control plane, not in the main stim packet.
- Reusing SDK stimulation objects can materially reduce overhead in long-running loops.
