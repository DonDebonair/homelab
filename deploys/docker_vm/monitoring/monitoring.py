from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, TemplateFile

# Versions pinned explicitly (no :latest) per CLAUDE.md "Docker image versioning".
# Sidecar images (node-exporter, snmp-exporter, cadvisor) and the loki log
# driver are pinned inline in templates/deploys where they're declared.

# As-code Grafana dashboards, provisioned as raw JSON files (see the generic
# `file-provisioned` provider in templates/grafana/dashboards-provider.yaml.j2).
# Each path is relative to files/grafana/; the leading "<Folder>/" segment is
# BOTH the on-disk subdir and -- via foldersFromFilesStructure -- the Grafana
# folder the dashboard lands in, so src, dest and folder stay in sync from one
# list. Downloaded from grafana.com / GitHub, then normalised: __inputs/
# __requires/__elements stripped, id=null, and the Prometheus datasource bound
# to this stack's uid (see the normalisation notes in the monitoring plan doc).
_dashboard_files = [
    "Node Exporter/node-exporter-full.json",   # grafana.com 1860
    "Synology/synology-comprehensive.json",     # github: wozniakpawel
    "Synology/synology-nas-details.json",        # grafana.com 14284
    "Synology/synology-snmp.json",               # grafana.com 18643
    "cAdvisor/cadvisor-dashboard.json",          # grafana.com 19792
    "cAdvisor/cadvisor-docker-insights.json",    # grafana.com 19908
]

apps = [
    ComposeApp(
        name="loki",
        image="grafana/loki",
        version="3.7.3",
        volumes=[
            # Old NAS chunks aren't migrated, but the logs accumulated here going
            # forward matter -> external=True keeps `down -v` from wiping them.
            NamedVolume(name="loki-data", mount_path="/loki", external=True),
            # Rendered loki-config.yaml lives in this dir, bind-mounted read-only.
            BindMount(source="loki/config", mount_path="/etc/loki", read_only=True),
        ],
        templates=[
            TemplateFile(src="loki-config.yaml", dest="loki/config/loki-config.yaml"),
        ],
    ),
    ComposeApp(
        name="prometheus",
        image="prom/prometheus",
        version="v3.12.0",
        domain="prometheus.dv.zone",
        volumes=[
            # Old NAS TSDB isn't migrated, but the metrics gathered here going
            # forward matter -> external=True keeps `down -v` from wiping them.
            NamedVolume(name="prometheus-data", mount_path="/prometheus", external=True),
            # Rendered scrape config + snmp_exporter config, bind-mounted read-only.
            BindMount(source="prometheus/config", mount_path="/etc/prometheus", read_only=True),
            BindMount(source="snmp", mount_path="/etc/snmp_exporter", read_only=True),
        ],
        templates=[
            # Prometheus reads its scrape config only at startup, and `compose up
            # -d` won't recreate the container when only a bind-mounted file's
            # content changes -> restart the primary service when it changes.
            TemplateFile(
                src="prometheus-config.yml",
                dest="prometheus/config/prometheus.yml",
                restart_on_change=True,
            ),
            TemplateFile(src="snmp.yml", dest="snmp/snmp.yml"),
        ],
    ),
    ComposeApp(
        name="grafana",
        image="grafana/grafana",
        # Bumped from the NAS's 11.1.1 to the current latest stable; the Postgres
        # schema auto-migrates on first start.
        version="13.1.0",
        domain="grafana.dv.zone",
        volumes=[
            # Plugins/renders only -- users/datasources and hand-built dashboards
            # live in the migrated Postgres DB, so this volume is low-recovery-cost.
            NamedVolume(name="grafana-data", mount_path="/var/lib/grafana"),
            # Provisioned (as-code) dashboards, read-only. These are loaded from
            # disk and re-synced by Grafana; they coexist with the DB dashboards
            # without touching them. See templates/grafana/.
            BindMount(
                source="grafana/provisioning",
                mount_path="/etc/grafana/provisioning",
                read_only=True,
            ),
        ],
        templates=[
            # Provider config is read only at startup -> restart grafana on change.
            TemplateFile(
                src="grafana/dashboards-provider.yaml",
                dest="grafana/provisioning/dashboards/dashboards-provider.yaml",
                restart_on_change=True,
            ),
        ],
        # Raw copies (not templates) -- the dashboard JSON has no Jinja, and
        # running it through the renderer would only risk a false hit on the
        # [[ ]]/[% %] delimiters. The generic file provider auto-reloads them on
        # its poll interval, so no restart is needed on change.
        files=[
            TemplateFile(
                src=f"grafana/{p}",
                dest=f"grafana/provisioning/dashboards/json/{p}",
            )
            for p in _dashboard_files
        ],
    ),
]
