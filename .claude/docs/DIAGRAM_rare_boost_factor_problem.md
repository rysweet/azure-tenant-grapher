# Visual Diagrams: rare_boost_factor Problem

## 1. Complete Data Flow with Problem Annotations

```mermaid
flowchart TD
    Start[Source Tenant: 91 types, 114 instances] --> Layer1[Layer 1: Pattern Distribution Analysis]

    Layer1 --> Dist[Distribution Scores:<br/>VM: 37.8%, Web: 24.1%, Container: 15.2%]

    Dist --> Layer2[Layer 2: Proportional Allocation]

    Layer2 --> Alloc{Pattern Allocations<br/>Total: 20 instances}

    Alloc --> VM[VM Workload: 8]
    Alloc --> Web[Web Application: 5]
    Alloc --> Container[Container Platform: 3]
    Alloc --> Data[Data Platform: 2]
    Alloc --> Other[Other Patterns: 2]

    VM --> VMSelect[Per-Pattern Selection<br/>Coverage Sampling + Upweight]
    Web --> WebSelect[Per-Pattern Selection<br/>Coverage Sampling + Upweight]
    Container --> ContainerSelect[Per-Pattern Selection<br/>Coverage Sampling + Upweight]
    Data --> DataSelect[Per-Pattern Selection<br/>Coverage Sampling + Upweight]
    Other --> OtherSelect[Per-Pattern Selection<br/>Coverage Sampling + Upweight]

    VMSelect --> Merge[Merge All Selections:<br/>18 instances total]
    WebSelect --> Merge
    ContainerSelect --> Merge
    DataSelect --> Merge
    OtherSelect --> Merge

    Merge --> Check{Missing Types?}

    Check -->|Yes: 7 types| Supp[Cross-Pattern Supplemental<br/>Budget: 10% = 2 instances]
    Check -->|No| Final

    Supp --> Final[Final Selection:<br/>20 instances, 84/91 types]

    %% Problem annotations
    Problem1[PROBLEM 1:<br/>Allocation blind to<br/>rare type distribution]:::problem
    Problem2[PROBLEM 2:<br/>Upweighting trapped<br/>within pattern boundaries]:::problem
    Problem3[PROBLEM 3:<br/>Insufficient budget<br/>for 7 missing types]:::problem

    Problem1 -.->|No awareness| Alloc
    Problem2 -.->|Can't see across| Data
    Problem3 -.->|Only 2 instances| Supp

    %% Rare type flow annotation
    RareType[Rare Type: KeyVault<br/>3 instances total]:::raretype
    RareType -.->|2 in Data Platform| Data
    RareType -.->|1 in Web App| Web
    RareType -.->|0 in VM| VM

    Note[If Data Platform allocation = 2<br/>and neither selected instance has KeyVault<br/>→ Type LOST]:::note
    Note -.-> DataSelect

    classDef problem fill:#dc3545,stroke:#721c24,color:#fff
    classDef raretype fill:#ffc107,stroke:#856404,color:#000
    classDef note fill:#17a2b8,stroke:#117a8b,color:#fff

    style Layer1 fill:#e1f5ff
    style Layer2 fill:#fff3cd
    style Merge fill:#f8d7da
    style Supp fill:#d4edda
    style Final fill:#f8d7da
```

## 2. Pattern Isolation Problem - Concrete Example

```mermaid
graph TD
    subgraph Source["Source Tenant (91 types)"]
        KV[KeyVault: 3 instances<br/>Data: 2, Web: 1, VM: 0]
        EH[Event Hub: 1 instance<br/>Data: 1, Web: 0, VM: 0]
        Redis[Redis: 5 instances<br/>Data: 3, Web: 2, VM: 0]
    end

    subgraph Allocation["Proportional Allocation (20 total)"]
        VMAlloc[VM Workload: 8 instances]
        WebAlloc[Web Application: 5 instances]
        DataAlloc[Data Platform: 2 instances]
    end

    subgraph Selection["Per-Pattern Selection"]
        VMSel[VM Selection:<br/>8 instances<br/>0 KeyVault possible]
        WebSel[Web Selection:<br/>5 instances<br/>1 KeyVault possible]
        DataSel[Data Selection:<br/>2 instances<br/>2 KeyVault possible<br/>1 Event Hub possible]
    end

    KV -->|2 instances| DataAlloc
    KV -->|1 instance| WebAlloc
    KV -->|0 instances| VMAlloc

    EH -->|1 instance| DataAlloc

    VMAlloc --> VMSel
    WebAlloc --> WebSel
    DataAlloc --> DataSel

    DataSel --> Risk{Risk: Small Allocation}

    Risk -->|Only 2 shots| Scenario1[Scenario A:<br/>Both have KeyVault<br/>✅ Type covered]
    Risk -->|Only 2 shots| Scenario2[Scenario B:<br/>Neither has KeyVault<br/>❌ Type LOST]
    Risk -->|Only 2 shots| Scenario3[Scenario C:<br/>One has KeyVault<br/>One has Event Hub<br/>✅ Both covered]

    style Risk fill:#dc3545,stroke:#721c24,color:#fff
    style Scenario2 fill:#dc3545,stroke:#721c24,color:#fff
    style Scenario1 fill:#28a745,stroke:#155724,color:#fff
    style Scenario3 fill:#28a745,stroke:#155724,color:#fff
    style DataSel fill:#ffc107,stroke:#856404,color:#000
```

