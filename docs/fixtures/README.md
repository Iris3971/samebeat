# Sanitized replay fixtures

These JSONL fixtures derive from the original Phase0 recordings. They preserve timing, QQ metadata and state transitions needed by regression tests. Non-QQ titles/artists/albums are replaced with OTHER_APP_PRIVATE_METADATA and the source with org.example.otherplayer. Only explicitly allowlisted playback fields remain; artwork, content identifiers and process identifiers are removed.

The sentinel intentionally remains in the local fixture to verify it never reaches reports or stored history. These are test data, not live logs. Do not add raw recordings or user configuration here.
