# Software Engineering Team Template

## Overview

Deploy a complete cross-functional software engineering team with a technical lead who **orchestrates and delegates** work to specialized team members. The supervisor NEVER does technical work themselves.

**Best for**: Building web applications, APIs, microservices, full-stack products

**Team Size**: 6 instances (1 supervisor + 5 workers)

**Estimated Duration**: 2-4 hours depending on complexity

**Key Principle**: **Pure Delegation Pattern** - The supervisor only coordinates, never implements

---

## Team Structure

### Technical Lead (Supervisor)
**Role**: `technical_lead` or `general`
**Enable Madrox**: ✅ Required (must spawn team members)

**Responsibilities** (Orchestration Only - NO Technical Work):
- Spawn all team members immediately upon receiving task
- Delegate work to appropriate team members
- Monitor progress via `get_pending_replies` polling
- Unblock team members when they report issues
- Aggregate results and ensure quality standards
- Report final deliverables to parent

**CRITICAL**: The supervisor NEVER:
- ❌ Writes code themselves
- ❌ Creates design documents themselves
- ❌ Implements features themselves
- ❌ Writes tests themselves
- ✅ ONLY delegates and coordinates

### Team Members (Workers)

All team members must be spawned with `parent_instance_id` set to the Technical Lead's instance ID to enable bidirectional messaging.

#### 1. Solutions Architect
**Role**: `architect`
**Focus**: System design, architecture decisions, technical specifications
**Deliverables**:
- System architecture diagrams
- Technical design documents
- API specifications and contracts
- Database schema design
- Integration point definitions

#### 2. Backend Developer
**Role**: `backend_developer`
**Focus**: API implementation, database operations, business logic
**Deliverables**:
- RESTful/GraphQL API endpoints
- Database migrations and queries
- Authentication and authorization logic
- Core business logic implementation

#### 3. Frontend Developer
**Role**: `frontend_developer`
**Focus**: UI/UX implementation, client-side application
**Deliverables**:
- React/Vue/Angular components
- State management implementation
- Responsive layouts and styling
- Client-side routing and navigation

#### 4. DevOps Engineer
**Role**: `devops_engineer`
**Focus**: Infrastructure, deployment, CI/CD
**Deliverables**:
- Docker containerization
- CI/CD pipeline configuration
- Cloud deployment setup (AWS/GCP/Azure)
- Monitoring and logging infrastructure

#### 5. QA Engineer
**Role**: `qa_engineer`
**Focus**: Testing strategy, automation, quality assurance
**Deliverables**:
- Test plan and strategy document
- Unit and integration tests
- End-to-end test automation
- Quality gates and acceptance criteria

---

## Workflow Phases

### 🚨 CRITICAL EXECUTION INSTRUCTIONS FOR SUPERVISOR

**YOU ARE A COORDINATOR, NOT A WORKER**

When you receive a task:
1. **IMMEDIATELY spawn all 5 team members** (do NOT analyze or design first)
2. **DELEGATE all technical work** to team members
3. **NEVER write code, designs, or documentation yourself**
4. **ONLY coordinate, monitor, and aggregate results**

Your workflow:
```
Receive task → Spawn team → Broadcast briefing → Delegate to specialists → Monitor → Aggregate → Deliver
```

If you find yourself:
- Reading codebase files directly → ❌ STOP, delegate to Architect
- Creating design documents → ❌ STOP, delegate to Architect
- Writing implementation code → ❌ STOP, delegate to Developer
- Writing tests → ❌ STOP, delegate to QA Engineer

**Your only tools**: `spawn_claude`, `broadcast_to_children`, `send_to_instance`, `get_pending_replies`, `get_children`

---

### Phase 1: Team Assembly (2-5 minutes)

**Supervisor Actions** (Immediate upon receiving task):
1. **Immediately spawn all 5 team members** with `parent_instance_id` parameter:
   - Solutions Architect (`architect` role)
   - Backend Developer (`backend_developer` role)
   - Frontend Developer (`frontend_developer` role)
   - DevOps Engineer (`devops_engineer` role)
   - QA Engineer (`qa_engineer` role)
2. Verify all spawned using `get_children` tool
3. Confirm 2-level hierarchy using `get_instance_tree` tool

**Success Criteria**:
- All 5 team members spawned immediately
- Network topology shows single supervisor with 5 children
- No unwanted extra instances spawned
- Total time: <5 minutes

### Phase 2: Project Briefing (5-10 minutes)

**Supervisor Actions** (Pure Delegation):
1. Use `broadcast_to_children` to send project briefing to ALL workers
2. Briefing includes: project description, timeline, individual responsibilities
3. Poll for acknowledgments using `get_pending_replies` (every 2-3 minutes)
4. Verify all workers acknowledged within 10 minutes

**Communication Pattern**:
- **Supervisor → All Workers**: `broadcast_to_children`
- **Each Worker → Supervisor**: `reply_to_caller` (mandatory)
- **Polling**: `get_pending_replies` every 2-3 minutes

**Success Criteria**:
- All workers acknowledge briefing within 10 minutes
- All workers understand their responsibilities
- Technical Lead confirms team readiness

