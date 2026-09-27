# Security and privacy

SameBeat v0.1.0 is a personal, single-user, self-hosted service. It has no OAuth or multi-tenant isolation. A secret MCP URL grants read access to listening metadata and history. Never publish it, even in a screenshot. Generate independent random ingest and MCP credentials; neither is shared with OB.

The Agent uploads only QQ metadata. Other Now Playing data is parsed transiently to identify occlusion and is neither persisted nor sent. Dry-run prints QQ metadata locally. Sharing-off stops uploads but does not erase historical data. Server SQLite history currently has no automatic retention policy. Protect backups, the private env/config files and AI client connections accordingly.

Application access-log filtering is not an end-to-end secrecy guarantee: reverse proxies, tunnel services, monitoring and client/platform logs may record URLs. Configure those separately. If a URL was disclosed, rotate the MCP secret, recreate the service, update private client endpoints and verify the old path fails. Never paste secrets into a public issue; report reproducible problems using synthetic values. No private security contact has been configured for this release candidate.

Ingest requires HTTPS except for exact loopback hosts. Redirects are not followed with the ingest credential. Docker binds to loopback; TLS termination belongs to the configured proxy. Host allowlisting must explicitly include your domain.

`scripts/check_release.py` is a local pattern and file-policy check, not proof that arbitrary secrets cannot exist. Review new material before committing. Real configs, raw logs, database files and keys are excluded. The source directory had no Git history to audit; the release tree is prepared separately.
