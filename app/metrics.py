"""Prometheus metrics."""
from prometheus_client import Gauge  # type: ignore

DEPLOYMENT_STATUS = Gauge(
    "sonic_salt_minion_deployment_status",
    "Deployment of Salt status on SONiC devices: -1 = failed, 0 = waiting, 1 = updated",
    ["hostname", "salt_pex_build_version"],
)
