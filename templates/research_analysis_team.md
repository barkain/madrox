# Research Analysis Team Template

## Overview

Deploy a research team that gathers information from multiple sources, analyzes findings, synthesizes insights, and produces comprehensive reports.

**Best for**: Market research, competitive intelligence, technology trend analysis, academic literature reviews

**Team Size**: 5 instances (1 supervisor + 4 workers)

**Estimated Duration**: 2-3 hours depending on research depth

---

## Team Structure

### Research Lead (Supervisor)
**Role**: `general` or `data_scientist`
**Enable Madrox**: ✅ Required (must spawn team members)

**Responsibilities**:
- Define research scope and objectives
- Spawn and manage research specialists
- Coordinate data collection and analysis phases
- Ensure data quality and citation accuracy
- Synthesize findings across specialists
- Deliver final research report

### Team Members (Workers)

All team members must be spawned with `parent_instance_id` set to the Research Lead's instance ID.

#### 1. Research Specialist
**Role**: `general`
**MCP Tools**: Brave Search, Playwright (browser automation)
**Focus**: Web research, data collection, source discovery
**Deliverables**:
- Curated list of relevant sources
- Extracted data from web sources
- Initial findings with citations
- Source credibility assessment

#### 2. Data Analyst
**Role**: `data_scientist`
**Focus**: Statistical analysis, pattern detection, quantitative insights
**Deliverables**:
- Statistical summaries of collected data
- Trend analysis and visualizations
- Quantitative insights and metrics
- Data quality validation report

#### 3. Report Synthesizer
**Role**: `general`
**Focus**: Cross-source analysis, insight extraction, pattern recognition
**Deliverables**:
- Synthesized findings across all sources
- Key insights and recommendations
- Gap analysis (missing information)
- Executive summary

#### 4. Technical Writer
**Role**: `technical_writer`
**Focus**: Professional report formatting, citation management
**Deliverables**:
- Formatted research report
- Properly cited sources (APA/MLA/Chicago)
- Visual presentation of findings
- Executive summary and appendices

---

## Workflow Phases

### Phase 1: Research Planning (10-15 minutes)

**Supervisor Actions**:
1. YOU are the Research Lead - spawn 4 specialists directly with `parent_instance_id` set to YOUR instance_id
2. Define research questions and objectives
3. Identify key topics and keywords
4. Assign research domains to each Research Specialist

**Communication Pattern**:
- Use `broadcast_to_children` to share research objectives
- Workers acknowledge using `reply_to_caller`

**Success Criteria**:
- All 4 workers spawned and acknowledged
- Research scope clearly defined
- Topics and keywords identified

### Phase 2: Data Collection (45-60 minutes)

**Supervisor Actions**:
1. Research Specialist conducts web research using Brave Search and Playwright
2. Research Specialist extracts and curates relevant sources
3. Research Lead monitors progress every 10 minutes
4. Data Analyst validates data quality as sources are collected

**Communication Pattern**:
- Research Specialist uses `reply_to_caller` every 15 minutes with findings
- Research Lead requests additional searches as needed via `send_to_instance`

**MCP Tool Usage**:
- **Brave Search**: For web search queries
- **Playwright**: For browser automation and data extraction
- **Memory MCP** (if available): Store findings for cross-worker access

**Success Criteria**:
- 20+ relevant sources identified and extracted
- All sources have proper citations
- Data quality validated by Data Analyst

### Phase 3: Data Analysis (30-45 minutes)

**Supervisor Actions**:
1. Data Analyst receives collected data from Research Specialist
2. Data Analyst performs statistical analysis and trend detection
3. Research Lead coordinates data validation
4. Report Synthesizer begins preliminary synthesis

**Communication Pattern**:
- Use `send_to_instance` to pass data from Research Specialist to Data Analyst
- Data Analyst uses `reply_to_caller` with analysis results
- Parallel work: Report Synthesizer begins while analysis completes

**Success Criteria**:
- Statistical summaries completed
- Trends and patterns identified
- Quantitative insights extracted

### Phase 4: Synthesis & Insights (30-40 minutes)

**Supervisor Actions**:
1. Report Synthesizer receives findings from Research Specialist and Data Analyst
2. Report Synthesizer performs cross-source analysis
3. Research Lead reviews synthesized insights
4. Identify key recommendations and action items

**Communication Pattern**:
- Use `coordinate_instances` with `coordination_type="sequential"`
- Research Specialist → Data Analyst → Report Synthesizer
- Research Lead reviews using `send_to_instance`

