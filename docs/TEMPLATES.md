# Madrox Task Template Library

## Overview

The Madrox Task Template Library provides pre-built, production-ready templates for common multi-agent workflows. These templates enable rapid deployment of hierarchical AI teams for complex tasks without needing to design network structures from scratch.

**Key Benefits**:
- **Rapid Deployment**: Spawn complete teams in minutes instead of hours
- **Best Practices**: Templates encode proven coordination patterns and communication protocols
- **Customizable**: Easy to adapt templates to specific use cases
- **Production-Ready**: Include error handling, monitoring, and resource constraints

---

## Available Templates

### 1. Software Engineering Team
**Location**: [`templates/software_engineering_team.md`](/templates/software_engineering_team.md)

**Purpose**: Build web applications, APIs, microservices, full-stack products

**Team Structure**:
- 1 Technical Lead (Supervisor)
- 5 Specialists: Backend Dev, Frontend Dev, DevOps, QA, Tech Writer

**Duration**: 2-4 hours

**Best For**:
- SaaS application development
- API and microservices implementation
- Full-stack product development
- Rapid prototyping

---

### 2. Research Analysis Team
**Location**: [`templates/research_analysis_team.md`](/templates/research_analysis_team.md)

**Purpose**: Gather information, analyze findings, synthesize insights, produce reports

**Team Structure**:
- 1 Research Lead (Supervisor)
- 4 Specialists: Research Specialist, Data Analyst, Report Synthesizer, Tech Writer

**Duration**: 2-3 hours

**Best For**:
- Market research
- Competitive intelligence
- Technology trend analysis
- Academic literature reviews

---

### 3. Security Audit Team
**Location**: [`templates/security_audit_team.md`](/templates/security_audit_team.md)

**Purpose**: Perform comprehensive application security assessment

**Team Structure**:
- 1 Security Lead (Supervisor)
- 6 Specialists: SAST Analyzer, Dependency Auditor, Auth Specialist, API Security, Crypto Analyst, Security Reporter

**Duration**: 2-4 hours

**Best For**:
- Pre-release security reviews
- Compliance assessments (SOC2, HIPAA)
- Vulnerability scanning
- Security hardening

---

### 4. Data Pipeline Team
**Location**: [`templates/data_pipeline_team.md`](/templates/data_pipeline_team.md)

**Purpose**: Design, implement, and monitor production-grade ETL/ELT pipelines

**Team Structure**:
- 1 Data Engineering Lead (Supervisor)
- 4 Specialists: Data Ingestion, Transformation Engineer, Validation Specialist, Monitoring Engineer

**Duration**: 2-4 hours

**Best For**:
- ETL pipeline development
- Data lake ingestion
- Real-time streaming
- Multi-source data aggregation

---

## Quick Start Guide

### Step 1: Choose a Template

Browse available templates and select one that matches your task requirements.

**Example**: Building a task management SaaS → Use **Software Engineering Team**

### Step 2: Review Template Structure

Read the template to understand:
- Team roles and responsibilities
- Workflow phases
- Communication protocols
- Resource constraints
- Success metrics

**Tip**: Pay special attention to the "Workflow Phases" section for execution sequence.

### Step 3: Customize Task Description

Templates have placeholder sections like `[TASK_DESCRIPTION]`. Replace with your specific requirements.

**Example for SW Engineering Team**:
```
TASK: Build a task management SaaS application with:
- User authentication (JWT)
- Task CRUD operations with categories and tags
- PostgreSQL database
- React frontend with Tailwind CSS
- Automated testing
```

### Step 4: Spawn Supervisor

Spawn the supervisor instance with `enable_madrox=True`:

**Using Madrox from Claude Code**:
```
Use mcp__madrox__spawn_claude tool:
- name: "sw-eng-team-lead"
- role: "architect"
- enable_madrox: True
```

**Tip**: Always set `enable_madrox=True` for supervisors who need to spawn children.

### Step 5: Send Instructions

Send the template instructions to the supervisor with your customized task description:

```
Send message to supervisor:

"Execute the Software Engineering Team workflow for the following task:

[YOUR TASK DESCRIPTION]

Follow the template phases:
1. Team Assembly - Spawn 5 specialists with parent_instance_id
2. Project Briefing - Use broadcast_to_children
3. Design Phase - Coordinate design proposals
4. Implementation Phase - Parallel development
5. Integration & Testing - Sequential handoffs
6. Documentation & Delivery - Final deliverable

Ensure all communication uses reply_to_caller for bidirectional messaging.
Report progress and final deliverables."
```

### Step 6: Monitor Progress

