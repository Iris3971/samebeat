# v0.1.0 release checklist

## Prepared locally

- [x] Read PLAN and Phase0–3 evidence; distinguish historical client acceptance from current tests.
- [x] Inventory source; record absence of original Git history.
- [x] Remove private deployment references; exclude real configs, logs, databases and key material.
- [x] Sanitize regression recordings; retain non-QQ sentinel leak assertions.
- [x] README / Quick Start / examples / MIT license / HANDOFF / VERSION / draft notes.
- [x] 55 local tests pass, including all four MCP tools.
- [x] URL hot-reload/redirect safety and estimated-position provenance regression coverage.
- [x] Quick Start credential generation and config formats validated.
- [x] Content scan clean and local private-config exact comparison clean.
- [x] Prepare source candidate archive and SHA-256 checksum outside the repository.

- [x] Third-party dependency/license review and concise Credits; source-only redistribution decision recorded in HANDOFF.

## Before the final tag and publication

- [x] Build the current Dockerfile from clean public source on the target VPS, without cache; isolated build-only acceptance passed on 2026-09-27.
- [x] Isolated container startup and actual Docker healthcheck: healthy, with disposable credentials, no published ports, network=none, and tmpfs-only test data; 12 internal smoke checks passed.
- [ ] Run hosted CI on the final source revision.
- [x] Maintainer independently confirmed clean candidate build (exit 0), running/healthy container with a disposable volume, complete cleanup and production service continuity.
- [x] Mac reboot/login autostart: maintainer confirmed a real reboot with no manual Agent launch on 2026-09-27.
- [x] ChatGPT MCP end-to-end revalidation: maintainer confirmed live QQ Music state, song and progress after that reboot; Claude retains historical Phase3 acceptance.
- [ ] Review the staged public source and license attribution; select repository owner/name.
- [ ] Commit reviewed files; verify a clean worktree and rescan the exact tagged tree.
- [ ] Create v0.1.0 tag from the validated commit; build the final archive from that tag.
- [ ] Publish release with docs/RELEASE_NOTES_v0.1.0.md, replacing draft-status text only after remaining gates pass.

The prepared archive is a **candidate**, not evidence that the remaining release gates passed. No push, public release or production change has been performed.

If distributing a prebuilt image or bundled dependencies, audit the exact image/packages and retain their licenses, copyright/NOTICE material and any required source-access information before publishing that additional artifact. The current candidate contains source only.

## Docker acceptance attempt — 2026-09-27

Run from the repository root:

```sh
docker version
docker compose version
docker build --progress=plain -t samebeat-acceptance:local ./server
```

All three commands returned exit status 127 (`command not found: docker`). Checked PATH, standard Docker Desktop/OrbStack application and CLI locations, alternative runtime commands and the default Docker socket; no container runtime was found. No Docker remote host/context was configured in the environment.

**Result: BLOCKED before build, not a Dockerfile/build failure.** No image was built; container start, healthcheck, volume permissions and container-level API/MCP acceptance remain untested. No application/build files were modified and no tests were rerun for this environment-only failure. Install or provide an approved Docker-compatible runtime with Compose, then rerun the commands and the start/healthcheck acceptance. Existing release gates remain unchanged. No public repository, tag or release was created.

## Isolated target-VPS Docker build acceptance — 2026-09-27

**PASS — build only.** Docker Engine 29.1.3; Compose 2.40.3+ds1-0ubuntu1~24.04.1 was present but was not used to start, stop or recreate anything. buildx was absent, so the installed legacy builder was explicitly selected. Its deprecation warning is informational; no runtime or plugin was installed.

A fresh remote temporary directory was created with Python `tempfile.mkdtemp(prefix="samebeat-build-acceptance-")`. Only six files were exported from the local Git index, with working-tree byte equality verified, and transferred over the existing SSH connection into `$WORK/context`: `.dockerignore`, `Dockerfile`, `requirements.txt`, `app.py`, `store.py`, `mcp_tools.py`. The same files were SHA-256 checked against the remote context after execution. No `.env`, secret, production directory, database or volume was used as build input.

Actual build command (only the generated temporary path is represented as `$WORK`):

```sh
DOCKER_BUILDKIT=0 docker build --no-cache --force-rm   --memory=384m --cpu-period=100000 --cpu-quota=50000   --iidfile "$WORK/image.id" "$WORK/context"
```

Result: all 12 Dockerfile steps completed, exit code **0**, elapsed **26.4 seconds**. Dependencies installed successfully. Image metadata inspection confirmed `USER samebeat`, the intended Uvicorn command and the configured healthcheck. This metadata check is **not** execution of the service or healthcheck. `--no-cache` disables instruction cache reuse; an existing base image may be reused. This was a clean-source build, not a claim of a newly pulled base or digest-pinned reproducibility.

Read-only verification commands included `docker version --format '{{.Server.Version}}'`, `docker compose version --short`, `docker buildx version`, `docker ps -aq`, selected-field `docker inspect`, and `docker image inspect`. No production environment variables were read or printed. Container comparison covered IDs, image IDs, status, start times, restart counts, port bindings, mounts and network configuration; both existing containers matched before/after. No additional containers remained.

Cleanup used `docker image rm <image-id>` without force, only for image IDs emitted by this build that were absent before it; pre-existing images were excluded. `--force-rm` removed build intermediate containers. The temporary directory was removed with Python `shutil.rmtree` on that exact generated path. Cleanup returned no errors and reinspection found none of this build's new image IDs remaining. No global prune, Compose up/down, production container operation, `.env`/SQLite/volume/proxy/network configuration change, image push, Git tag or hosted release was performed.