## 3. Upweighting Behavior: Baseline vs Aggressive

```mermaid
flowchart LR
    subgraph Baseline["Baseline (rare_boost_factor=1.0)"]
        B_Inst[Data Platform: 12 instances available]
        B_Inst --> B_Score1[Instance 1:<br/>KeyVault + Storage<br/>Score: 2.0]
        B_Inst --> B_Score2[Instance 2:<br/>Redis + Cosmos + Event Hub<br/>Score: 4.0]
        B_Inst --> B_Score3[Instance 3:<br/>SQL + KeyVault<br/>Score: 2.5]

        B_Score2 --> B_Select1[Selected 1st: Instance 2]
        B_Score3 --> B_Select2[Selected 2nd: Instance 3]

        B_Select1 --> B_Result[Result:<br/>Redis ✅<br/>Cosmos ✅<br/>Event Hub ✅<br/>KeyVault ✅<br/>4/4 types]
        B_Select2 --> B_Result
    end

    subgraph Aggressive["Aggressive (rare_boost_factor=5.0)"]
        A_Inst[Data Platform: 12 instances available]
        A_Inst --> A_Score1[Instance 1:<br/>KeyVault + Storage<br/>Boost: 30x<br/>Score: 10.0]
        A_Inst --> A_Score2[Instance 2:<br/>Redis + Cosmos + Event Hub<br/>Boost: 15x each<br/>Score: 20.0]
        A_Inst --> A_Score3[Instance 3:<br/>SQL + KeyVault<br/>Boost: 30x<br/>Score: 12.0]

        A_Score2 --> A_Select1[Selected 1st: Instance 2<br/>DOMINATES]
        A_Score1 --> A_Select2[Selected 2nd: Instance 1]

        A_Select1 --> A_Result[Result:<br/>Redis ✅<br/>Cosmos ✅<br/>Event Hub ✅<br/>KeyVault ❌<br/>3/4 types]
        A_Select2 --> A_Result
    end

    style B_Result fill:#28a745,stroke:#155724,color:#fff
    style A_Result fill:#dc3545,stroke:#721c24,color:#fff
    style A_Score2 fill:#ffc107,stroke:#856404,color:#000
```

## 4. Depth vs Breadth Trade-off

```mermaid
graph TD
    subgraph Problem["Selection Constraint: 2 instances from Data Platform"]
        Constraint[Budget: 2 instances<br/>Rare types: 4 types<br/>Cannot cover all]
    end

    subgraph LowBoost["Low Boost (factor=1.0)"]
        LB_Strategy[Strategy: Maximize BREADTH<br/>Select instances with DIVERSE types]
        LB_Strategy --> LB_I1[Instance A:<br/>KeyVault + Storage<br/>Score: 2.0]
        LB_Strategy --> LB_I2[Instance B:<br/>Redis + Cosmos<br/>Score: 2.5]
        LB_I1 --> LB_Result[Coverage: 4 types<br/>Depth: 1x each]
        LB_I2 --> LB_Result
    end

    subgraph HighBoost["High Boost (factor=5.0)"]
        HB_Strategy[Strategy: Maximize DEPTH<br/>Select instances with HIGHEST-BOOSTED types]
        HB_Strategy --> HB_I1[Instance C:<br/>KeyVault + Event Hub<br/>Boost: 30x each<br/>Score: 25.0]
        HB_Strategy --> HB_I2[Instance D:<br/>KeyVault + KeyVault refs<br/>Boost: 30x<br/>Score: 20.0]
        HB_I1 --> HB_Result[Coverage: 2 types<br/>Depth: 2-3x each]
        HB_I2 --> HB_Result
    end

    Constraint --> LowBoost
    Constraint --> HighBoost

    Compare[Comparison:<br/>Low boost: 4 types, shallow coverage<br/>High boost: 2 types, deep coverage]

    LB_Result --> Compare
    HB_Result --> Compare

    Compare --> Insight[INSIGHT: High boost sacrifices BREADTH for DEPTH<br/>With limited budget, this REDUCES total coverage]

    style Constraint fill:#ffc107,stroke:#856404,color:#000
    style LB_Result fill:#28a745,stroke:#155724,color:#fff
    style HB_Result fill:#dc3545,stroke:#721c24,color:#fff
    style Insight fill:#17a2b8,stroke:#117a8b,color:#fff
```