Monitor the supervisor's progress:

**Live Status**:
```
Use mcp__madrox__get_live_instance_status:
- instance_id: [supervisor_id]
```

**Pending Replies**:
```
Use mcp__madrox__get_pending_replies:
- instance_id: [supervisor_id]
```

**Network Topology**:
```
Use mcp__madrox__get_instance_tree
```

### Step 7: Collect Results

Once the supervisor reports completion, collect deliverables:

```
Use mcp__madrox__get_pending_replies to get final report
Use mcp__madrox__list_instance_files to see generated files
Use mcp__madrox__retrieve_instance_file to download specific files
```

---

## Template Customization

### Adjusting Team Size

**Add Workers**:
If you need additional specialists, modify the team structure section:

**Example**: Add a second Backend Developer for microservices
```
Modified Team:
- 1 Technical Lead
- 2 Backend Developers (one for each microservice)
- 1 Frontend Developer
- 1 DevOps Engineer
- 1 QA Engineer
- 1 Technical Writer

Total: 7 instances (1 + 6)
```

**Remove Workers**:
For simpler tasks, reduce team size:

**Example**: Simplified SW Engineering Team for prototyping
```
Minimal Team:
- 1 Technical Lead
- 1 Full-Stack Developer (Backend + Frontend combined)
- 1 Technical Writer

Total: 3 instances (1 + 2)
```

### Changing Roles

Madrox supports 10 predefined roles:
- `general` (default)
- `architect`
- `frontend_developer`
- `backend_developer`
- `data_scientist`
- `devops_engineer`
- `designer`
- `qa_engineer`
- `security_analyst`
- `technical_writer`
- `project_manager`

Assign roles that best match your task requirements.

### Modifying Workflow Phases

Templates provide recommended workflow phases, but you can customize:

**Add Phases**: Insert additional steps (e.g., "Security Review" before deployment)
**Remove Phases**: Skip unnecessary steps (e.g., skip "Documentation" for prototypes)
**Reorder Phases**: Change sequence if needed (e.g., "Testing" before "Implementation")

### Adjusting Resource Constraints

Templates include default resource limits. Adjust based on your needs:

**Token Limits**:
```
Default: 100,000 tokens per worker
Increase for complex tasks: 200,000 tokens
Decrease for simple tasks: 50,000 tokens
```

**Cost Limits**:
```
Default: $5 per worker
Adjust based on budget constraints
```

**Timeout**:
```
Default: 120-240 minutes per worker
Increase for long-running tasks: 360 minutes (6 hours)
Decrease for quick tasks: 60 minutes
```

### Adding MCP Tools

Some templates benefit from MCP tool access:

**Research Analysis Team** + **Brave Search**:
```
When spawning Research Lead, configure:
mcp_servers = {
    "brave-search": {"enabled": true},
    "playwright": {"enabled": true}
}
```

**Data Pipeline Team** + **Database Access**:
```
When spawning Data Engineering Lead, configure:
mcp_servers = {
    "postgres": {"enabled": true, "connection": "[connection_string]"},
    "sqlite": {"enabled": true}
}
```

---

## Communication Patterns

### Broadcast Pattern
**Use Case**: Supervisor sends identical message to all workers

**Tool**: `broadcast_to_children`

**When to Use**:
- Project briefings
- Phase transitions
- Urgent announcements
- Design reviews

**Example**:
```
Supervisor broadcasts: "Phase 2 complete. Begin Phase 3: Implementation.
Report progress every 15 minutes using reply_to_caller."
```

### Direct Messaging Pattern
**Use Case**: Supervisor coordinates with individual worker

**Tool**: `send_to_instance`

**When to Use**:
- 1-on-1 coordination
- Specific task assignments
- Blocker resolution
- Individual feedback

**Example**:
```
Supervisor to Backend Developer: "Implement authentication API endpoint.
Use JWT with 24-hour expiration. Reply when complete."
```

### Reply Pattern
**Use Case**: Worker reports status, deliverables, or questions to supervisor

**Tool**: `reply_to_caller`

**When to Use**:
- Status updates
- Deliverable submissions
- Questions and blockers
- Acknowledgments

**Example**:
```
Backend Developer replies: "Authentication API endpoint complete.
Endpoints: POST /auth/login, POST /auth/register, POST /auth/refresh.
JWT implementation with 24-hour expiration. Ready for testing."
```

### Coordination Patterns
**Use Case**: Orchestrate multiple workers in specific sequence

**Tool**: `coordinate_instances`

**Parallel Coordination**:
```
coordination_type: "parallel"
Use Case: All workers execute simultaneously (e.g., implementation phase)
```