### Phase 3: Design Phase (20-30 minutes)

**Supervisor Actions** (Delegate to Architect):
1. **Delegate design work to Solutions Architect** using `send_to_instance`
2. Request architecture document from Architect
3. Wait for Architect's design using `get_pending_replies`
4. Once received, **broadcast design to all team members** for review
5. Collect feedback from team via `get_pending_replies`
6. Send feedback to Architect for revisions if needed
7. Approve final design before proceeding to implementation

**Communication Pattern**:
- **Supervisor → Architect**: `send_to_instance` (design request)
- **Architect → Supervisor**: `reply_to_caller` (design document)
- **Supervisor → All Workers**: `broadcast_to_children` (design review)
- **Workers → Supervisor**: `reply_to_caller` (feedback)

**Architect Deliverables**:
- System architecture diagram
- API specifications and endpoints
- Database schema design
- Integration point definitions
- Technology stack recommendations

**Success Criteria**:
- Architecture document received from Architect
- All team members reviewed and approved design
- No conflicting architectural decisions
- Technical Lead never wrote design themselves (only coordinated)

### Phase 4: Implementation Phase (60-90 minutes)

**Supervisor Actions**:
1. Coordinate parallel implementation across Backend, Frontend, DevOps
2. Use `coordinate_instances` tool with `coordination_type="parallel"`
3. Poll for progress updates every 15 minutes
4. Unblock workers if they report issues or blockers
5. QA Engineer begins writing tests based on implementation progress

**Communication Pattern**:
- **Progress updates**: Workers use `reply_to_caller` every 15 minutes with status
- **Blocker handling**: Workers report blockers immediately via `reply_to_caller`
- **Cross-team questions**: Technical Lead facilitates using `send_to_instance`

**Error Handling**:
- **Non-responsive worker**: Send direct message after 3 missed check-ins
- **Stuck worker**: Use `interrupt_instance` and redirect to simpler approach
- **Critical failure**: Use `terminate_instance` and respawn replacement worker

**Success Criteria**:
- Backend API implemented and testable
- Frontend components built and functional
- DevOps infrastructure configured
- Tests written for critical paths

### Phase 5: Integration & Testing (20-30 minutes)

**Supervisor Actions**:
1. Frontend Developer integrates with Backend API
2. QA Engineer runs full test suite
3. DevOps Engineer deploys to staging environment
4. Technical Lead coordinates sequential handoffs using `coordinate_instances` with `coordination_type="sequential"`

**Communication Pattern**:
- **Sequential coordination**: Backend → Frontend → DevOps → QA
- **Handoff validation**: Each worker verifies output before next stage
- **Issue reporting**: Workers report integration issues immediately

**Success Criteria**:
- Frontend successfully integrates with Backend API
- All tests pass in staging environment
- Application deployed and accessible
- No critical bugs identified

### Phase 6: Documentation & Delivery (15-20 minutes)

**Supervisor Actions**:
1. Technical Writer documents all components
2. Technical Lead aggregates all deliverables
3. Perform final review and quality check
4. Package deliverables for handoff

**Communication Pattern**:
- **Final deliverables**: All workers use `reply_to_caller` with completion status
- **Documentation requests**: Tech Writer uses supervisor as intermediary for questions

**Success Criteria**:
- Complete API documentation
- Setup and deployment guides
- All code documented with comments
- Final deliverable package ready

---

## Communication Protocols

### Supervisor → All Workers (Broadcast)
**Tool**: `broadcast_to_children`
**Use Cases**:
- Project briefings
- Phase transitions
- Urgent announcements
- Design reviews

**Pattern**:
1. Supervisor calls `broadcast_to_children` with message
2. All workers receive identical message
3. Workers reply using `reply_to_caller`
4. Supervisor polls with `get_pending_replies`

### Supervisor → Individual Worker (Direct)
**Tool**: `send_to_instance`
**Use Cases**:
- 1-on-1 coordination
- Specific task assignments
- Blocker resolution
- Individual feedback

**Pattern**:
1. Supervisor calls `send_to_instance` targeting specific worker
2. Worker receives message
3. Worker replies using `reply_to_caller`
4. Supervisor receives reply in response queue

### Worker → Supervisor (Reply)
**Tool**: `reply_to_caller`
**Use Cases**:
- Status updates
- Deliverable submissions
- Questions and blockers
- Acknowledgments

**Pattern**:
1. Worker calls `reply_to_caller` with message
2. Message queued in supervisor's response queue
3. Supervisor polls with `get_pending_replies` to retrieve
4. Supervisor processes and responds if needed

### Coordination Patterns
**Tool**: `coordinate_instances`

**Parallel Coordination** (`coordination_type="parallel"`):
- All workers execute simultaneously
- Use during implementation phase
- Technical Lead aggregates results

**Sequential Coordination** (`coordination_type="sequential"`):
- Workers execute in specific order
- Use during integration phase
- Handoffs between workers

---

## Error Handling Strategies

### Non-Responsive Worker
**Symptoms**: Worker doesn't reply after 3 polling attempts (15 minutes)

