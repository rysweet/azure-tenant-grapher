"""Cost management service package.

This package provides modular components for Azure cost tracking and analysis.
Each module handles a specific responsibility:
- data_fetch: Azure Cost API integration
- storage: Neo4j persistence
- query: Cost data retrieval
- forecasting: Linear regression predictions
- anomaly_detection: Z-score analysis
- reporting: Markdown/JSON reports
"""

from .anomaly_detection import AnomalyDetector
from .data_fetch import CostDataFetcher
from .forecasting import CostForecaster
from .query import CostQueryService
from .reporting import CostReporter
from .storage import CostStorageService

__all__ = [
    "AnomalyDetector",
    "CostDataFetcher",
    "CostForecaster",
    "CostQueryService",
    "CostReporter",
    "CostStorageService",
]