**Sequential Coordination**:
```
coordination_type: "sequential"
Use Case: Workers execute in order with handoffs (e.g., ingestion → transformation → validation)
```

---

## Error Handling

### Common Issues and Solutions

#### Non-Responsive Worker
**Symptoms**: Worker doesn't reply after 3 polling attempts (15 minutes)

**Template Guidance**:
1. Send direct message with urgent flag
2. Wait for immediate response (60 second timeout)
3. Check worker status with `get_live_instance_status`
4. If stuck, use `interrupt_instance` to send Ctrl+C
5. Redirect worker to simpler alternative approach

#### Stuck Worker
**Symptoms**: Worker reports being blocked or unable to proceed

**Template Guidance**:
1. Understand blocker details via direct message
2. Provide alternative approach or simplified requirements
3. If blocker is external dependency, coordinate with relevant team member
4. If unresolvable, use `interrupt_instance` and reassign task

#### Worker Crash
**Symptoms**: Worker becomes unresponsive or reports fatal error

**Template Guidance**:
1. Use `terminate_instance` to clean up failed worker
2. Spawn replacement worker with same role
3. Brief replacement worker on progress made by failed worker
4. Resume task from last checkpoint

#### Integration Failures
**Symptoms**: Components don't integrate correctly

**Template Guidance**:
1. Identify conflicting component using QA feedback
2. Send direct messages to relevant workers
3. Coordinate bug fix using `coordinate_instances` with relevant workers only
4. Re-run integration tests
5. Iterate until integration succeeds

---

## Best Practices

### 1. Always Set `parent_instance_id` for Workers
**Why**: Enables `reply_to_caller` for bidirectional messaging

**How**: When supervisor spawns workers, always include `parent_instance_id` parameter

**Result**: Workers can report status, ask questions, and submit deliverables

### 2. Use Non-Blocking Network Spawning
**Why**: Prevents supervisor from blocking for 120 seconds during network setup

**How**: Use `wait_for_response=False` when spawning workers

**Pattern**:
```
1. Supervisor spawns workers with wait_for_response=False
2. Wait 10-15 seconds for network assembly
3. Verify network with get_instance_tree
4. Begin coordination
```

### 3. Poll for Replies Regularly
**Why**: Worker responses queue up and need to be retrieved

**How**: Supervisor calls `get_pending_replies` every 5-15 minutes

**Result**: Supervisor has visibility into worker progress and can respond to blockers

### 4. Establish Clear Success Metrics
**Why**: Provides objective criteria for task completion

**How**: Define measurable outcomes in template (e.g., "All tests pass", "API documentation complete")

**Result**: Clear understanding of when task is done

### 5. Implement Quality Gates
**Why**: Prevents low-quality work from propagating downstream

**How**: Each phase has validation criteria before proceeding to next phase

**Example**: Design phase must be approved by supervisor before implementation begins

### 6. Document Limitations
**Why**: Sets realistic expectations and identifies areas for manual follow-up

**How**: Workers report what they couldn't complete and why

**Result**: Clear handoff with known gaps

---

## Advanced Usage

### Multi-Level Hierarchies

For complex tasks, create multi-level networks:

**Example**: Enterprise System with 3-Level Hierarchy
```
Program Manager (Level 0)
├── Technical Lead 1 (Level 1) - Microservice Team 1
│   ├── Backend Developer (Level 2)
│   ├── Frontend Developer (Level 2)
│   └── QA Engineer (Level 2)
├── Technical Lead 2 (Level 1) - Microservice Team 2
│   ├── Backend Developer (Level 2)
│   ├── Frontend Developer (Level 2)
│   └── QA Engineer (Level 2)
└── DevOps Lead (Level 1) - Infrastructure Team
    ├── DevOps Engineer 1 (Level 2)
    └── DevOps Engineer 2 (Level 2)
```

**Total**: 12 instances (1 + 3 + 8)

**Coordination**: Program Manager coordinates Technical Leads, who coordinate their own teams

### Mixing Claude and Codex Instances

Templates can use both Claude and Codex instances:

**Example**: Claude for architecture, Codex for code implementation
```
Technical Lead (Claude - Supervisor)
├── Architect (Claude - Worker)
├── Backend Developer (Codex - Worker)
├── Frontend Developer (Codex - Worker)
└── QA Engineer (Claude - Worker)
```

**Spawn Codex Workers**:
```
Use mcp__madrox__spawn_codex tool:
- name: "backend-dev-codex"
- model: "gpt-5-codex"
- parent_instance_id: [supervisor_id]
```

### Template Composition