At that build-only checkpoint, no SameBeat application, dependency or Dockerfile repair was needed and tests were not rerun. The subsequent runtime and final validation below supersede its then-pending startup, reboot and ChatGPT items. The earlier local-machine environment failure above is retained as history and is superseded for the **build** gate by this successful target-VPS run.

## Isolated container runtime and final acceptance — 2026-09-27

**PASS.** Rebuilt the same six-file clean context with the previously recorded no-cache command: Docker 29.1.3, exit 0, 12 build steps, 31.2 seconds. Context hashes matched current candidate source; no build/application repair was necessary.

Two independent random disposable credentials were generated remotely in a private temporary `test.env` (mode 0600). No production `.env` or database was read or copied. `$TEST_CONTAINER` was a unique generated test name; `$IMAGE_ID` was this build's image ID. Actual startup command, with only generated identifiers/paths replaced by variables:

```sh
docker run --detach --name "$TEST_CONTAINER" --network=none --restart=no \
  --memory=192m --cpus=0.25 --pids-limit=64 --read-only \
  --cap-drop=ALL --security-opt=no-new-privileges \
  --tmpfs /data:rw,noexec,nosuid,size=16m,uid=10001,mode=0700 \
  --tmpfs /tmp:rw,noexec,nosuid,size=16m,mode=1777 \
  --env-file "$WORK/test.env" "$IMAGE_ID"
```

No `-p`, host bind mount, existing volume, production network or proxy route was used. The image's own scheduled HEALTHCHECK reached **healthy**, restart count **0**. `docker exec -i "$TEST_CONTAINER" python -` ran standard-library HTTP checks against container-local loopback with synthetic listening data; it did not contact external MCP clients.

All **12 smoke checks** passed: non-root UID 10001; healthz HTTP 200; unauthenticated state rejection; unauthenticated ingest rejection; authenticated ingest/state round trip; writable isolated SQLite; exactly four read-only MCP tools listed; successful calls to listening_summary, now_playing, recent_history and track_context; invalid MCP path rejection. This verifies a container using temporary memory-backed data, not a production Compose migration or named-volume persistence test.

Cleanup removed only the uniquely named test container (`docker container rm --force "$TEST_CONTAINER"`), newly built image IDs without force, and the exact generated temporary directory. No global prune or Compose up/down was used. Both pre-existing production container snapshots matched afterward (identity, image, status, start time, restart count, ports, mounts and networks); container/volume sets and network inspections matched the baseline. No temporary images, extra containers or test directory remained; cleanup errors: **0**.

### Maintainer-provided real-device acceptance

The maintainer explicitly reported a completed physical Mac reboot, no manual SameBeat Agent launch, and successful live playback-state/song/progress retrieval in ChatGPT after QQ Music playback. Record **Mac autostart PASS** and **ChatGPT end-to-end revalidation PASS**. This evidence comes from the maintainer's real environment, while the candidate container checks above use isolated synthetic data. No production deployment change or byte-for-byte production/candidate comparison was performed by this task; do not misrepresent those separate evidence sources.

### Additional maintainer-provided isolated-volume acceptance

The maintainer reports that, during the interruption, the current Mac release candidate source was freshly uploaded into a separate VPS temporary directory and clean-built with exit 0. The new image was started in an independent temporary container with random test secrets and a separate temporary volume, without publishing host ports, reading the production `.env`, or connecting to/modifying OB. Final observed status was `STATUS=running HEALTH=healthy`. The temporary container, image, volume and test directory were deleted afterward. Production `samebeat` remained healthy and `ombre-brain` continued running normally.

Record this as **PASS, maintainer-provided evidence**. It is a distinct volume-based acceptance run, not a rewrite of the previously recorded automated tmpfs run. The supplied report did not include full commands, image digest or timings, so none are invented here. This continuation made no new remote connection or production operation.

### Hosted CI: exact gate interpretation

The existing checklist places `Run hosted CI on the final source revision` under `Before the final tag and publication`. It therefore remains an **open pre-publication checklist item**. However, neither the original PLAN nor this repository specifies that a hosted CI result is an explicit non-waivable v0.1.0 hard blocker, and no `must pass`/required-status-check policy is defined in repository files. The workflow runs tests on push/pull_request; a workflow's existence alone does not prove remote branch protection. This local repository currently has no remote and no commit, so no hosted required-check configuration or CI result was verified.

Hosted CI was introduced during release preparation, rather than inherited from the original product acceptance criteria. This task does not silently waive or remove it and does not label local tests as hosted CI. Before publication, either run it on the intended remote revision or have the maintainer explicitly resolve its checklist status. No repository was created or published to obtain CI.

### Final local verification and readiness

- Fresh Python 3.13 environment installed declared dependencies under requirements-lock.txt; `pip check` passed.
- `python -m unittest discover -s agent -p 'test_*.py'`: **17 passed**.
- `python -m unittest discover -s server -p 'test_*.py'`: **38 passed**.
- Total **55/55 passed**; existing SQLite fixture ResourceWarnings do not fail tests.
- `python scripts/check_release.py`: **0 findings**. Exact-match comparison against local configured ingest credential/address and documented VPS address: **0 files matched**, values never printed. Production secret files were not read.
- Reviewed working/staged diff and status; no application, dependency, Dockerfile or workflow change in this acceptance pass. Documentation updates are staged with the existing initial candidate, with no commit/tag/remote created. The candidate archive and checksum are refreshed from that staged source; extracted content is checked against it and rescanned.

Functional acceptance requested here has passed. Remaining publication work: resolve the open hosted-CI item, select/review the target repository and attribution, then commit/tag/publish only when authorized. No new functional or secret-scan blocker was found. Public image redistribution still requires its own artifact/license audit; this candidate remains source-only.