## 5. Solution Comparison

```mermaid
flowchart TB
    Start[Problem: rare_boost_factor reduces coverage]

    Start --> Current[Current Architecture:<br/>Allocation → Selection → Supplemental]

    Current --> Sol1[Solution 1:<br/>Coverage-Aware Allocation]
    Current --> Sol2[Solution 2:<br/>Increase Supplemental Budget]
    Current --> Sol3[Solution 3:<br/>Two-Phase Selection]
    Current --> Sol4[Solution 4:<br/>Expose Budget Parameter]

    Sol1 --> Sol1_Detail[Modify Layer 2 allocation<br/>based on rare type distribution<br/>✅ Fixes root cause<br/>⚠️ Medium complexity]

    Sol2 --> Sol2_Detail[Increase cross-pattern budget<br/>from 10% to 20-30%<br/>✅ Simple fix<br/>⚠️ Doesn't fix root cause]

    Sol3 --> Sol3_Detail[Phase 1: Global rare type selection<br/>Phase 2: Proportional selection<br/>✅ Comprehensive<br/>⚠️ High complexity]

    Sol4 --> Sol4_Detail[Make supplemental budget configurable<br/>✅ Minimal effort<br/>⚠️ User must tune parameter]

    Sol1_Detail --> Rec[RECOMMENDED:<br/>Implement Sol4 immediately (30 min)<br/>Implement Sol1 medium-term (1 week)]
    Sol2_Detail --> Rec
    Sol3_Detail --> Rec
    Sol4_Detail --> Rec

    style Start fill:#dc3545,stroke:#721c24,color:#fff
    style Current fill:#ffc107,stroke:#856404,color:#000
    style Rec fill:#28a745,stroke:#155724,color:#fff
```

## 6. Root Cause Summary (Single Diagram)

```mermaid
flowchart TD
    RootCause[ROOT CAUSE:<br/>Pattern Isolation]

    RootCause --> Symptom1[Symptom 1:<br/>Allocation blind to rare types]
    RootCause --> Symptom2[Symptom 2:<br/>Upweighting trapped within patterns]
    RootCause --> Symptom3[Symptom 3:<br/>Insufficient supplemental budget]

    Symptom1 --> Effect1[Effect: Small patterns<br/>bottleneck rare types]
    Symptom2 --> Effect2[Effect: Can't prioritize<br/>across pattern boundaries]
    Symptom3 --> Effect3[Effect: 10% budget insufficient<br/>for 7.6% missing types]

    Effect1 --> Result[RESULT:<br/>Higher boost → LOWER coverage<br/>Baseline: 85/91 (93.4%)<br/>Boost 5.0: 84/91 (92.3%)]
    Effect2 --> Result
    Effect3 --> Result

    Result --> Mechanism[MECHANISM:<br/>High boost creates depth vs breadth trade-off<br/>Focuses on FEW highly-boosted types<br/>Neglects MANY moderately-rare types]

    style RootCause fill:#dc3545,stroke:#721c24,color:#fff
    style Result fill:#dc3545,stroke:#721c24,color:#fff
    style Mechanism fill:#ffc107,stroke:#856404,color:#000
```

## Usage Notes

**Diagram 1**: Complete data flow showing where problems occur
**Diagram 2**: Concrete example of pattern isolation risk
**Diagram 3**: Behavioral difference between baseline and aggressive upweighting
**Diagram 4**: Depth vs breadth trade-off explanation
**Diagram 5**: Solution comparison with recommendations
**Diagram 6**: Root cause summary (single-page reference)

These diagrams support the analysis in `ANALYSIS_rare_boost_factor_counterintuitive_behavior.md`.
