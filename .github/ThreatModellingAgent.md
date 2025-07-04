OK, I want to start a new feature, create an issue, branch, and corresponding PR - the feature is threat modeling. First, I want you to do a comprehensive review of @/docs/resources/CloudThreatModelling.md for accuracy, clarity, and factualness. Make any necessary updates. Then, we are going to create an AI agent whose job it is to review the tenant specification and llm summaries generated by the ```azure-tenant-grapher generate-spec``` command, and then create a threat model for the tenant. The agent will use the Microsoft Threat Modeling Tool (TMT) to generate a Data-Flow Diagram (DFD) and STRIDE-based threat list. The agent will also use the Azure Security Benchmark (ASB) v3 as a baseline for cloud controls. The agent will be able to generate a report in Markdown format that includes the DFD, threat list, and any identified risks or vulnerabilities.


The Threat Modeling Agent will be implemented as a Python script that integrates with the Microsoft Threat Modeling Tool (TMT) and Azure Security Benchmark (ASB) v3. The agent will:

[]: # 1. **Review Tenant Specification**: Analyze the tenant specification generated by `azure-tenant-grapher generate-spec`.
[]: # 2. **Generate DFD**: Create a Data-Flow Diagram using TMT.
[]: # 3. **Enumerate Threats**: Use STRIDE to identify threats based on the DFD.
[]: # 4. **Generate Report**: Compile findings into a Markdown report, including the DFD, threat list, and identified risks.

The agent will be implemented as a new command line command `generate-threat-model` in the `azure-tenant-grapher` CLI. The command will invoke the generate-spec command to ensure the tenant specification is up-to-date before proceeding with threat modeling using the specification. If a full "build" is required, the command will also handle that prior to the generate-spec command.

The agent will be an autogen agent (see @https://github.com/microsoft/autogen and @https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/index.html).

The agent should use the mcp server feature of the azure-tenant-grapher to help it understand and query the graph.
