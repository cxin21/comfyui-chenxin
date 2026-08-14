---
name: minimax-h3-prompt
description: Write and audit model-native MiniMax-H3 text-to-video-with-audio and reference-to-video-with-audio prompts. Use for shot timing, actions, camera transitions, reference ownership, dialogue, sound, and music; never for ComfyUI execution.
---

# MiniMax-H3 Prompt

This skill turns a video brief into a copyable H3 prompt. The LLM authors the story, shots, action, camera, dialogue, and sound; local code validates the temporal and reference invariants and counts the exact tokenizer context. The result is ordinary prompt text, independent of any execution workflow.

## Paths

- `h3_t2va`: text-to-video-with-audio.
- `h3_ref2va`: one- or three-reference-image video with audio.

## Method

1. Lock duration, shot count, state transitions, and final landing states.
2. For references, define ordered `Picture N` owners and retain their appearance consistently.
3. Write executable shots with timestamps, camera behavior, synchronous sound/dialogue, and audio/music separation.
4. Run the deterministic audit and exact context budget check.
5. Copy the returned `text` into any compatible H3 tool.

## Out of scope

No workflow discovery, ComfyUI calls, model/checkpoint selection, execution
registry, or mandatory downstream gate.
