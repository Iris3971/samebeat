# SameBeat v0.1.0 — release checkpoint

Date: 2026-09-27. Status: **source repository published; v0.1.0 tag and GitHub Release pending**.

## Evidence and source inventory

The current Project Sources mirror contained only two OB reference files, not the requested SameBeat documents. The local SameBeat source directory supplied PLAN, phase0-findings, phase1-agent, phase2-server, phase3-mcp, Agent/Server/MCP code and two replay logs. A separately saved PLAN copy was also read and did not supersede the implemented Phase3 state.

The original directory is not a Git repository: no commits, remotes, tags or Git history could be inspected there. No history was rewritten. This release tree is a separate public preparation copy; original source, running Agent, private config and production deployment were not changed. Synced Project Sources remain read-only.

Phase3 completion is supported by implemented code and historical Claude acceptance records. ChatGPT end-to-end revalidation and real Mac reboot/autostart were explicitly confirmed by the maintainer on 2026-09-27: no manual Agent launch, followed by successful live playback state, song and progress retrieval. Automated acceptance separately verifies the candidate in an isolated container and does not modify production. Historical phase stop instructions were replaced with the present scope; no Phase4/5 work was added.

## Changes

- Bilingual README and Quick Start; AI-agnostic, read-only positioning and five-state semantics.
- Public phase summaries replacing private deployment records; sanitized replay fixtures preserve state transitions without other apps' real media content or system identifiers.
- Blank runtime credentials, configurable public Host allowlist, private-file ignores and Docker build-context allowlist.
- Ingest URL parser validation at startup and hot reload, invalid URL disables sharing, no authenticated redirects, no endpoint/error-detail logging.
- Agent extrapolated heartbeats and pause-only events correctly mark estimated progress.
- MIT license as specified in the original PLAN, using “SameBeat contributors” attribution; VERSION, changelog and draft release notes.
- Local pattern/file-policy scanner, test workflow, exact installed dependency constraints, regression tests.

## Validation performed

- Python 3.13.9, clean temporary environment installed the original pinned server dependencies and httpx 0.28.1. Resolved versions recorded in requirements-lock.txt.
- Agent: **17 tests passed** (11 original replay tests + 4 URL/redirect/logging tests + 2 progress-provenance tests).
- Server/MCP: **38 tests passed** (37 original + all-four-tools transport invocation).
- Total: **55 tests passed**. HTTP/MCP tests use a local in-process ASGI transport, synthetic credentials and temporary SQLite; they are not external connector tests.
- Quick Start Python snippet executed in a temporary directory; two distinct random credentials and mode 0600 verified without displaying values. Example TOML parsed, Python syntax checked, installer shell syntax checked.
- Release content scanner: zero findings. Additional local-only exact comparison against configured ingest token/address: zero matches. Real values were not copied into this tree or printed.
- Original scan found deployment IP/domain references in phase documents and a hard-coded server default. Replaced in the release tree. A non-loopback test IP was synthetic and replaced with loopback.
- This is a targeted pattern scan plus allowlisted export and review, not a formal penetration test or a guarantee against every possible secret. No original Git history existed to scan.

## Acceptance status and remaining publication work

- Docker build, isolated startup and actual built-in healthcheck passed on the target VPS. Twelve internal synthetic API/MCP checks passed; all test resources were cleaned, both production container snapshots and the container/volume/network baselines matched.
- The maintainer additionally confirmed an independent clean build and running/healthy candidate container with a temporary volume, random test credentials, no published ports and complete cleanup. Production SameBeat stayed healthy and OB kept running; this is separate from the automated tmpfs evidence.
- Mac real reboot/autostart and ChatGPT live MCP end-to-end revalidation passed according to the maintainer's explicit report. Claude retains Phase3 historical acceptance evidence. The production deployment was not changed or compared byte-for-byte to the candidate by this task.
- Final local tests: 17 Agent + 38 Server/MCP = **55 passed**. Dependency consistency passed, secret scan and private-value comparison found no matches.
- The reviewed source was committed and pushed to `Iris3971/samebeat`. GitHub Actions `Checks` passed on the initial public commit `bc342ff367ea`; the final documentation-only commit must pass the same workflow before tagging.
- Repository/attribution review and the first commit are complete. No functional blocker was found; the v0.1.0 tag and GitHub Release remain pending.

Some existing Server tests emit unclosed SQLite ResourceWarnings under Python 3.13; tests pass, but fixture cleanup can be improved separately. Natural loop detection remains heuristic and cannot perfectly distinguish a manual seek at the very end. v0.1 is single-user, has no OAuth, and its stored history has no automatic retention policy.

