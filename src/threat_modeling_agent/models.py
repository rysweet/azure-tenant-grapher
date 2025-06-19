"""Pydantic data models for the Threat Modeling Agent."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ASBControl(BaseModel):
    """
    Represents an Azure Security Benchmark (ASB) control.

    Attributes:
        control_id (str): The unique identifier for the ASB control.
        title (str): The title of the ASB control.
        description (str): A detailed description of the ASB control.
    """

    control_id: str
    """The unique identifier for the ASB control."""

    title: str
    """The title of the ASB control."""

    description: str
    """A detailed description of the ASB control."""


class Threat(BaseModel):
    """
    Represents a threat identified in the threat modeling process.

    Attributes:
        id (str): The unique identifier for the threat.
        title (str): The title of the threat.
        description (str): A detailed description of the threat.
        severity (str): The severity level of the threat.
        stride (str): The STRIDE category of the threat.
        category (str): The threat category.
        element (str): The DFD element associated with the threat.
        asb_controls (List[ASBControl]): List of related ASB controls.
        raw (Dict): The raw threat data as a dictionary.
    """

    id: str
    """The unique identifier for the threat."""

    title: str
    """The title of the threat."""

    description: str
    """A detailed description of the threat."""

    severity: str
    """The severity level of the threat."""

    stride: str
    """The STRIDE category of the threat."""

    category: str
    """The threat category."""

    element: str
    """The DFD element associated with the threat."""

    asb_controls: List[ASBControl]
    """List of related ASB controls."""

    raw: Dict[str, Any]
    """The raw threat data as a dictionary."""


class DFDNode(BaseModel):
    """
    Represents a node in a Data Flow Diagram (DFD).

    Attributes:
        id (str): The unique identifier for the node.
        label (str): The display label for the node.
        type (str): The type of the node (e.g., process, data store, external entity).
    """

    id: str
    """The unique identifier for the node."""

    label: str
    """The display label for the node."""

    type: str
    """The type of the node (e.g., process, data store, external entity)."""


class DFDEdge(BaseModel):
    """
    Represents an edge (data flow) in a Data Flow Diagram (DFD).

    Attributes:
        source (str): The source node identifier.
        target (str): The target node identifier.
        label (str): The label describing the data flow.
    """

    source: str
    """The source node identifier."""

    target: str
    """The target node identifier."""

    label: str
    """The label describing the data flow."""


class ThreatModelReport(BaseModel):
    """
    Represents a complete threat model report.

    Attributes:
        dfd (str): The DFD representation (e.g., as a string or serialized format).
        threats (List[Threat]): List of identified threats.
        spec_path (str): Path to the specification file used for modeling.
        generated (datetime): The datetime when the report was generated.
        summary (Optional[str]): An optional summary of the report.
    """

    dfd: str
    """The DFD representation (e.g., as a string or serialized format)."""

    threats: List[Threat]
    """List of identified threats."""

    spec_path: str
    """Path to the specification file used for modeling."""

    generated: datetime
    """The datetime when the report was generated."""

    summary: Optional[str] = None
    """An optional summary of the report."""
