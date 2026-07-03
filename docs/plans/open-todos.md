# Open TODOs — homelab

A single index of the outstanding follow-ups scattered across the individual
plan docs in `docs/plans/`. Each item links to the source doc, which keeps the
full detail/runbook — this file is just the master list so nothing gets lost.

Status legend: ⬜ not started · 🔶 in progress / partially done

Last reviewed: 2026-07-03.

---

## 1. NAS / Ansible decommissioning

Every app migrated to `docker_vm` was left **stopped-but-present** on the NAS
(kept as a fallback for a few days). Once confident, decommission each: stop the
NAS container, remove its entry from `roles/docker-apps/vars/main.yml` (+ delete
the `roles/docker-apps/templates/<app>.yml.j2`), and only then delete its NAS
data dir. Then flip nothing else — the tracker rows are already ✅.

- ⬜ **dozzle** — remove from NAS / Ansible `roles/docker-apps`. ([docker-apps-migration.md](docker-apps-migration.md) "Out of scope")
- ⬜ **miniflux** — Ansible config left in place as fallback; decommission.
- ⬜ **paperless** — stop NAS containers, remove `paperless` from `roles/docker-apps/`, then delete `/volume2/docker/paperless`. ([paperless-migration.md](paperless-migration.md) "Follow-ups")
- ⬜ **forgejo** — stop NAS container, remove entry + template, then delete `/volume2/docker/forgejo` and `forgejo-db.dump`. ([forgejo-migration.md](forgejo-migration.md) "Decommission")
- ⬜ **portainer** — NAS/Ansible portainer decommission.
- ⬜ **tautulli** — left stopped-but-present; Ansible decommission.
- ⬜ **pgadmin** — left stopped-but-present; Ansible decommission.
- ⬜ **pinchflat** — left stopped-but-present; Ansible decommission.
- ⬜ **cwa** — stop/remove NAS `cwa` stack + entry (`nas.yml` apps list + `roles/docker-apps/templates/cwa.yml.j2`); keep `/volume2/docker/cwa/config` + old library path until confident, then clean up. ([cwa-migration.md](cwa-migration.md) "Decommission")
- ⬜ **qbittorrent / sabnzbd** — decommission NAS instances after verifying downloads land in the shared NFS tree. ([docker-apps-migration.md](docker-apps-migration.md))
- ⬜ **Caddy proxies (NAS)** — the Ansible `proxies` role still re-creates the Caddy stack on the NAS when `nas.yml` runs; comment it out of `nas.yml` (or remove it) now that docker_vm serves the proxies. Flip any Cloudflare DNS still aimed at NAS macvlan IPs to the docker_vm IPs (192.168.50.20/.21). ([caddy-proxies-migration.md](caddy-proxies-migration.md) "Cut-over notes")
- ⬜ **pi-hole + `roles/dns-setup`** — decommission once Technitium DNS is fully cut over. ([technitium-dns.md](technitium-dns.md) "Out of scope")
- ⬜ **NAS monitoring** — remove `roles/monitoring/`, the Loki bits in `roles/docker-setup/`, the NAS `dockerd.json` log-driver override, then drop the stale NAS containers/volumes. ([monitoring-migration.md](monitoring-migration.md) "Step 7")

## 2. Remaining app migrations (NAS → docker_vm)

Tracked in full in [docker-apps-migration.md](docker-apps-migration.md).

- ⬜ **nocodb** — postgres-backed (`postgres_lxc` DB + user), `nocodb` vol, secrets. Reuses the NAS→postgres_lxc dump/restore path.
- ⬜ **n8n** — postgres-backed, `n8n` vol (uid/gid 1000), secrets.

## 3. New apps to stand up (fresh, not migrations)

