# SameBeat v0.1.0

Let the AI you already talk to know what you are listening to.

SameBeat is an AI-agnostic, read-only listening-presence layer for the official QQ Music Mac client. It exposes playback facts through four MCP tools: now_playing, recent_history, track_context and listening_summary.

QQ Music remains the player and source of truth. SameBeat provides senses; OB or another independent system can provide memory; the AI makes judgments. No audio access, lyrics, playback controls, emotion inference or automatic memory writes.

Unknown stays unknown: occluded/offline never means “not listening.” Estimated progress and stale state are labeled. Private self-hosting uses independent ingest and MCP credentials.

This initial release is macOS-only on the Agent side and single-user on the server side. Loop detection is heuristic; client support varies. The candidate passed isolated Docker build, startup and built-in healthcheck on the target VPS. The maintainer confirmed real Mac reboot/autostart and ChatGPT MCP end-to-end revalidation. Hosted CI remains an open pre-publication checklist item; it has not run. See HANDOFF.md for the exact validation status. These notes are a draft; no remote release has been created.