**Actions**:
1. Send direct message using `send_to_instance` with urgent flag
2. Wait for immediate response (60 second timeout)
3. If no response, check worker status with `get_live_instance_status`
4. If stuck, use `interrupt_instance` to send Ctrl+C
5. Redirect worker to simpler alternative approach

### Stuck Worker
**Symptoms**: Worker reports being blocked or unable to proceed

**Actions**:
1. Use `send_to_instance` to understand blocker details
2. Provide alternative approach or simplified requirements
3. If blocker is external dependency, coordinate with relevant team member
4. If unresolvable, use `interrupt_instance` and reassign task

### Worker Crash or Critical Failure
**Symptoms**: Worker becomes unresponsive or reports fatal error

**Actions**:
1. Use `terminate_instance` to clean up failed worker
2. Spawn replacement worker with same role
3. Brief replacement worker on progress made by failed worker
4. Resume task from last checkpoint

### Integration Failures
**Symptoms**: Components don't integrate correctly during Phase 5

**Actions**:
1. Identify conflicting component using QA Engineer feedback
2. Send direct messages to relevant workers (e.g., Backend + Frontend)
3. Coordinate bug fix using `coordinate_instances` with relevant workers only
4. Re-run integration tests
5. Iterate until integration succeeds

---

## Resource Constraints

### Per-Worker Limits
- **Max Tokens**: 100,000 tokens per worker
- **Max Cost**: $5.00 per worker ($30 total team cost)
- **Timeout**: 120 minutes per worker
- **Max Retries**: 3 attempts for failed operations

### Team-Wide Limits
- **Max Instances**: 6 (1 lead + 5 workers)
- **Total Duration**: 4 hours maximum
- **Total Cost**: $30 maximum ($5 per worker × 6)
- **Concurrent Operations**: 5 workers in parallel

### Enforcement
- Supervisors should monitor resource usage periodically
- Terminate workers that exceed limits
- Scale down team size if approaching budget limits

---

## Task Customization Examples

### Simple SaaS Application
**Description**: Task management web app with user auth, CRUD operations, PostgreSQL database, React frontend, Docker deployment

**Team**: All 5 workers
**Duration**: 2 hours
**Complexity**: Low

### Medium Complexity Microservices
**Description**: E-commerce platform with 3 microservices (users, products, orders), API gateway, React frontend, Kubernetes deployment

**Team**: All 5 workers + additional Backend Developer for microservices
**Duration**: 4 hours
**Complexity**: Medium

### Enterprise System
**Description**: Multi-tenant SaaS with 5+ microservices, GraphQL gateway, complex frontend, comprehensive test coverage, OpenAPI docs

**Team**: Multiple teams with hierarchical structure (3-level network)
**Duration**: 8+ hours
**Complexity**: High

---

## Success Metrics

### Team Assembly Metrics
- ✅ All 5 workers spawned with `parent_instance_id`
- ✅ 2-level hierarchy topology confirmed
- ✅ No unwanted extra instances spawned
- ✅ Assembly completed within 10 minutes

### Communication Metrics
- ✅ All workers acknowledge briefing within 15 minutes
- ✅ All workers use `reply_to_caller` for responses
- ✅ Supervisor polls regularly (every 5-15 minutes)
- ✅ No communication timeouts or dropped messages

### Deliverable Metrics
- ✅ Backend API implemented and functional
- ✅ Frontend UI completed and integrated
- ✅ Infrastructure deployed to staging
- ✅ Tests pass with >80% coverage
- ✅ Complete documentation delivered

### Quality Metrics
- ✅ No critical bugs in final deliverable
- ✅ All integration points working correctly
- ✅ Code follows best practices and standards
- ✅ Documentation is clear and comprehensive

### Timeline Metrics
- ✅ Design phase: <45 minutes
- ✅ Implementation phase: <90 minutes
- ✅ Integration phase: <30 minutes
- ✅ Total duration: <4 hours

---

## Network Topology

```
Technical Lead (Supervisor)
├── Backend Developer (Worker)
├── Frontend Developer (Worker)
├── DevOps Engineer (Worker)
├── QA Engineer (Worker)
└── Technical Writer (Worker)
```

**Hierarchy**: Single-level supervised network
**Communication**: Bidirectional (supervisor ↔ workers)
**Coordination**: Parallel and sequential patterns

---

## Common Pitfalls

### ❌ Not Setting `parent_instance_id` on Workers
**Result**: Workers cannot use `reply_to_caller`
**Solution**: Always pass `parent_instance_id` when spawning workers

### ❌ Using `wait_for_response=True` During Spawn
**Result**: Supervisor blocks for 120 seconds
**Solution**: Use `wait_for_response=False` for network spawning, poll status separately

### ❌ Not Polling for Replies
**Result**: Worker responses never retrieved
**Solution**: Call `get_pending_replies` every 5-15 minutes

### ❌ Spawning Unwanted Extra Instances
**Result**: Resource waste and network confusion
**Solution**: Never call deprecated `get_main_instance_id` tool

---

## Template Version

**Version**: 2.0
**Last Updated**: October 2025
**Tested With**: Madrox v1.0, Claude Sonnet 3.5, Codex CLI
