from deploys.common.docker_compose.models import ComposeApp, BindMount, NamedVolume, TemplateFile

# Versions pinned explicitly (no :latest) per CLAUDE.md "Docker image versioning".
# Sidecar images (node-exporter, snmp-exporter, cadvisor) and the loki log
# driver are pinned inline in templates/deploys where they're declared.

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
            # "Node Exporter Full" (grafana.com id 1860, rev 45), bound to the
            # existing Prometheus datasource. The file provider auto-reloads
            # dashboard JSON on its poll interval, so no restart needed here.
            TemplateFile(
                src="grafana/node-exporter-full.json",
                dest="grafana/provisioning/dashboards/json/node-exporter-full.json",
            ),
        ],
    ),
]
