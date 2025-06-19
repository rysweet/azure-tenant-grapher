import json
import logging
import os

from .asb_mapper import map_controls
from .dfd_builder import DFDBuilderStrategy
from .threat_enumerator import enumerate_threats
from .tmt_runner import run_tmt


class ThreatModelAgent:
    """
    Main ThreatModelAgent class for orchestrating the threat modeling workflow.
    """

    def __init__(self, spec_path: str, summaries_path: str):
        self.spec_path = spec_path
        self.summaries_path = summaries_path
        self.tenant_spec = None
        self.llm_summaries = None
        self.logger = logging.getLogger("ThreatModelAgent")

    async def run(self):
        print("=== Threat Modeling Agent: Starting workflow ===")
        await self._log_stage("Loading data")
        report_path = None
        try:
            self._load_data()
        except Exception as e:
            self.logger.error(f"Failed to load data: {e}")
            print(f"❌ Error: Failed to load data: {e}")
            print("Aborting workflow.")
            return None

        # DFD building stage
        await self._log_stage("Building DFD (Data Flow Diagram)")
        if self.tenant_spec is None or self.llm_summaries is None:
            self.logger.error("Cannot build DFD: tenant_spec or llm_summaries is None.")
            print(
                "❌ Error: Cannot build DFD because tenant_spec or llm_summaries is missing."
            )
        else:
            try:
                _, _, dfd_artifact = DFDBuilderStrategy.run(
                    self.tenant_spec, self.llm_summaries
                )
                if dfd_artifact:
                    self.logger.info("DFD artifact successfully built.")
                    print("✅ DFD artifact (Mermaid diagram):")
                    print(dfd_artifact)

                    # TMT invocation stage (stub)
                    await self._log_stage(
                        "Invoking Microsoft Threat Modeling Tool (TMT)"
                    )
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
                        await self._log_stage("Enumerating threats")
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
                            await self._log_stage("Mapping threats to ASB controls")
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
                                    print(
                                        "⚠️  ASB mapping returned no enriched threats."
                                    )
                            except Exception as e:
                                self.logger.error(f"ASB mapping failed: {e}")
                                print(f"❌ Error: ASB mapping failed: {e}")

                            # Report generation stage
                            if enriched_threats:
                                await self._log_stage("Generating Markdown report")
                                try:
                                    from .report_builder import build_markdown

                                    report_path = build_markdown(
                                        dfd_artifact=dfd_artifact,
                                        enriched_threats=enriched_threats,
                                        spec_path=self.spec_path,
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

        # Threat enumeration and ASB mapping not implemented per instructions

        print("=== Threat Modeling Agent: Workflow complete ===")
        return report_path

    def _load_data(self):
        # Load tenant specification (Markdown or JSON)
        if not os.path.exists(self.spec_path):
            raise FileNotFoundError(
                f"Tenant specification file not found: {self.spec_path}"
            )
        if self.spec_path.lower().endswith(".json"):
            try:
                with open(self.spec_path, encoding="utf-8") as f:
                    self.tenant_spec = json.load(f)
            except Exception as e:
                raise ValueError(
                    f"Failed to parse tenant specification JSON: {e}"
                ) from e
        elif self.spec_path.lower().endswith(".md"):
            try:
                with open(self.spec_path, encoding="utf-8") as f:
                    self.tenant_spec = f.read()
            except Exception as e:
                raise ValueError(
                    f"Failed to read tenant specification Markdown: {e}"
                ) from e
        else:
            raise ValueError("Tenant specification file must be .json or .md")

        # Load LLM summaries (JSON)
        if not os.path.exists(self.summaries_path):
            raise FileNotFoundError(
                f"LLM summaries file not found: {self.summaries_path}"
            )
        if not self.summaries_path.lower().endswith(".json"):
            raise ValueError("LLM summaries file must be a .json file")
        try:
            with open(self.summaries_path, encoding="utf-8") as f:
                self.llm_summaries = json.load(f)
        except Exception as e:
            raise ValueError(f"Failed to parse LLM summaries JSON: {e}") from e

    async def _log_stage(self, stage: str):
        print(f"[Stage] {stage}...")
