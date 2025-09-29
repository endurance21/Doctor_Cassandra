from __future__ import annotations
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

class ClusterInventory(ABC):
    @abstractmethod
    def list_customers(self) -> List[str]: ...
    @abstractmethod
    def list_clusters(self, customer: Optional[str] = None) -> List[Dict[str, Any]]: ...
    @abstractmethod
    def topology(self, customer: str, cluster: str) -> Dict[str, Any]: ...

class MetricsProvider(ABC):
    @abstractmethod
    def query(self, customer: str, cluster: str, metric: str, window: str = "15m") -> Dict[str, Any]: ...
    @abstractmethod
    def node_health(self, customer: str, cluster: str, node: str) -> Dict[str, Any]: ...

class LogsProvider(ABC):
    @abstractmethod
    def fetch(self, customer: str, cluster: str, node: Optional[str], pattern: Optional[str],
              since: str = "15m", limit: int = 200) -> Dict[str, Any]: ...

class NodeController(ABC):
    @abstractmethod
    def restart_node(self, customer: str, cluster: str, node: str) -> Dict[str, Any]: ...
    @abstractmethod
    def advise_capacity(self, customer: str, cluster: str) -> Dict[str, Any]: ...
