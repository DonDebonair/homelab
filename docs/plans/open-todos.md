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
- ✅ **Seerr** — replaces **overseerr** (superseded by [Seerr](https://seerr.dev/), done 2026-07-06). `requests.dv.zone` now serves `ghcr.io/seerr-team/seerr` (v3.3.0) in place of `sctx/overseerr`; the overseerr `ComposeApp` + `overseerr.yaml.j2` were removed and a fresh `seerr` `ComposeApp` + `seerr.yaml.j2` stand up on a new external `seerr-config` volume (no data carried over — overseerr itself carried nothing over either). Seerr keeps Overseerr's `/api/v1` surface, so the homepage `overseerr` widget is reused, pointed at a fresh API key in `op://Homelab/Seerr/password`. Template adds `init: true` (the image ships no init process upstream). Not behind Authelia — it self-auths via Plex, same as overseerr. ([docker-apps-migration.md](docker-apps-migration.md) overseerr section)

## 4. Per-app functional follow-ups

- ✅ **cwa — native OIDC** (done 2026-07-07). Authelia client `calibre-web` registered in `proxies/vars.py` (redirect `https://books.dv.zone/login/generic/authorized`, `client_secret_basic`, scopes incl. `groups`, no PKCE/claims-policy — CWA reads claims from userinfo), secret in `op://Homelab/Calibre-Web OIDC client/password`, and `import secure *` removed from `cwa.yaml.j2` so native OIDC is the sole gate. **CWA has no env/config-file OIDC** — the provider is configured once in CWA's admin UI (persists in `app.db` on the `cwa-config` volume), so there's nothing in `cwa.yaml.j2`/`apps/secrets.py`. Verified end-to-end (OIDC login works, standard login disabled). Full runbook in [cwa-migration.md](cwa-migration.md) "Follow-ups #1". ([cwa-migration.md](cwa-migration.md) "Follow-ups #1")

## 5. Monitoring follow-ups

All from [monitoring-migration.md](monitoring-migration.md) "Risks / follow-ups".

- ✅ **node-exporter scope** — now reports true host metrics, including host filesystems and NICs (done 2026-07-05). Switched the `node-exporter` service in `prometheus.yaml.j2` to the upstream single-mount pattern: `pid: host` + `network_mode: host` + `/:/host:ro,rslave` bind + `--path.rootfs=/host`, running node-exporter's **default collector set** (same as the apt hosts, so the metric set is consistent and includes `node_uname_info` for the dashboard's host selector). The only docker_vm-specific tuning is `--collector.netdev.device-exclude` + `--collector.netclass.ignored-devices` to drop the ~48 container `veth*`/`br-*` NICs host networking exposes (keeping `ens18`/`macvlan-shim`/`lo`). Because host networking takes it off the monitoring bridge, the Prometheus `nodeexporter` job scrapes it by host IP (`host.data.docker_vm_ip`, new in `group_data/docker_vm.py`) with `instance=docker_vm`; the scrape-config template is flagged `restart_on_change=True` so Prometheus reloads it. Verified: `node_filesystem_size_bytes` shows host mounts, `node_network_*` limited to real NICs, all four targets `up`.
- ✅ **node-exporter on the other hosts** — added to `proxmox_host`, `pbs_vm`, and `postgres_lxc` (done 2026-07-05). New reusable group-agnostic deploy `deploys/common/node_exporter/` installs the distro `prometheus-node-exporter` (apt) + enables the systemd service; wired into those three group blocks in `deploy.py` (deliberately **not** docker_vm — it already binds `:9100` via the compose exporter). Bare-metal/LXC needs none of the container-namespace workarounds, so the default collector set is used. The Prometheus `nodeexporter` job gained one target per host (`proxmox_host`/`pbs_vm`/`postgres_lxc`, IPs from `group_data/all.py`); all four targets verified `up`. Two incidental fixes fell out of this: (1) a pre-existing crash in the PVE `backup_job` op — newer PVE returns `prune-backups` as a JSON object, so the `PVEBackupJobs` fact now normalises it back to CSV (`facts/proxmox/pve.py`, + harness case `one_job_prune_object.json`); (2) the Proxmox host's `/etc/resolv.conf` pointed at the dead `192.168.1.21` resolver — user re-pointed it at the Technitium resolvers (`192.168.50.30` + `192.168.1.210`) via the PVE UI. (Note: apt 3.0.3 on the Proxmox host balloons memory instead of failing fast when a download stalls on unresolvable DNS — it hit ~80 GB RSS before DNS was fixed.)
- ✅ **Node Exporter Full dashboard in Grafana** (done 2026-07-05). Provisioned as-code (grafana.com id 1860, rev 45) via a read-only `/etc/grafana/provisioning` bind mount on the grafana `ComposeApp` + a file provider (`deploys/docker_vm/monitoring/templates/grafana/`); the `ds_prometheus` var is bound to the existing Prometheus datasource (`bdtbm6juuq7swc`). Read-only in the UI, coexists with the DB-stored dashboards. **Gotcha:** Grafana 13 uses unified storage — provisioned dashboards don't show up in the legacy `dashboard` SQL table and get a generated `resource` name with a compressed `value`, so verify via the UI/API, **not** by querying storage tables. All four hosts appear in the dashboard's selector once each exports `node_uname_info`.

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