**Success Criteria**:
- Key insights identified across all sources
- Recommendations formulated
- Gaps and limitations documented

### Phase 5: Report Generation (20-30 minutes)

**Supervisor Actions**:
1. Technical Writer receives all findings, analysis, and synthesis
2. Technical Writer formats professional research report
3. Research Lead performs final review
4. Deliver completed report

**Communication Pattern**:
- Use `broadcast_to_children` to share final findings with all workers for review
- Technical Writer uses `reply_to_caller` to submit draft report
- Research Lead approves final version

**Success Criteria**:
- Complete formatted report delivered
- All sources properly cited
- Executive summary included
- Visual presentation of key findings

---

## Communication Protocols

### Research Data Sharing
**Challenge**: Workers need to access findings from other workers

**Solutions**:
1. **Memory MCP**: Store findings in shared memory accessible to all workers
2. **Supervisor Relay**: Research Lead passes findings between workers using `send_to_instance`
3. **Broadcast Updates**: Use `broadcast_to_children` to share important findings with entire team

### Progress Monitoring
**Pattern**: Research Lead polls every 10-15 minutes using `get_pending_replies`

**Status Update Format**:
- Research Specialist: "Collected 15 sources on [topic], found key data on [insight]"
- Data Analyst: "Analyzed 12 datasets, identified 3 key trends: [list trends]"
- Report Synthesizer: "Synthesized 4 key insights: [list insights]"
- Technical Writer: "Draft report 60% complete, executive summary done"

### Coordination Patterns

**Sequential Research Pipeline**:
1. Research Specialist collects sources
2. Data Analyst analyzes data
3. Report Synthesizer extracts insights
4. Technical Writer formats report

Use `coordinate_instances` with `coordination_type="sequential"` for this workflow.

**Parallel Collection**:
During Phase 2, spawn multiple Research Specialists for different research domains, then aggregate findings.

---

## Error Handling Strategies

### Insufficient Data Collection
**Symptoms**: Research Specialist finds <10 relevant sources

**Actions**:
1. Expand search keywords using `send_to_instance`
2. Try alternative search strategies
3. Use Playwright for deeper web scraping
4. Consider spawning additional Research Specialist for parallel collection

### Low-Quality Sources
**Symptoms**: Data Analyst identifies unreliable or biased sources

**Actions**:
1. Research Specialist filters out low-credibility sources
2. Apply source credibility criteria (peer-reviewed, reputable publishers)
3. Cross-validate findings across multiple independent sources

### Analysis Gaps
**Symptoms**: Report Synthesizer identifies missing information

**Actions**:
1. Research Lead sends targeted research request to Research Specialist
2. Focus on filling identified gaps
3. Document limitations if gaps cannot be filled

### Citation Errors
**Symptoms**: Technical Writer finds incomplete or incorrect citations

**Actions**:
1. Send citation issues back to Research Specialist via `send_to_instance`
2. Research Specialist retrieves missing citation information
3. Technical Writer updates with corrected citations

---

## MCP Tool Requirements

### Required Tools
- **None** - Basic research can be done with Claude's built-in capabilities

### Recommended Tools
- **Brave Search**: Web search for current information
- **Playwright**: Browser automation for data extraction
- **Memory**: Shared data storage across workers

### Optional Tools
- **Wikipedia**: Quick reference lookups
- **ArXiv**: Academic paper research
- **GitHub**: Code and repository research

### Tool Configuration
Configure MCP tools when spawning Research Lead:
- Include only necessary tools to avoid permission prompts
- Configure tool-specific parameters (e.g., search result limits)

---

## Research Topic Examples

### Market Research
**Topic**: "Analyze the AI code assistant market: competitors, pricing, features, market size"

**Research Questions**:
- Who are the top 10 competitors?
- What are their pricing models?
- What features do they offer?
- What is the total addressable market size?
- What are the key trends and differentiators?

**Expected Duration**: 2-3 hours

### Technology Trend Analysis
**Topic**: "Research the adoption of Rust programming language in enterprise: trends, use cases, challenges"

**Research Questions**:
- What is the adoption trend over the past 5 years?
- Which enterprises are using Rust?
- What are the primary use cases?
- What challenges do organizations face?
- What is the future outlook?

**Expected Duration**: 2-3 hours

### Competitive Intelligence
**Topic**: "Competitive analysis of project management SaaS: Asana, Monday.com, ClickUp, Linear"

**Research Questions**:
- What are the key features of each platform?
- What are their pricing strategies?
- What are their target markets?
- What are their strengths and weaknesses?
- What gaps exist in the market?