Combine multiple templates for comprehensive workflows:

**Example**: Build → Audit → Deploy
```
Phase 1: Software Engineering Team builds application (4 hours)
Phase 2: Security Audit Team reviews application (2 hours)
Phase 3: DevOps Team deploys to production (1 hour)

Total: 7 hours, 15+ instances across 3 teams
```

---

## Performance Optimization

### Reduce Team Size for Simpler Tasks
**Benefit**: Lower cost, faster coordination
**Trade-off**: Less specialized expertise

### Use Parallel Coordination
**Benefit**: Faster completion time
**Trade-off**: Higher concurrent resource usage

### Set Aggressive Timeouts
**Benefit**: Prevents hanging workers from wasting resources
**Trade-off**: May terminate legitimately slow operations

### Limit Token Usage Per Worker
**Benefit**: Cost control
**Trade-off**: May need to respawn workers if they hit limits

---

## Troubleshooting

### "Supervisor cannot spawn children"
**Cause**: `enable_madrox=True` not set when spawning supervisor
**Solution**: Respawn supervisor with `enable_madrox=True`

### "Worker cannot use reply_to_caller"
**Cause**: `parent_instance_id` not set when spawning worker
**Solution**: Respawn worker with `parent_instance_id` parameter

### "Network takes 120 seconds to spawn"
**Cause**: Using `wait_for_response=True` during network spawning
**Solution**: Use non-blocking pattern (`wait_for_response=False` + verification)

### "Supervisor reports no replies from workers"
**Cause**: Supervisor not polling with `get_pending_replies`
**Solution**: Supervisor should call `get_pending_replies` every 5-15 minutes

### "Unwanted extra instances spawned"
**Cause**: Worker calling deprecated `get_main_instance_id` tool
**Solution**: Use `instance_id` from spawn response, never call `get_main_instance_id`

---

## Template Development Guidelines

### Creating Custom Templates

Want to create your own template? Follow these guidelines:

**Required Sections**:
1. **Overview**: Purpose, best for, team size, duration
2. **Team Structure**: Supervisor + worker roles and responsibilities
3. **Workflow Phases**: Step-by-step execution sequence
4. **Communication Protocols**: How workers coordinate
5. **Error Handling**: Recovery strategies for common failures
6. **Resource Constraints**: Token/cost/time limits
7. **Success Metrics**: Measurable outcomes
8. **Network Topology**: Hierarchy diagram

**Template Format**:
- Markdown format (`.md` files)
- No executable code blocks
- Instruction-based guidance
- Example task descriptions
- Common pitfalls section

**Testing Checklist**:
- ✅ Template instructions are clear and unambiguous
- ✅ All Madrox tools used correctly
- ✅ Communication patterns follow bidirectional messaging
- ✅ Error handling covers common failures
- ✅ Resource limits are realistic
- ✅ Success metrics are measurable
- ✅ Template tested with real task

**Contribution**:
Submit custom templates via GitHub pull request to `/templates` directory.

---

## FAQ

### Q: Can I use templates without modification?
**A**: Yes, templates are production-ready. Just customize the task description placeholder.

### Q: How do I know which template to use?
**A**: Match your task type to template purpose. See "Best For" section in each template.

### Q: Can I combine multiple templates?
**A**: Yes, use template composition for multi-phase workflows (e.g., Build → Audit → Deploy).

### Q: What if my task doesn't fit any template?
**A**: Use templates as starting points and customize team structure, roles, and workflow phases.

### Q: Are templates compatible with Codex instances?
**A**: Yes, templates work with both Claude and Codex instances. Some templates benefit from Codex for code implementation.

### Q: How do I handle tasks larger than template scope?
**A**: Use multi-level hierarchies or spawn multiple teams in parallel.

### Q: Can I create my own templates?
**A**: Yes, follow the "Template Development Guidelines" section and submit via pull request.

### Q: What if a template workflow doesn't work for my use case?
**A**: Customize workflow phases - add, remove, or reorder steps as needed.

---

## Resources

- **Templates Directory**: `/templates`
- **Example Usage**: See individual template files for task examples
- **API Reference**: [`docs/API_REFERENCE.md`](/docs/API_REFERENCE.md)
- **Architecture Guide**: [`docs/ARCHITECTURE.md`](/docs/ARCHITECTURE.md)
- **Troubleshooting**: [`docs/TROUBLESHOOTING.md`](/docs/TROUBLESHOOTING.md)

---

## Template Version

**Document Version**: 1.0
**Last Updated**: October 2025
**Tested With**: Madrox v1.0, Claude Sonnet 3.5, Codex CLI
