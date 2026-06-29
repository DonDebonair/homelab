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
            TemplateFile(src="prometheus-config.yml", dest="prometheus/config/prometheus.yml"),
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
            # Plugins/renders only -- dashboards/users/datasources live in the
            # migrated Postgres DB, so this volume is low-recovery-cost.
            NamedVolume(name="grafana-data", mount_path="/var/lib/grafana"),
        ],
    ),
]
