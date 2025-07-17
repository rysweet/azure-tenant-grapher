import logging
from typing import Any, Dict, List

from src.config_manager import create_neo4j_config_from_env
from src.utils.session_manager import create_session_manager

from .asb_mapper import map_controls
from .dfd_builder import DFDBuilderStrategy
from .threat_enumerator import enumerate_threats
from .tmt_runner import run_tmt


class ThreatModelAgent:
    """
    Main ThreatModelAgent class for orchestrating the threat modeling workflow.
    Now loads DFD nodes, edges, and LLM summaries directly from Neo4j.
    """

    def __init__(self):
        from src.utils.neo4j_startup import ensure_neo4j_running

        self.logger = logging.getLogger("ThreatModelAgent")
        ensure_neo4j_running()
        self.neo4j_config = create_neo4j_config_from_env().neo4j
        self.session_manager = create_session_manager(self.neo4j_config)
        self.session_manager.connect()

    def _load_dfd_graph_from_neo4j(self) -> Dict[str, Any]:
        """
        Query Neo4j for DFD nodes and edges, including LLM summaries as properties.
        Returns a dict with 'nodes' and 'edges'.
        """
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        with self.session_manager.session() as session:
            # Query for nodes with LLM summaries
            node_query = """
            MATCH (n)
            WHERE n.id IS NOT NULL
            OPTIONAL MATCH (n)-[:HAS_SUMMARY]->(s)
            RETURN n.id AS id, COALESCE(n.label, n.id, '') AS label, n.type AS type, s.summary AS summary
            """
            for record in session.run(node_query):
                nodes.append(
                    {
                        "id": record["id"],
                        "label": record["label"],
                        "type": record["type"],
                        "summary": record["summary"],
                    }
                )
            # Query for edges
            edge_query = """
            MATCH (src)-[r]->(dst)
            WHERE COALESCE(src.id, src.name, '') <> '' AND COALESCE(dst.id, dst.name, '') <> ''
            RETURN COALESCE(src.id, src.name, '') AS source, COALESCE(dst.id, dst.name, '') AS target, r.label AS label
            """
            for record in session.run(edge_query):
                edges.append(
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "label": record["label"] or "",
                    }
                )
        return {"nodes": nodes, "edges": edges}

    async def run(self):
        print("=== Threat Modeling Agent: Starting workflow ===")
        report_path = None
        try:
            dfd_graph = self._load_dfd_graph_from_neo4j()
        except Exception as e:
            self.logger.error(f"Failed to load DFD graph from Neo4j: {e}")
            print(f"❌ Error: Failed to load DFD graph from Neo4j: {e}")
            print("Aborting workflow.")
            return None

        print("[Stage] Building DFD (Data Flow Diagram)...")
        try:
            _, _, dfd_artifact = DFDBuilderStrategy.run(dfd_graph, dfd_graph)
            if dfd_artifact:
                self.logger.info("DFD artifact (Mermaid diagram) successfully built.")
                print("✅ DFD artifact (Mermaid diagram):")
                print(dfd_artifact)

                # TMT invocation stage (stub)
                print("[Stage] Invoking Microsoft Threat Modeling Tool (TMT)...")
                tmt_results = None
                try:
                    tmt_results = run_tmt(dfd_artifact, logger=self.logger)
                    if tmt_results:
                        self.logger.info(
                            f"TMT runner returned {len(tmt_results)} threats (stub)."
                        )
                        print("✅ TMT runner output (stubbed threats):")
                        for threat in tmt_results:
                            print(
                                f"- [{threat['severity']}] {threat['title']}: {threat['description']}"
                            )
                    else:
                        self.logger.warning("TMT runner returned no threats.")
                        print("⚠️  TMT runner returned no threats.")
                except Exception as e:
                    self.logger.error(f"TMT runner failed: {e}")
                    print(f"❌ Error: TMT runner failed: {e}")

                # Threat enumeration stage
                if tmt_results:
                    print("[Stage] Enumerating threats...")
                    enumerated_threats = None
                    try:
                        enumerated_threats = enumerate_threats(
                            tmt_results, logger=self.logger
                        )
                        if enumerated_threats:
                            self.logger.info(
                                f"Threat enumeration produced {len(enumerated_threats)} threats (stub)."
                            )
                            print("✅ Threat enumeration output (stub):")
                            for threat in enumerated_threats:
                                print(
                                    f"- [{threat['severity']}] {threat['title']}: {threat['description']}"
                                )
                        else:
                            self.logger.warning(
                                "Threat enumeration returned no threats."
                            )
                            print("⚠️  Threat enumeration returned no threats.")
                    except Exception as e:
                        self.logger.error(f"Threat enumeration failed: {e}")
                        print(f"❌ Error: Threat enumeration failed: {e}")

                    # ASB mapping stage
                    enriched_threats = None
                    if enumerated_threats:
                        print("[Stage] Mapping threats to ASB controls...")
                        try:
                            enriched_threats = map_controls(
                                enumerated_threats, logger=self.logger
                            )
                            if enriched_threats:
                                self.logger.info(
                                    f"ASB mapping produced {len(enriched_threats)} enriched threats (stub)."
                                )
                                print("✅ ASB mapping output (stub):")
                                for threat in enriched_threats:
                                    print(
                                        f"- [{threat['severity']}] {threat['title']}: {threat['description']}"
                                    )
                                    print(
                                        f"  ASB Controls: {threat.get('asb_controls', [])}"
                                    )
                            else:
                                self.logger.warning(
                                    "ASB mapping returned no enriched threats."
                                )
                                print("⚠️  ASB mapping returned no enriched threats.")
                        except Exception as e:
                            self.logger.error(f"ASB mapping failed: {e}")
                            print(f"❌ Error: ASB mapping failed: {e}")

                        # Report generation stage
                        if enriched_threats:
                            print("[Stage] Generating Markdown report...")
                            try:
                                from .report_builder import build_markdown

                                report_path = build_markdown(
                                    dfd_artifact=dfd_artifact,
                                    enriched_threats=enriched_threats,
                                    spec_path="(from Neo4j)",
                                    logger=self.logger,
                                )
                                if report_path:
                                    self.logger.info(
                                        f"Report generated at: {report_path}"
                                    )
                                    print(
                                        f"✅ Threat modeling report generated: {report_path}"
                                    )
                                else:
                                    self.logger.error("Report generation failed.")
                                    print("❌ Error: Report generation failed.")
                            except Exception as e:
                                self.logger.error(f"Report generation failed: {e}")
                                print(f"❌ Error: Report generation failed: {e}")

            else:
                self.logger.error("DFD artifact could not be built.")
                print("❌ Error: DFD artifact could not be built.")
        except Exception as e:
            self.logger.error(f"DFD building failed: {e}")
            print(f"❌ Error: DFD building failed: {e}")

        print("=== Threat Modeling Agent: Workflow complete ===")
        return report_path
