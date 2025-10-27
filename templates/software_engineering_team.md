# Software Engineering Team Template

## Overview

Deploy a complete cross-functional software engineering team with a technical lead who coordinates development, testing, and delivery of SaaS products.

**Best for**: Building web applications, APIs, microservices, full-stack products

**Team Size**: 6 instances (1 supervisor + 5 workers)

**Estimated Duration**: 2-4 hours depending on complexity

---

## Team Structure

### Technical Lead (Supervisor)
**Role**: `architect` or `general`
**Enable Madrox**: ✅ Required (must spawn team members)

**Responsibilities**:
- Spawn and manage specialized team members
- Coordinate development workflow across phases
- Brief team on project requirements using broadcast
- Aggregate results and ensure quality standards
- Handle errors and blockers across team
- Deliver final integrated solution

### Team Members (Workers)

All team members must be spawned with `parent_instance_id` set to the Technical Lead's instance ID to enable bidirectional messaging.

#### 1. Backend Developer
**Role**: `backend_developer`
**Focus**: API design, database architecture, business logic
**Deliverables**:
- RESTful/GraphQL API endpoints
- Database schema and migrations
- Authentication and authorization logic
- Core business logic implementation

#### 2. Frontend Developer
**Role**: `frontend_developer`
**Focus**: UI/UX, client-side application, responsive design
**Deliverables**:
- React/Vue/Angular components
- State management implementation
- Responsive layouts and styling
- Client-side routing and navigation

#### 3. DevOps Engineer
**Role**: `devops_engineer`
**Focus**: Infrastructure, deployment, CI/CD
**Deliverables**:
- Docker containerization
- CI/CD pipeline configuration
- Cloud deployment setup (AWS/GCP/Azure)
- Monitoring and logging infrastructure

#### 4. QA Engineer
**Role**: `qa_engineer`
**Focus**: Testing strategy, automation, quality assurance
**Deliverables**:
- Test plan and strategy document
- Unit and integration tests
- End-to-end test automation
- Quality gates and acceptance criteria

#### 5. Technical Writer
**Role**: `technical_writer`
**Focus**: Documentation, API references, user guides
**Deliverables**:
- API documentation (OpenAPI/Swagger)
- Setup and deployment guides
- User documentation
- Code comments and inline docs

---

## Workflow Phases

### Phase 1: Team Assembly (5-10 minutes)

**Supervisor Actions**:
1. Spawn Technical Lead
2. Send message to Technical Lead with instructions to spawn 5 team members
3. Technical Lead spawns each team member with `parent_instance_id` parameter
4. Verify all team members spawned successfully using `get_children` tool
5. Confirm 2-level hierarchy using `get_instance_tree` tool

**Success Criteria**:
- All 5 team members spawned with parent_instance_id
- Network topology shows single supervisor with 5 children
- No unwanted extra instances spawned

### Phase 2: Project Briefing (10-15 minutes)

**Supervisor Actions**:
1. Technical Lead uses `broadcast_to_children` to send project briefing to all workers
2. Briefing includes: project description, timeline, individual responsibilities, deliverables
3. Technical Lead polls for acknowledgments using `get_pending_replies`
4. Workers reply using `reply_to_caller` with their understanding and initial plan

**Communication Pattern**:
- **Supervisor → All Workers**: `broadcast_to_children`
- **Each Worker → Supervisor**: `reply_to_caller` (mandatory)
- **Polling**: `get_pending_replies` every 5 minutes

**Success Criteria**:
- All workers acknowledge briefing within 10 minutes
- All workers provide initial approach/plan
- Technical Lead has clear visibility into team readiness

### Phase 3: Design Phase (30-45 minutes)

**Supervisor Actions**:
1. Request design proposals from Backend Developer and Frontend Developer
2. Request infrastructure requirements from DevOps Engineer
3. Request test strategy from QA Engineer
4. Coordinate design review across team
5. Approve designs before implementation begins

**Communication Pattern**:
- **1-on-1 coordination**: Use `send_to_instance` for individual worker requests
- **Design review**: Use `broadcast_to_children` to share designs with full team
- **Feedback collection**: Use `get_pending_replies` to gather input

**Worker Deliverables**:
- Backend: API architecture diagram, database schema, endpoint specifications
- Frontend: Component structure, wireframes, state management approach
- DevOps: Infrastructure diagram, deployment strategy
- QA: Test plan, coverage targets, acceptance criteria
- Tech Writer: Documentation structure outline

**Success Criteria**:
- All designs reviewed and approved by Technical Lead
- No conflicting architectural decisions
- Team alignment on implementation approach

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
