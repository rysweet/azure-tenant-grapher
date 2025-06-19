# Threat Modeling for Azure Cloud Environments & Applications

A practical, end-to-end tutorial with examples, diagrams, and a CWE-linked glossary.

---

## 1. Why Threat Model in the Cloud?

Threat modeling is a structured way to anticipate “what can go wrong” in an architecture so that security controls are designed in—not bolted on. Microsoft embeds threat modeling in the Security Development Lifecycle (SDL) and requires every service team to review and mitigate unacceptable risks before release. For cloud workloads, the technique is even more valuable because the attack surface is fluid: services are loosely coupled, identities span tenants, and infrastructure is defined in code.

**References:**
- [Microsoft SDL Threat Modeling](https://learn.microsoft.com/en-us/security/engineering/threat-modeling)
- [Azure Security Documentation](https://learn.microsoft.com/en-us/azure/security/)

---

## 2. Prerequisites & Tooling

| Item | Purpose |
|------|---------|
| [Microsoft Threat Modeling Tool (TMT)](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool) | Free Windows desktop tool for creating Data-Flow Diagrams (DFDs) and automatically generating STRIDE-based threat lists. |
| [Azure Reference Architectures](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/) | Microsoft-published diagrams as starting points; each shows trust boundaries and recommended controls. |
| [Azure Security Benchmark (ASB) v4](https://learn.microsoft.com/en-us/azure/security/benchmarks/introduction) | Baseline of cloud controls; DevOps security control DS-1 explicitly mandates threat modeling. |
| [OWASP Threat Modeling Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html) | Cloud-agnostic guidance that complements SDL/STRIDE. |

**Tip:** Install the [TMT Azure Template](https://github.com/microsoft/ThreatModelingTemplates) so the stencil already contains services such as Key Vault, App Service, and Event Hub.

---

## 3. Step-by-Step Workflow

### 3.1 Define Objectives & Scope

Drivers: compliance (e.g., PCI DSS), risk appetite, DEV → TEST → PROD promotion gates. Record assumptions (e.g., “traffic is TLS-only”)—they become test criteria later.

### 3.2 Create an Architecture & Data-Flow Diagram

Use the symbols in TMT or the mermaid snippet below. Mark trust boundaries wherever control shifts (internet edge, VNet, subnets, managed identity token issuance).

```mermaid
flowchart TD
  Internet((User))
  AGW[Azure Application Gateway (WAF)]
  App[App Service API]
  SQL[(Azure SQL DB)]
  KV[Key Vault]
  Storage[(Blob Storage)]
  Internet -->|HTTPS 443| AGW
  AGW -->|TLS 443| App
  App -->|AAD token| KV
  App -->|TCP 1433 | SQL
  App -->|HTTPS 443| Storage
  classDef boundary stroke-dasharray: 5 5
  class AGW,App,SQL,KV,Storage boundary
```

Paste the code into the [Mermaid Live Editor](https://mermaid.live/) to render the diagram.

### 3.3 Decompose & Label Elements

Identify external interactors (User, AAD), processes (App Service), data stores (SQL, Storage), and data flows. The more precise the decomposition, the higher the quality of generated threats.

### 3.4 Enumerate Threats with STRIDE

| STRIDE Category | Example in Diagram | Native Azure Mitigations |
|-----------------|-------------------|--------------------------|
| Spoofing | Fake JWT presented to App | AAD issuer & audience validation, Managed Identities |
| Tampering | SQL query altered in transit | TLS 1.2+, Private Link |
| Repudiation | User denies deleting blob | Storage diagnostic & Azure Monitor logs |
| Information Disclosure | Blob container made public | Defender for Cloud “Public Blob” alert |
| Denial of Service | Bot flood at AGW | WAF rate limiting, Azure Front Door |
| Elevation of Privilege | App’s Managed Identity gets ‘Contributor’ at subscription scope | RBAC least-privilege reviews, PIM |

**See:** [STRIDE Threat Model Background](https://learn.microsoft.com/en-us/security/engineering/threat-modeling#stride)

### 3.5 Map Threats to Controls & Gaps

Leverage [ASB v4](https://learn.microsoft.com/en-us/azure/security/benchmarks/introduction) and the [Cloud Adoption Framework Secure methodology](https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/secure/) to select controls and discover gaps. Track them in backlog items tied to pipelines.

### 3.6 Prioritize (Risk Rating)

Common schemes include DREAD or CVSS. For small teams, a simple matrix (High-Medium-Low impact × likelihood) is sufficient.

### 3.7 Validate & Iterate

Update the model when architecture or threat landscape changes (for example, when adding Event Hub). DS-1 requires revalidation at each “major security-impact change”.

---

## 4. Worked Example: Serverless Image-Processing API

| Stage | Action | Notes |
|-------|--------|-------|
| Diagram | Functions → Storage → Computer Vision API | Event-Driven architecture |
| Threats | Tampering of callback URL; DoS via large files; Info disclosure by over-permissive SAS tokens | STRIDE + tool auto-gen |
| Controls | - Signed inbound requests with AAD app ID<br> - Function-level concurrency limit<br> - Short-lived, IP-scoped SAS | All enforceable in ARM/Bicep/TF |

This “shift-left” model is then version-controlled alongside IaC so that PRs failing security tests (e.g., open ingress) block merges.

---

## 5. Operationalizing in CI/CD

1. **Automated model linting:** Use tools or scripts to compare TMT files against diagrams in the repository.
2. **Pipeline gates:** Require STRIDE checklist completion before release.
3. **Defender for Cloud:** Correlate runtime alerts to modeled threats to validate mitigations.
4. **Review cadence:** Quarterly threat-model workshop (include architects & DevOps) plus ad-hoc on material changes.

---

## 6. Glossary of Common Weaknesses

| CWE ID | Weakness | Cloud-Relevant Scenario |
|--------|----------|------------------------|
| CWE-287 | Improper Authentication | B2C sign-in bypass via mis-scoped policy |
| CWE-284 | Improper Access Control | “Contributor” role granted on entire RG |
| CWE-522 | Insufficiently Protected Credentials | Secrets in appsettings.json pushed to Git |
| CWE-798 | Hard-coded Secrets | Storage key in container image |
| CWE-79 | Cross-Site Scripting (XSS) | React front-end served from App Service |
| CWE-400 | Uncontrolled Resource Consumption (DoS) | Queue trigger with no poison-message handling |
| CWE-601 | Open Redirect | Misconfigured function route used in phishing |
| CWE-200 | Exposure of Sensitive Information | Stack trace returned by API on error |

For an up-to-date list, see [CWE Top 25 Most Dangerous Software Weaknesses](https://cwe.mitre.org/top25/archive/2024/2024_cwe_top25.html).

---

## 7. Further Learning Paths

- [Microsoft Learn: Introduction to Threat Modeling](https://learn.microsoft.com/en-us/training/modules/intro-threat-modeling/)
- [Microsoft Security Briefs: SDL Threat Modeling Techniques](https://learn.microsoft.com/en-us/security/engineering/threat-modeling)
- [OWASP Attack Surface & ASVS Cheat Sheets](https://cheatsheetseries.owasp.org/cheatsheets/Attack_Surface_Analysis_Cheat_Sheet.html), [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
- [Azure Security Benchmark Workbook](https://learn.microsoft.com/en-us/azure/security/benchmarks/security-benchmark-workbook) – Pull DS-1 recommendations into Azure Workbook dashboards for continuous tracking

---

## Key Takeaways

1. Start with an accurate diagram—automation only helps if the model reflects reality.
2. Use STRIDE + ASB controls to think like an attacker and answer “what can go wrong” on Azure.
3. Bake the model into CI/CD so deviations raise pull-request feedback, keeping documentation and code in lock-step.

Apply this cycle iteratively and your cloud architecture will evolve with security considerations at every step—not just the penetration-test crunch time at the end of a release.