## Resume commands

From the release-tree root, follow README development commands to scan and rerun tests. Inspect `git diff --cached --stat` and `git diff --cached` locally. Review docs/RELEASE_CHECKLIST.md and draft notes before committing. Never copy private deployment files back into this tree. To use the candidate in production, deploy its server code separately and preserve private credentials/data; configure the real public Host privately.

## Third-party dependency and license review

Reviewed 2026-09-27 against the current staged public source tree, imports, subprocess calls, Dockerfile, workflow, requirements and the exact 34 distributions in requirements-lock.txt. Read each installed distribution's shipped license/copyright files and publisher metadata from the clean PyPI environment; version-specific PyPI links below identify the reviewed releases. This is a source-only candidate: it includes no wheels, virtual environment, container image, media-control executable or third-party source tree.

### Usage and provenance

- **media-control 0.7.7** is an external executable invoked with `stream --no-artwork --micros`, not linked, copied or modified. Its [official README](https://github.com/ungive/media-control#license) credits Jonas van den Berg and declares BSD-3-Clause. The [Homebrew formula metadata](https://formulae.brew.sh/api/formula/media-control.json) independently identifies upstream, version 0.7.7 and BSD-3-Clause. The upstream LICENSE link could not be retrieved during this review; the attribution and license identifier are based on those explicit declarations, not an assumed MIT license.
- **mediaremote-adapter** is media-control's upstream component, BSD-3-Clause per its [official license](https://github.com/ungive/mediaremote-adapter/blob/master/LICENSE). SameBeat does not directly import or ship its Perl script/framework. Its use of system Perl and MediaRemote is mediated by the separately installed CLI.
- **MCP** is the interoperability protocol. The actual runtime dependency is the [official Python SDK](https://github.com/modelcontextprotocol/python-sdk/blob/main/LICENSE), MIT, with an upstream Anthropic copyright notice. SameBeat imports its API; no SDK source was found copied or modified in this tree. Using the protocol does not itself mean deriving SameBeat from protocol implementation source.
- Agent Python imports are standard-library only. Server imports FastAPI, Pydantic and the MCP SDK; Uvicorn starts the ASGI service and tzdata supplies a timezone fallback. HTTPX is explicitly installed for tests. Transitive runtime dependencies, including dependencies activated by extras, are listed below.
- Inspection found no vendor directory, submodule, bundled third-party executable/library, third-party source headers or identifiable copied upstream implementation. This is a review finding, not proof of originality of every line: the original source directory had no commit history or provenance ledger.

### Exact Python dependency inventory

Scope is based on the installed Python 3.13 environment and dependency markers/extras. All 34 locked distributions are accounted for; other platforms or future resolutions may differ. Links are publisher release records; license identifiers were checked against the installed release's bundled license text, not inferred from package names.

| Project / reviewed version | Use | License |
|---|---|---|
| [annotated-doc 0.0.5](https://pypi.org/project/annotated-doc/0.0.5/) | transitive runtime dependency | MIT |
| [annotated-types 0.8.0](https://pypi.org/project/annotated-types/0.8.0/) | transitive runtime dependency | MIT |
| [anyio 4.15.1](https://pypi.org/project/anyio/4.15.1/) | transitive runtime dependency | MIT |
| [attrs 26.1.0](https://pypi.org/project/attrs/26.1.0/) | transitive runtime dependency | MIT |
| [certifi 2026.7.22](https://pypi.org/project/certifi/2026.7.22/) | transitive test-only dependency | MPL-2.0 |
| [cffi 2.1.1](https://pypi.org/project/cffi/2.1.1/) | transitive runtime dependency | MIT-0 |
| [click 8.5.0](https://pypi.org/project/click/8.5.0/) | transitive runtime dependency | BSD-3-Clause |
| [cryptography 50.0.1](https://pypi.org/project/cryptography/50.0.1/) | transitive runtime dependency | Apache-2.0 OR BSD-3-Clause |
| [fastapi 0.141.1](https://pypi.org/project/fastapi/0.141.1/) | API framework | MIT |
| [h11 0.16.0](https://pypi.org/project/h11/0.16.0/) | transitive runtime dependency | MIT |
| [httpcore 1.0.9](https://pypi.org/project/httpcore/1.0.9/) | transitive test-only dependency | BSD-3-Clause |
| [httpcore2 2.13.1](https://pypi.org/project/httpcore2/2.13.1/) | transitive runtime dependency | BSD-3-Clause |
| [httpx 0.28.1](https://pypi.org/project/httpx/0.28.1/) | test HTTP client | BSD-3-Clause |
| [httpx2 2.13.1](https://pypi.org/project/httpx2/2.13.1/) | transitive runtime dependency | BSD-3-Clause |
| [idna 3.20](https://pypi.org/project/idna/3.20/) | transitive runtime dependency | BSD-3-Clause |
| [jsonschema 4.26.0](https://pypi.org/project/jsonschema/4.26.0/) | transitive runtime dependency | MIT |
| [jsonschema-specifications 2025.9.1](https://pypi.org/project/jsonschema-specifications/2025.9.1/) | transitive runtime dependency | MIT |
| [mcp 2.2.0](https://pypi.org/project/mcp/2.2.0/) | official MCP server SDK | MIT |
| [mcp-types 2.2.0](https://pypi.org/project/mcp-types/2.2.0/) | transitive runtime dependency | MIT |
| [opentelemetry-api 1.45.0](https://pypi.org/project/opentelemetry-api/1.45.0/) | transitive runtime dependency | Apache-2.0 |
| [pycparser 3.0](https://pypi.org/project/pycparser/3.0/) | transitive runtime dependency | BSD-3-Clause |
| [pydantic 2.13.5](https://pypi.org/project/pydantic/2.13.5/) | request validation | MIT |
| [pydantic_core 2.46.5](https://pypi.org/project/pydantic_core/2.46.5/) | transitive runtime dependency | MIT |
| [PyJWT 2.15.0](https://pypi.org/project/PyJWT/2.15.0/) | transitive runtime dependency | MIT |
| [python-multipart 0.0.32](https://pypi.org/project/python-multipart/0.0.32/) | transitive runtime dependency | Apache-2.0 |
| [referencing 0.37.0](https://pypi.org/project/referencing/0.37.0/) | transitive runtime dependency | MIT |
| [rpds-py 2026.6.3](https://pypi.org/project/rpds-py/2026.6.3/) | transitive runtime dependency | MIT |
| [sse-starlette 3.4.11](https://pypi.org/project/sse-starlette/3.4.11/) | transitive runtime dependency | BSD-3-Clause |
| [starlette 1.7.0](https://pypi.org/project/starlette/1.7.0/) | transitive runtime dependency | BSD-3-Clause |
| [truststore 0.10.4](https://pypi.org/project/truststore/0.10.4/) | transitive runtime dependency | MIT |
| [typing-inspection 0.4.4](https://pypi.org/project/typing-inspection/0.4.4/) | transitive runtime dependency | MIT |
| [typing_extensions 4.16.0](https://pypi.org/project/typing_extensions/4.16.0/) | transitive runtime dependency | PSF-2.0 |
| [tzdata 2026.4](https://pypi.org/project/tzdata/2026.4/) | IANA timezone fallback data | Apache-2.0; underlying IANA data public domain |
| [uvicorn 0.54.0](https://pypi.org/project/uvicorn/0.54.0/) | ASGI runtime | BSD-3-Clause |

The runtime graph contains 31 distributions. HTTPX, httpcore and certifi are test-only in this resolved graph. Some libraries are installed transitively even when SameBeat does not exercise their optional product features; their presence does not mean SameBeat implements OAuth, telemetry export or playback control.

### System, installation and CI dependencies

| Component | Use and license boundary |
|---|---|
| CPython / standard library | Interpreter and Agent runtime, PSF license with historical/included third-party notices; [official licensing](https://docs.python.org/3/license.html). Not included in the source archive. |
| SQLite | Used through Python sqlite3; [public domain](https://www.sqlite.org/copyright.html). No SQLite source/binary included. |
| macOS, MediaRemote, launchd/launchctl, system utilities | External operating-system facilities. Apple's terms apply; SameBeat does not redistribute or relicense them. |
| QQ Music | Separately installed proprietary player and metadata source; no client code, artwork or audio is shipped. |
| Bash | Executes the launchd installer; external interpreter, not copied into the repository. Shell scripts are not a redistribution of the interpreter. |
| Homebrew | Optional installation tool; [BSD-2-Clause](https://github.com/Homebrew/brew/blob/master/LICENSE.txt). Not a runtime Python dependency and not bundled. |
| Docker Engine / Compose | Optional server deployment tooling; [Moby/Docker Engine](https://github.com/moby/moby/blob/master/LICENSE) and [Compose](https://github.com/docker/compose/blob/main/LICENSE) use Apache-2.0 for their own code. Docker Desktop, if chosen, has separate product terms; it is not bundled or required specifically. |
| python:3.13-slim | Docker base image selected at build time; [official packaging](https://github.com/docker-library/python) is MIT, but the image includes CPython and Debian components under multiple licenses. The complete image must not be described as MIT-only. Images were built privately for acceptance and removed afterward; no image was distributed. |
| actions/checkout@v4, actions/setup-python@v5 | CI-only references, both MIT ([checkout](https://github.com/actions/checkout/blob/v4/LICENSE), [setup-python](https://github.com/actions/setup-python/blob/v5/LICENSE)); implementation code is fetched by the runner, not vendored here. |
| pip | Dependency installation tool supplied with the environment; its own vendored dependencies retain their licenses. It is not included in this source archive. |

### MIT compatibility and notices decision

**No license conflict was identified for the current source-only release and dependency usage.** SameBeat's own files can remain MIT; this does not convert any dependency to MIT. No additional third-party LICENSE or NOTICE file is required in this source tree based on the inspected contents, because it does not redistribute the dependencies' code or binaries. README credits are attribution, not a substitute for license notices when redistribution does occur.

- MIT, BSD-2-Clause, BSD-3-Clause and PSF-covered copies must retain the applicable copyright/license/disclaimer notices when redistributed. BSD non-endorsement conditions also remain applicable. cffi's reviewed version declares MIT-0, subject to any separately licensed included components in an actual artifact.
- Apache-2.0 dependencies can be used alongside MIT SameBeat code. When distributing their code/binaries, include the applicable license, preserve required notices, mark changes if any, and carry forward any applicable upstream NOTICE content. Apache obligations and patent terms are not replaced by SameBeat's MIT license. See [Apache section 4](https://www.apache.org/licenses/LICENSE-2.0.txt).
- cryptography offers Apache-2.0 **OR** BSD-3-Clause; both are upstream alternatives, not a requirement to relicense SameBeat. Its native wheels may also include other components whose artifact-specific notices must be preserved.
- certifi's MPL-2.0 does not require independent SameBeat files to become MPL. If distributing certifi or its covered files, retain MPL notices and satisfy the applicable source-availability duties for those files. In this resolved environment it is test-only and absent from the candidate archive. See [Mozilla's official FAQ](https://www.mozilla.org/en-US/MPL/2.0/FAQ/) and [license sections 3.1–3.4](https://www.mozilla.org/en-US/MPL/2.0/).
- tzdata's packaging is Apache-2.0; its underlying IANA timezone data is public domain. Keep the package's own notices when distributing the package.

For a future prebuilt image, app bundle or wheel bundle, audit the **actual artifact**, including native-wheel bundled libraries and all base-image system packages; preserve installed dist-info/licenses and system copyright files, include source-access information where required, and handle applicable NOTICE files. The current unlocked Docker base tag and build-time transitive resolution mean the local lock inventory is not a complete image bill of materials. This is a distribution-specific gate, not a newly discovered blocker for publishing the present source-only archive.

### Outcome

README Credits added; this audit appended to existing HANDOFF; release checklist updated. No application code, dependency versions or SameBeat LICENSE changed, and no unnecessary license-copy directory was created. Subsequent build/runtime, maintainer-reported reboot/ChatGPT checks and hosted CI on the initial public commit passed. The final documentation-only revision still requires its CI rerun before tagging.

### Final acceptance follow-up

See docs/RELEASE_CHECKLIST.md for actual commands, evidence sources and the CI gate analysis. The final candidate archive/checksum are synchronized with the reviewed staged documentation. This task updates documentation only; no application/build/dependency source or workflow changes were needed. Tests and secret scans were rerun after setting up a fresh local environment.

Changed documentation in this acceptance pass: README.md, HANDOFF.md, docs/RELEASE_CHECKLIST.md, docs/RELEASE_NOTES_v0.1.0.md, docs/QUICKSTART.md, docs/PLAN.md, docs/phase1-agent.md and docs/phase3-mcp.md. The source archive and SHA256SUMS outside the repository were refreshed; no new repository files were added. All 37 source files were included in the initial public commit.

The final continuation reused this same workspace and existing candidate. The GitHub repository was created by the maintainer, and the reviewed initial commit was pushed without modifying production resources. Final tests and scans were rerun locally before publication.
