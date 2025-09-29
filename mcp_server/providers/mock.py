from __future__ import annotations
from typing import List, Dict, Any, Optional
from .base import ClusterInventory, MetricsProvider, LogsProvider, NodeController
import random, time

CUSTOMERS = ["Contoso", "Fabrikam"]
CLUSTERS = {
    "Contoso": [
        {"name":"nova-preprod", "version":"4.1.3", "dcs":["WEU","WUS"]},
        {"name":"nova-prod",    "version":"4.1.3", "dcs":["WEU","EUS2"]}
    ],
    "Fabrikam": [
        {"name":"fab-analytics","version":"3.11.16","dcs":["IND","WEU"]}
    ]
}
TOPO = {
    ("Contoso","nova-preprod"): {
        "cluster":"nova-preprod","version":"4.1.3",
        "dcs":[
            {"name":"WEU","racks":[{"name":"rack1","nodes":["10.0.0.10","10.0.0.11"]}]},
            {"name":"WUS","racks":[{"name":"rack1","nodes":["10.1.0.20","10.1.0.21"]}]}
        ]
    },
    ("Contoso","nova-prod"): {
        "cluster":"nova-prod","version":"4.1.3",
        "dcs":[{"name":"WEU","racks":[{"name":"rack1","nodes":["10.0.1.10","10.0.1.11","10.0.1.12"]}]}]
    },
    ("Fabrikam","fab-analytics"): {
        "cluster":"fab-analytics","version":"3.11.16",
        "dcs":[{"name":"IND","racks":[{"name":"rack1","nodes":["10.9.0.5","10.9.0.6"]}]}]
    }
}

class MockInventory(ClusterInventory):
    def list_customers(self) -> List[str]:
        return CUSTOMERS
    def list_clusters(self, customer: Optional[str] = None) -> List[Dict[str, Any]]:
        if customer:
            return CLUSTERS.get(customer, [])
        out: List[Dict[str,Any]] = []
        for c, arr in CLUSTERS.items():
            for item in arr:
                out.append({"customer":c, **item})
        return out
    def topology(self, customer: str, cluster: str) -> Dict[str, Any]:
        return TOPO.get((customer, cluster), {"error":"not found"})

class MockMetrics(MetricsProvider):
    def query(self, customer: str, cluster: str, metric: str, window: str = "15m") -> Dict[str, Any]:
        now = int(time.time())
        series = [{"t": now - i*60, "v": round(random.uniform(1,20),2)} for i in range(15)]
        return {"customer":customer,"cluster":cluster,"metric":metric,"window":window,"series":list(reversed(series))}
    def node_health(self, customer: str, cluster: str, node: str) -> Dict[str, Any]:
        return {
            "customer":customer,"cluster":cluster,"node":node,
            "status":"UN","load_gb": round(random.uniform(50, 300), 1),
            "pending_compactions": random.randint(0, 30),
            "latency_ms_p99": round(random.uniform(2, 40), 1),
            "read_timeout_rate": round(random.uniform(0, 0.5), 3),
            "disk_pct": random.randint(35, 85)
        }

class MockLogs(LogsProvider):
    def fetch(self, customer: str, cluster: str, node: Optional[str], pattern: Optional[str],
              since: str = "15m", limit: int = 200) -> Dict[str, Any]:
        lines = []
        for i in range(min(limit, 10)):
            lines.append(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} [{node or '10.0.0.10'}] INFO CompactionTask - Completed SSTable compaction.")
        if pattern:
            lines = [ln for ln in lines if pattern.lower() in ln.lower()]
        return {"customer":customer,"cluster":cluster,"node":node,"since":since,"count":len(lines),"lines":lines}

class MockNodeCtl(NodeController):
    def restart_node(self, customer: str, cluster: str, node: str) -> Dict[str, Any]:
        # mock side-effect
        print(f"MockNodeCtl.restart_node: {customer}, {cluster}, {node}")
        return {"customer":customer,"cluster":cluster,"node":node,"action":"restart","status":"SIMULATED_OK"}
    def advise_capacity(self, customer: str, cluster: str) -> Dict[str, Any]:
        # naive mock: if avg p99 > 25ms or disk > 80% → suggest +2 nodes
        topo = TOPO.get((customer, cluster))
        node_count = sum(len(r["nodes"]) for dc in topo["dcs"] for r in dc["racks"]) if topo else 3
        advice = {
            "current_nodes": node_count,
            "suggested_nodes": node_count + 2,
            "rationale": "High tail latency and/or disk > 80% in last 1h (mock)."
        }
        return {"customer":customer,"cluster":cluster,"advice":advice}