- ⬜ **Shelfmark** — replaces `cwa-dl` (superseded). Stand up fresh on docker_vm (own `ComposeApp` + template), pointed at the same `/srv/docker/volumes/cwa/ingest` bind so downloads flow into CWA's auto-ingest. No `cwa-dl` config/state carried over. Then decommission the NAS `cwa-dl` stack + its `cloudflarebypass` sidecar. Check whether Shelfmark still needs a cloudflare-bypass sidecar or bundles it. ([cwa-migration.md](cwa-migration.md) "Follow-ups #2")
- ⬜ **Seerr** — replaces **overseerr** (superseded by [Seerr](https://seerr.dev/)). Migrate `requests.dv.zone` off `sctx/overseerr` onto Seerr. Low-cost swap since overseerr was a fresh install with little state. ([docker-apps-migration.md](docker-apps-migration.md) overseerr section)

## 4. Per-app functional follow-ups

- ⬜ **pgadmin** — repoint the migrated `PostgreSQL Main` server (host `postgres-db`, unresolvable on the VM) to a reachable IP (`192.168.1.195` NAS pg / `192.168.1.41` postgres_lxc). UI step. ([docker-apps-migration.md](docker-apps-migration.md) pgadmin section)
- ⬜ **cwa — native OIDC.** Currently only Authelia forward-auth at the proxy; add CWA's native OIDC client against Authelia (Authelia client in `proxies/vars.py`, secret in 1Password + `apps/secrets.py`, OAuth env in `cwa.yaml.j2`) so SSO identities map to CWA users/permissions. ([cwa-migration.md](cwa-migration.md) "Follow-ups #1")
- ⬜ **paperless — homepage widget.** Optionally regenerate a Paperless API token and add it as `homepage.widget.key` (the NAS's hardcoded key was dropped). ([paperless-migration.md](paperless-migration.md) "Follow-ups")
- ⬜ **paperless — cleanup.** Remove the leftover import dump: `sudo rm -rf /srv/docker/volumes/paperless/export/*` on docker_vm (~2.9 G; data now in `paperless-media`). ([paperless-migration.md](paperless-migration.md))

## 5. Monitoring follow-ups

All from [monitoring-migration.md](monitoring-migration.md) "Risks / follow-ups".

- ⬜ **snmp_exporter config compat** — `snmp.j2` is the NAS-generated config; if snmp-exporter v0.30.1 rejects it, regenerate with the matching `generator` or pin an older snmp-exporter.
- ⬜ **node-exporter scope** — ported verbatim (container-namespaced metrics, no host `/proc`,`/sys`,`/` mounts, no `pid: host`). Add host mounts + `pid: host` if true host metrics are wanted.
- ⬜ **Loki volume ownership** — if Loki logs permission errors writing `/loki/chunks` on first start, `chown` the fresh `loki-data` volume to the image's loki uid.
- ⬜ **Dozzle** — redundant once logs live in Loki; either drop it or override its service back to the `json-file` log driver if you still want `docker logs`.

## 6. DNS follow-ups

From [technitium-dns.md](technitium-dns.md) "Out of scope (future phases)".

- ⬜ **Second Technitium instance on `nas` → form a cluster.** Stand up a second Technitium instance on the NAS and cluster it with the docker_vm instance for HA/redundancy (config + zone sync across nodes). Add `dns_ip` to `group_data/nas.py`, call `setup_technitium_dns()` in the `nas` block (same `deploys/dns/` code), then configure clustering per [Understanding Clustering in Technitium](https://blog.technitium.com/2025/11/understanding-clustering-and-how-to.html).
- ⬜ **pi-hole decommission** — see §1.

## 7. Infra / tooling

- ⬜ **Renovate** — automate Docker image version bumps once all apps are off Ansible onto docker_vm (replaces the dropped `watchtower`). ([CLAUDE.md](../../CLAUDE.md) "Docker image versioning"; [docker-apps-migration.md](docker-apps-migration.md) tracker)
- ⬜ **Shared external NFS volume op** — qbittorrent/sabnzbd/etc. each keep their own inline `NfsVolume` for `/volume1/entertainment` because pyinfra's built-in `docker.volume` can't set `--opt` driver options. A custom op for a shared external NFS volume would be tidier. Deferred. ([docker-apps-migration.md](docker-apps-migration.md) NFS notes)
