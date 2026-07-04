# Open TODOs — homelab

A single index of the outstanding follow-ups scattered across the individual
plan docs in `docs/plans/`. Each item links to the source doc, which keeps the
full detail/runbook — this file is just the master list so nothing gets lost.

Status legend: ⬜ not started · 🔶 in progress / partially done · ✅ done

Last reviewed: 2026-07-04.

---

## 1. NAS / Ansible decommissioning

✅ **Runtime decommission done.** Every app migrated to `docker_vm` has had its
NAS container **stopped and removed**, and its NAS bind-mount data
**deleted** (dozzle, miniflux, paperless, forgejo, portainer, tautulli, pgadmin,
pinchflat, n8n, nocodb, cwa, qbittorrent, sabnzbd, and the monitoring stack).
Nothing is left running on the NAS for these.

The Ansible **config** (entries in `roles/docker-apps`, `roles/monitoring`,
`roles/proxies`, the `nas.yml` app lists, per-app `*.yml.j2` templates, etc.) is
**intentionally kept in place** — see the repo-split TODO in §7. It is no longer
tracked as per-app removal work here.

✅ **Cloudflare tunnel flipped** to the docker_vm proxy — external traffic no
longer routes through the NAS. Nothing left in this section.

## 2. Remaining app migrations (NAS → docker_vm)

✅ **All 16 migratable apps are ported** (nocodb, the last one, done 2026-07-03).
Nothing left here — remaining work is the fresh-app stand-ups that supersede
migrated apps (§3). Tracked in full in
[docker-apps-migration.md](docker-apps-migration.md).

## 3. New apps to stand up (fresh, not migrations)

- ⬜ **Shelfmark** — replaces `cwa-dl` (superseded). Stand up fresh on docker_vm (own `ComposeApp` + template), pointed at the same `/srv/docker/volumes/cwa/ingest` bind so downloads flow into CWA's auto-ingest. No `cwa-dl` config/state carried over. Then decommission the NAS `cwa-dl` stack + its `cloudflarebypass` sidecar. Check whether Shelfmark still needs a cloudflare-bypass sidecar or bundles it. ([cwa-migration.md](cwa-migration.md) "Follow-ups #2")
- ⬜ **Seerr** — replaces **overseerr** (superseded by [Seerr](https://seerr.dev/)). Migrate `requests.dv.zone` off `sctx/overseerr` onto Seerr. Low-cost swap since overseerr was a fresh install with little state. ([docker-apps-migration.md](docker-apps-migration.md) overseerr section)

## 4. Per-app functional follow-ups

- ⬜ **cwa — native OIDC.** Currently only Authelia forward-auth at the proxy; add CWA's native OIDC client against Authelia (Authelia client in `proxies/vars.py`, secret in 1Password + `apps/secrets.py`, OAuth env in `cwa.yaml.j2`) so SSO identities map to CWA users/permissions. ([cwa-migration.md](cwa-migration.md) "Follow-ups #1")

## 5. Monitoring follow-ups

All from [monitoring-migration.md](monitoring-migration.md) "Risks / follow-ups".

- ⬜ **node-exporter scope** — ported verbatim (container-namespaced metrics, no host `/proc`,`/sys`,`/` mounts, no `pid: host`). Add host mounts + `pid: host` if true host metrics are wanted.

## 6. DNS follow-ups

From [technitium-dns.md](technitium-dns.md) "Out of scope (future phases)".

- ✅ **Second Technitium instance on `nas` → form a cluster** (done 2026-07-04). Detailed as
  **Phase 2** of [technitium-dns.md](technitium-dns.md). docker_vm primary renamed
  `dns.dv.zone`→`dns1.dv.zone`; NAS secondary `dns2.dv.zone` up at macvlan `192.168.1.210`; SSO
  on both; cluster domain `cluster.dv.zone` with `dns1/dns2.cluster.dv.zone` served by caddy
  (multi-domain) with valid LE certs. **Cluster formed and working** (config/blocklists/users
  sync primary→secondary). Only follow-up left: add `192.168.1.210` as a secondary resolver in
  the router's DHCP scope so LAN clients actually fail over (manual, outside pyinfra).

## 7. Infra / tooling

- ✅ **Split the repo in two** (done 2026-07-04) — the legacy Ansible setup was carved into its own repo (`homelab-old`) and this repo (`homelab`) is now the pyinfra-only setup. A full-history archive of the original combined repo lives in `homelab-evolution-archive`. All three had secrets scrubbed before `homelab`/`homelab-old` were made public (`homelab-evolution-archive` stays private).
- ⬜ **Renovate** — automate Docker image version bumps once all apps are off Ansible onto docker_vm (replaces the dropped `watchtower`). ([CLAUDE.md](../../CLAUDE.md) "Docker image versioning"; [docker-apps-migration.md](docker-apps-migration.md) tracker)
- ⬜ **Shared external NFS volume op** — qbittorrent/sabnzbd/etc. each keep their own inline `NfsVolume` for `/volume1/entertainment` because pyinfra's built-in `docker.volume` can't set `--opt` driver options. A custom op for a shared external NFS volume would be tidier. Deferred. ([docker-apps-migration.md](docker-apps-migration.md) NFS notes)
