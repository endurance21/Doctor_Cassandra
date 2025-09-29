from __future__ import annotations
from typing import Optional, Dict, Any
from fastmcp import FastMCP
from fastmcp.resources import TextResource
import json

# swap these to real implementations later
from providers import MockInventory, MockMetrics, MockLogs, MockNodeCtl
PORT=8001
mcp = FastMCP("cass-doctor")

inventory = MockInventory()
metrics   = MockMetrics()
logs      = MockLogs()
ctl       = MockNodeCtl()

# ------------------ RESOURCES (dynamic + static) ------------------

@mcp.resource("cassandra://inventory/customers", mime_type="application/json")
def res_customers() -> Dict[str, Any]:
    return {"customers": inventory.list_customers()}

@mcp.resource("cassandra://inventory/{customer}/clusters", mime_type="application/json")
def res_clusters(customer: str) -> Dict[str, Any]:
    return {"customer": customer, "clusters": inventory.list_clusters(customer)}

@mcp.resource("cassandra://cluster/{customer}/{cluster}/topology", mime_type="application/json")
def res_topology(customer: str, cluster: str) -> Dict[str, Any]:
    return inventory.topology(customer, cluster)

# Example static runbook (swap for real docs later)
RUNBOOK_TWCS = """# TWCS Runbook (Mock)
- Check table options: compaction = 'TimeWindowCompactionStrategy'
- Ensure proper `compaction_window_unit` and `compaction_window_size`
- Verify TTL and tombstone purge grace settings
"""
mcp.add_resource(TextResource(
    uri="cassandra://runbooks/twcs.md",
    mime_type="text/markdown",
    text=RUNBOOK_TWCS
))

# ------------------ TOOLS ------------------

@mcp.tool
def list_clusters(customer: Optional[str] = None) -> Any:
    """
    List clusters across all customers, or for a specific customer.
    """
    return inventory.list_clusters(customer)

@mcp.tool
def cluster_overview(customer: str, cluster: str) -> Dict[str, Any]:
    """
    Return a compact overview: topology + a couple of synthetic KPIs.
    """
    topo = inventory.topology(customer, cluster)
    dc_counts = []
    total_nodes = 0
    for dc in topo.get("dcs", []):
        n = sum(len(r["nodes"]) for r in dc["racks"])
        total_nodes += n
        dc_counts.append({"dc": dc["name"], "nodes": n})
    kpis = {"replication_ok": True, "recent_alerts": 1, "approx_total_nodes": total_nodes}
    return {"topology": topo, "dc_counts": dc_counts, "kpis": kpis}

@mcp.tool
def node_health(customer: str, cluster: str, node: str) -> Dict[str, Any]:
    """
    Health snapshot for a node (status, load, p99, timeouts, disk%).
    """
    return metrics.node_health(customer, cluster, node)

@mcp.tool
def query_metrics(customer: str, cluster: str, metric: str, window: str = "15m") -> Dict[str, Any]:
    """
    Query a metric time series (mocked). metric examples: 'read_p99_ms', 'cpu_pct'.
    """
    return metrics.query(customer, cluster, metric, window)

@mcp.tool
def fetch_logs(customer: str, cluster: str, node: Optional[str] = None,
               pattern: Optional[str] = None, since: str = "15m", limit: int = 200) -> Dict[str, Any]:
    """
    Fetch recent logs matching pattern (mocked).
    """
    return logs.fetch(customer, cluster, node, pattern, since, limit)

@mcp.tool
def restart_node(customer: str, cluster: str, node: str) -> Dict[str, Any]:
    """
    Restart a node (MOCK — no side-effects).
    """
    return ctl.restart_node(customer, cluster, node)

@mcp.tool
def advise_capacity(customer: str, cluster: str) -> Dict[str, Any]:
    """
    Capacity advice (MOCK). Suggests new node count & rationale.
    """
    return ctl.advise_capacity(customer, cluster)

if __name__ == "__main__":
    mcp.run()  # stdio transport; works with Inspector or programmatic clients