**Expected Duration**: 3-4 hours

### Academic Literature Review
**Topic**: "Review recent research on transformer architecture improvements (2023-2025)"

**Research Questions**:
- What are the key innovations in transformer architectures?
- Which papers have the most impact?
- What are the performance improvements?
- What are the limitations of current approaches?
- What are the future research directions?

**Expected Duration**: 3-4 hours

---

## Resource Constraints

### Per-Worker Limits
- **Max Tokens**: 100,000 tokens per worker
- **Max Cost**: $5.00 per worker ($25 total)
- **Timeout**: 180 minutes (3 hours) per worker
- **MCP Tool Calls**: Unlimited (but consider rate limits)

### Team-Wide Limits
- **Max Instances**: 5 (1 lead + 4 workers)
- **Total Duration**: 4 hours maximum
- **Total Cost**: $25 maximum
- **Concurrent Tool Calls**: 10 across all workers

### Web Research Rate Limits
- **Brave Search**: 50 queries per minute across all workers
- **Playwright**: 20 concurrent browser sessions maximum
- Be respectful of website rate limits when scraping

---

## Success Metrics

### Data Collection Metrics
- ✅ 20+ relevant sources identified
- ✅ All sources have proper citations
- ✅ Data quality validated (>80% credible sources)
- ✅ Collection completed within 60 minutes

### Analysis Metrics
- ✅ Statistical summaries completed
- ✅ 3+ key trends identified
- ✅ Quantitative insights extracted
- ✅ Data visualizations created (if applicable)

### Synthesis Metrics
- ✅ Cross-source analysis completed
- ✅ 5+ key insights extracted
- ✅ Recommendations formulated
- ✅ Gaps and limitations documented

### Report Quality Metrics
- ✅ Professional formatting
- ✅ All sources properly cited (APA/MLA/Chicago style)
- ✅ Executive summary included
- ✅ Visual presentation of findings
- ✅ Clear recommendations and action items

### Timeline Metrics
- ✅ Planning: <15 minutes
- ✅ Data collection: <60 minutes
- ✅ Analysis: <45 minutes
- ✅ Synthesis: <40 minutes
- ✅ Report generation: <30 minutes
- ✅ Total: <3 hours

---

## Network Topology

```
Research Lead (Supervisor)
├── Research Specialist (Worker) [Brave Search + Playwright]
├── Data Analyst (Worker)
├── Report Synthesizer (Worker)
└── Technical Writer (Worker)
```

**Hierarchy**: Single-level supervised network
**Communication**: Bidirectional (supervisor ↔ workers)
**Coordination**: Sequential pipeline with parallel collection option

---

## Advanced Variations

### Multi-Domain Parallel Research
For broad research topics, spawn multiple Research Specialists for different domains:

```
Research Lead (Supervisor)
├── Research Specialist - Domain 1 (Worker)
├── Research Specialist - Domain 2 (Worker)
├── Research Specialist - Domain 3 (Worker)
├── Data Analyst (Worker)
├── Report Synthesizer (Worker)
└── Technical Writer (Worker)
```

**Team Size**: 7 instances (1 lead + 6 workers)
**Use Case**: Comprehensive multi-domain research

### Rapid Intelligence Gathering
Simplified 3-worker team for quick research:

```
Research Lead (Supervisor)
├── Research Specialist (Worker)
├── Analyst/Synthesizer (Worker) [Combined role]
└── Technical Writer (Worker)
```

**Team Size**: 4 instances (1 lead + 3 workers)
**Duration**: 1-2 hours
**Use Case**: Quick competitive intelligence, rapid market scans

---

## Common Pitfalls

### ❌ Not Configuring MCP Tools
**Result**: Research Specialist cannot access Brave Search or Playwright
**Solution**: Configure MCP tools when spawning Research Lead or pass tool access to workers

### ❌ Insufficient Source Validation
**Result**: Low-quality or biased findings
**Solution**: Data Analyst validates sources, Research Specialist applies credibility criteria

### ❌ Poor Data Handoffs
**Result**: Workers don't have access to data from other workers
**Solution**: Use Memory MCP or supervisor relay pattern for data sharing

### ❌ Incomplete Citations
**Result**: Report lacks credibility and reproducibility
**Solution**: Research Specialist captures full citation info during collection

### ❌ No Executive Summary
**Result**: Report findings buried in details
**Solution**: Report Synthesizer creates clear executive summary with key insights

---

## Template Version

**Version**: 1.0
**Last Updated**: October 2025
**Tested With**: Madrox v1.0, Claude Sonnet 3.5
