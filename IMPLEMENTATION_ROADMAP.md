# Autonomous Supervision Implementation Roadmap

## Overview

Detailed implementation plan for adding autonomous supervision to Madrox, enabling self-monitoring and self-healing agent networks. This roadmap outlines the phases, tasks, and technical implementation details required to build the autonomous supervision system.

---

## Phase 1: Core Infrastructure

### Goals
- Event bus with pub/sub pattern
- Event emission from existing components
- **Transcript analysis system (primary monitoring)**
- Progress tracking foundation
- Optional MCP tools for explicit status reporting

### Tasks

#### 1.1 Event System

**Files to Create**:
```
src/orchestrator/events/__init__.py
src/orchestrator/events/base.py          # NetworkEvent base class
src/orchestrator/events/instance.py      # Instance-related events
src/orchestrator/events/message.py       # Message-related events
src/orchestrator/events/health.py        # Health-related events
src/orchestrator/events/progress.py      # Progress-related events
src/orchestrator/event_bus.py            # EventBus implementation
```

**Implementation Order**:
1. Create `NetworkEvent` base class with timestamp, event_type, instance_id
2. Implement `EventBus` with asyncio.Queue-based pub/sub
3. Add event type definitions (20+ event types)
4. Unit tests for event bus (publish, subscribe, history)

**Code Snippet** (`event_bus.py`):
```python
class EventBus:
    """In-memory event bus for network supervision."""

    def __init__(self, max_history: int = 1000):
        self.subscribers: dict[str, list[asyncio.Queue]] = {}
        self.event_history: deque[NetworkEvent] = deque(maxlen=max_history)
        self._lock = asyncio.Lock()

    async def publish(self, event: NetworkEvent):
        """Publish event to all subscribers."""
        async with self._lock:
            self.event_history.append(event)

        # Notify subscribers
        subscribers = self.subscribers.get(event.event_type, [])
        wildcard_subscribers = self.subscribers.get("*", [])

        for queue in subscribers + wildcard_subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Subscriber queue full, dropping event")

    def subscribe(self, event_type: str = "*") -> asyncio.Queue:
        """Subscribe to events."""
        queue = asyncio.Queue(maxsize=100)
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(queue)
        return queue
```

#### 1.2 Event Integration

**Files to Modify**:
- `src/orchestrator/tmux_instance_manager.py`
- `src/orchestrator/instance_manager.py`

**Integration Points**:
```python
# In spawn_instance()
await self.event_bus.publish(
    InstanceSpawnedEvent(
        instance_id=instance_id,
        name=name,
        role=role,
        parent_id=parent_id
    )
)

# In send_message()
await self.event_bus.publish(
    MessageSentEvent(
        from_instance_id=self.supervisor_id,
        to_instance_id=instance_id,
        message_id=message_id,
        message=message
    )
)

# In state transitions
await self.event_bus.publish(
    InstanceStateChangedEvent(
        instance_id=instance_id,
        old_state=old_state,
        new_state=new_state
    )
)
```

#### 1.3 Transcript Analysis System (Primary Monitoring)

**Philosophy**: Analyze existing transcript data (tmux output, message history) instead of requiring explicit instrumentation.

**Files to Create**:
```
src/orchestrator/transcript_analyzer.py    # TranscriptAnalyzer class (PRIMARY)
src/orchestrator/progress/__init__.py
src/orchestrator/progress/tracker.py       # ProgressTracker class
src/orchestrator/progress/metrics.py       # InstanceMetrics, signals
```

**TranscriptAnalyzer** (primary monitoring):
```python
class TranscriptAnalyzer:
    """Analyzes instance transcripts for progress signals."""

    def __init__(self, instance_manager: InstanceManager):
        self.manager = instance_manager
        self.baseline_patterns: dict[str, PatternProfile] = {}

    async def analyze_instance(self, instance_id: str) -> TranscriptAnalysis:
        """Analyze recent transcript for progress and issues."""

        # Get tmux pane content (existing functionality)
        transcript = await self.manager.get_tmux_pane_content(
            instance_id,
            lines=100
        )

        # Extract progress signals from natural language
        signals = self._extract_progress_signals(transcript)

        # Detect issues from patterns
        issues = self._detect_issues(transcript, signals)

        # Detect anomalies vs baseline
        anomalies = self._detect_anomalies(instance_id, transcript)

        return TranscriptAnalysis(
            instance_id=instance_id,
            signals=signals,
            issues=issues,
            anomalies=anomalies
        )

    def _extract_progress_signals(self, transcript: str) -> list[ProgressSignal]:
        """Extract signals from natural language."""
        signals = []

        # Completion signals
        if re.search(r'\b(completed|finished|done)\b', transcript, re.I):
            signals.append(ProgressSignal(type="completion", confidence=0.9))

        # Active work signals
        if re.search(r'\b(working|analyzing|processing)\b', transcript, re.I):
            signals.append(ProgressSignal(type="active", confidence=0.85))

        # Blocked signals
        if re.search(r'\b(blocked|stuck|waiting for)\b', transcript, re.I):
            signals.append(ProgressSignal(type="blocked", confidence=0.9))

        # Error signals
        if re.search(r'\b(error|failed|exception)\b', transcript, re.I):
            signals.append(ProgressSignal(type="error", confidence=0.95))

        # Tool usage (indicates activity)
        tools_used = re.findall(r'<invoke name="(\w+)">', transcript)
        if tools_used:
            signals.append(ProgressSignal(
                type="tool_execution",
                confidence=0.95,
                details={"tools": tools_used}
            ))

        return signals
```

**Monitoring Loop**:
```python
async def monitor_all_transcripts(self):
    """Continuously analyze instance transcripts."""
    while True:
        for instance_id in self.active_instances:
            # Analyze every 60 seconds
            analysis = await self.transcript_analyzer.analyze_instance(instance_id)

            # Update progress tracker
            await self.progress_tracker.update_from_transcript(
                instance_id,
                analysis
            )

            # Emit events for issues
            for issue in analysis.issues:
                await self.event_bus.publish(
                    IssueDetectedEvent(instance_id=instance_id, issue=issue)
                )

        await asyncio.sleep(60)
```

**Benefits**:
- ✅ No instrumentation needed
- ✅ Rich natural language context
- ✅ Non-intrusive
- ✅ Leverages existing infrastructure

#### 1.4 Optional MCP Tools (Supplementary)

**Note**: Transcript analysis is primary. These tools are optional for explicit status reporting.

**File to Modify**:
- `src/orchestrator/mcp_adapter.py`

**Optional Tools**:

1. **report_status** (optional):
```python
async def _report_status(
    self,
    instance_id: str,
    status: str,
    progress_percentage: float | None = None,
    message: str | None = None
) -> dict:
    """Optional explicit status reporting (transcript analysis is primary)."""

    await self.event_bus.publish(
        StatusReportEvent(
            instance_id=instance_id,
            status=status,
            progress=progress_percentage,
            message=message
        )
    )

    return {"success": True, "message": "Status recorded"}
```

2. **log_checkpoint** (optional):
```python
async def _log_checkpoint(
    self,
    instance_id: str,
    checkpoint_type: str,
    task_description: str,
    details: dict | None = None
) -> dict:
    """Optional explicit checkpoint logging (transcript analysis handles most cases)."""

    checkpoint = Checkpoint(
        timestamp=datetime.now(UTC),
        checkpoint_type=checkpoint_type,
        task_description=task_description,
        details=details or {}
    )

    await self.event_bus.publish(
        CheckpointEvent(
            instance_id=instance_id,
            checkpoint=checkpoint
        )
    )

    return {"success": True, "checkpoint_id": checkpoint.id}
```

**When to use these tools**:
- High-stakes operations needing explicit confirmation
- Instances that don't produce regular output
- Fine-grained progress tracking (e.g., "45% complete")

### Deliverables Phase 1
- ✅ Event bus with 20+ event types
- ✅ Event emission from instance manager
- ✅ **Transcript analyzer (primary monitoring mechanism)**
- ✅ Progress tracker with metrics storage
- ✅ Optional MCP tools: report_status, log_checkpoint (supplementary)
- ✅ Unit tests (>80% coverage)

---

## Phase 2: Supervisor Agent

### Goals
- Supervisor agent with specialized system prompt
- Auto-spawn supervisor on network creation
- Decision engine with rule matching
- Action executor for remediation

### Tasks

#### 2.1 Supervisor Agent System Prompt

**File to Create**:
```
resources/prompts/supervisor.txt
```

**Prompt Content** (excerpt):
```
You are the Supervisor Agent for a Madrox multi-agent network.

RESPONSIBILITIES:
1. Monitor all instances for health, progress, and issues
2. Detect problems: stuck, waiting, idle, error loops, deadlocks
3. Make autonomous decisions to resolve issues
4. Coordinate work distribution and load balancing
5. Escalate critical unresolvable issues

AVAILABLE TOOLS:
- get_network_status: View all instances and their states
- get_instance_metrics: Detailed progress metrics for instance
- send_to_instance: Send message to any instance
- spawn_instance: Create new helper instance
- terminate_instance: Kill problematic instance
- broadcast_to_children: Message all children of parent
- escalate_issue: Alert user about critical problem

DECISION GUIDELINES:

Stuck Detection (instance busy >5min, no progress):
- Send status check message
- If no response in 2min, send reminder
- If still no response, spawn debugger helper
- After 3 failed interventions, escalate to user

Waiting Detection (instance idle, recently completed work):
- Check if there's pending work in queue
- If yes, assign next work item
- If no, send "standby" message

Error Loop (>3 errors in 5min):
- Analyze error patterns
- If fixable, send guidance
- If not, spawn specialized helper
- If helpers don't resolve, escalate

Deadlock (circular wait):
- Detect cycle in wait-for graph
- Break cycle by providing interim result
- Coordinate resolution between blocked instances

ESCALATION CRITERIA:
- 3+ consecutive failed interventions
- Resource limits preventing helper spawn
- Unrecognized error patterns
- User-defined critical thresholds breached
```

#### 2.2 Supervisor Auto-Spawn

**Files to Modify**:
- `src/orchestrator/instance_manager.py`

**Implementation**:
```python
async def spawn_supervised_network(
    self,
    coordinator_config: dict,
    supervision_config: SupervisionConfig | None = None
) -> str:
    """Spawn a network with autonomous supervision."""

    # Spawn coordinator
    coordinator_id = await self.spawn_instance(**coordinator_config)

    # Spawn supervisor
    supervisor_id = await self.spawn_instance(
        name="network-supervisor",
        role="supervisor",
        parent_instance_id=None,  # Root level
        enable_madrox=True,
        system_prompt=load_supervisor_prompt(),
        wait_for_ready=True
    )

    # Link supervisor to coordinator
    self.supervision_registry[coordinator_id] = supervisor_id

    # Start supervisor monitoring loop
    asyncio.create_task(
        self._supervisor_monitor_loop(supervisor_id, coordinator_id)
    )

    return coordinator_id
```

#### 2.3 Decision Engine

**Files to Create**:
```
src/orchestrator/supervisor/__init__.py
src/orchestrator/supervisor/decision_engine.py
src/orchestrator/supervisor/rules.py
src/orchestrator/supervisor/actions.py
```

**DecisionEngine**:
```python
class DecisionEngine:
    """Makes autonomous supervision decisions."""

    def __init__(self, progress_tracker: ProgressTracker):
        self.progress_tracker = progress_tracker
        self.rules = [
            StuckInstanceRule(),
            WaitingInstanceRule(),
            ErrorLoopRule(),
            DeadlockRule(),
            IdleInstanceRule()
        ]

    async def evaluate(self, network_state: NetworkState) -> list[Decision]:
        """Evaluate all rules and return decisions."""
        decisions = []

        for rule in self.rules:
            if rule.condition_met(network_state):
                decision = rule.make_decision(network_state)
                if decision:
                    decisions.append(decision)

        # Sort by priority
        decisions.sort(key=lambda d: d.priority)

        return decisions
```

**Example Rule**:
```python
class StuckInstanceRule:
    """Detect and handle stuck instances."""

    def condition_met(self, state: NetworkState) -> bool:
        """Check if any instance is stuck."""
        for instance in state.instances.values():
            if state.progress_tracker.analyze_instance(instance.id) == ProgressState.STUCK:
                return True
        return False

    def make_decision(self, state: NetworkState) -> Decision:
        """Create decision for stuck instance."""
        stuck_instances = [
            i for i in state.instances.values()
            if state.progress_tracker.analyze_instance(i.id) == ProgressState.STUCK
        ]

        instance = stuck_instances[0]  # Handle first

        intervention_count = state.intervention_history.count(instance.id)

        if intervention_count == 0:
            # First intervention: Status check
            return Decision(
                decision_type=DecisionType.INTERVENE,
                actions=[
                    SendMessageAction(
                        instance_id=instance.id,
                        message="I notice you haven't made progress in 5 minutes. "
                               "Can you provide a status update?"
                    )
                ],
                confidence=0.9
            )
        elif intervention_count == 1:
            # Second intervention: Reminder
            return Decision(
                decision_type=DecisionType.INTERVENE,
                actions=[
                    SendMessageAction(
                        instance_id=instance.id,
                        message="Following up on status. Are you blocked? "
                               "Do you need assistance?"
                    )
                ],
                confidence=0.85
            )
        elif intervention_count == 2:
            # Third intervention: Spawn helper
            return Decision(
                decision_type=DecisionType.SPAWN_HELPER,
                actions=[
                    SpawnInstanceAction(
                        role="debugger",
                        parent_id=instance.parent_id
                    ),
                    SendMessageAction(
                        instance_id=instance.id,
                        message="A debugger specialist has been assigned to assist you."
                    )
                ],
                confidence=0.8
            )
        else:
            # Escalate
            return Decision(
                decision_type=DecisionType.ESCALATE,
                actions=[
                    EscalateAction(
                        severity="error",
                        message=f"Instance {instance.name} stuck after 3 interventions"
                    )
                ],
                confidence=0.95
            )
```

#### 2.4 Action Executor

**File to Create**:
```
src/orchestrator/supervisor/action_executor.py
```

**Implementation**:
```python
class ActionExecutor:
    """Executes supervisor decisions."""

    def __init__(self, instance_manager: InstanceManager):
        self.manager = instance_manager
        self.execution_history: list[ActionResult] = []

    async def execute(self, decision: Decision) -> list[ActionResult]:
        """Execute all actions in a decision."""
        results = []

        for action in decision.actions:
            result = await self._execute_action(action)
            results.append(result)

            # Log execution
            logger.info(
                f"Executed action {action.action_type}",
                extra={"decision_id": decision.decision_id, "result": result}
            )

            # Record in history
            self.execution_history.append(result)

        return results

    async def _execute_action(self, action: Action) -> ActionResult:
        """Execute single action."""
        try:
            if isinstance(action, SendMessageAction):
                response = await self.manager.send_to_instance(
                    instance_id=action.target_instance_id,
                    message=action.message,
                    wait_for_response=action.wait_for_response,
                    timeout_seconds=action.timeout_seconds
                )
                return ActionResult(success=True, data=response)

            elif isinstance(action, SpawnInstanceAction):
                instance_id = await self.manager.spawn_instance(
                    name=action.name,
                    role=action.role,
                    parent_instance_id=action.parent_id
                )
                return ActionResult(success=True, instance_id=instance_id)

            # ... other action types

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return ActionResult(success=False, error=str(e))
```

### Deliverables Phase 2
- ✅ Supervisor system prompt (100+ lines)
- ✅ Auto-spawn logic for supervisor
- ✅ Decision engine with 5 rule types
- ✅ Action executor with 6 action types
- ✅ Integration tests

---

## Phase 3: Detection & Remediation

### Goals
- Implement all detection heuristics
- Test remediation actions
- Fine-tune detection thresholds
- End-to-end workflow tests

### Tasks

#### 3.1 Detection Heuristics

**File**: `src/orchestrator/progress/analyzer.py`

**Implementations**:

1. **Stuck Detection**:
```python
def _is_stuck(self, metrics: InstanceMetrics) -> bool:
    """Detect if instance is stuck."""
    # Must be in busy state
    if metrics.current_state != "busy":
        return False

    # No checkpoints in last 5 minutes
    time_since_checkpoint = (
        datetime.now(UTC) - metrics.last_checkpoint.timestamp
    ).total_seconds()

    if time_since_checkpoint < 300:
        return False

    # No tool executions in last 5 minutes
    recent_tools = sum(
        count for tool, count in metrics.tool_executions.items()
        if metrics.tool_timestamps[tool] > datetime.now(UTC) - timedelta(minutes=5)
    )

    return recent_tools == 0
```

2. **Waiting Detection**:
```python
def _is_waiting(self, metrics: InstanceMetrics) -> bool:
    """Detect if instance is waiting for work."""
    # Must be idle
    if metrics.current_state != "idle":
        return False

    # Recently completed something
    if not metrics.last_checkpoint:
        return False

    if metrics.last_checkpoint.checkpoint_type != "completed":
        return False

    # Idle for >2 minutes after completion
    idle_time = (
        datetime.now(UTC) - metrics.last_activity
    ).total_seconds()

    return idle_time > 120
```

3. **Error Loop Detection**:
```python
def _is_error_loop(self, metrics: InstanceMetrics) -> bool:
    """Detect if instance is in error loop."""
    # Count errors in last 5 minutes
    recent_errors = [
        error for error in metrics.error_history
        if error.timestamp > datetime.now(UTC) - timedelta(minutes=5)
    ]

    if len(recent_errors) < 3:
        return False

    # Check if errors are similar (same type)
    error_types = [e.error_type for e in recent_errors]
    most_common = max(set(error_types), key=error_types.count)

    return error_types.count(most_common) >= 3
```

4. **Deadlock Detection**:
```python
def detect_deadlock(self, network: NetworkState) -> list[list[str]]:
    """Detect circular wait conditions."""
    # Build wait-for graph
    wait_graph: dict[str, str] = {}

    for instance_id, instance in network.instances.items():
        if instance.waiting_for_instance_id:
            wait_graph[instance_id] = instance.waiting_for_instance_id

    # Find cycles using DFS
    def find_cycle(start: str, visited: set, path: list) -> list[str] | None:
        if start in visited:
            # Found cycle
            cycle_start = path.index(start)
            return path[cycle_start:]

        visited.add(start)
        path.append(start)

        if start in wait_graph:
            next_node = wait_graph[start]
            return find_cycle(next_node, visited, path)

        return None

    cycles = []
    for instance_id in wait_graph:
        cycle = find_cycle(instance_id, set(), [])
        if cycle and cycle not in cycles:
            cycles.append(cycle)

    return cycles
```

#### 3.2 Remediation Testing

**Test Scenarios**:
1. Simulated stuck instance → Supervisor sends messages → Resolves
2. Simulated waiting instance → Supervisor assigns work → Resumes
3. Simulated error loop → Supervisor spawns helper → Recovers
4. Simulated deadlock → Supervisor breaks cycle → Unblocks

**File**: `tests/integration/test_remediation.py`

#### 3.3 Threshold Tuning

Run experiments to tune:
- Stuck threshold (300s → optimal?)
- Waiting threshold (120s → optimal?)
- Error loop count (3 → optimal?)
- Intervention timing (2min → optimal?)

### Deliverables Phase 3
- ✅ 5 detection heuristics implemented
- ✅ Remediation actions tested
- ✅ Thresholds tuned via experimentation
- ✅ Integration tests passing

---

## Phase 4: Testing & Documentation

### Goals
- Comprehensive test coverage
- Performance benchmarking
- Documentation updates
- Example workflows

### Tasks

#### 4.1 Unit Tests

**Test Files**:
```
tests/test_event_bus.py
tests/test_progress_tracker.py
tests/test_decision_engine.py
tests/test_action_executor.py
tests/test_supervisor_agent.py
```

**Coverage Target**: >85%

#### 4.2 Integration Tests

**Scenarios**:
1. Reverse engineering workflow with stuck analyzer
2. Dev team with load imbalance
3. Research network with deadlock
4. Long-running task with multiple failures

**File**: `tests/integration/test_supervised_workflows.py`

#### 4.3 Performance Testing

**Benchmarks**:
- Baseline: 50 instances without supervision
- Supervised: 40 instances with supervision
- Measure: CPU, memory, latency overhead

**File**: `tests/performance/test_supervision_overhead.py`

#### 4.4 Documentation

**Files to Create**:
```
docs/SUPERVISION_GUIDE.md       # User guide
docs/SUPERVISION_API.md         # API reference
docs/SUPERVISION_TUNING.md      # Configuration tuning
examples/supervised_reverse_engineering.py
examples/supervised_dev_team.py
```

### Deliverables Phase 4
- ✅ >85% test coverage
- ✅ All integration tests passing
- ✅ Performance benchmarks documented
- ✅ Complete documentation
- ✅ 3 example workflows

---

## Implementation Approaches

### 1. Transcript Analysis (PRIMARY APPROACH - Implemented in Phase 1)

**Status**: Core feature, not optional

Mine instance conversations and terminal output for progress signals instead of requiring explicit instrumentation:

```python
def extract_progress_signals(instance_output: str) -> list[ProgressSignal]:
    """Extract progress signals from natural language output."""

    signals = []

    # Pattern: "Completed X"
    if re.search(r"(completed|finished|done with)", instance_output, re.I):
        signals.append(ProgressSignal(type="completion", confidence=0.9))

    # Pattern: "Working on X"
    if re.search(r"(working on|analyzing|processing)", instance_output, re.I):
        signals.append(ProgressSignal(type="active", confidence=0.8))

    # Pattern: "Blocked by X"
    if re.search(r"(blocked|waiting for|stuck on)", instance_output, re.I):
        signals.append(ProgressSignal(type="blocked", confidence=0.85))

    # Pattern: Error messages
    if re.search(r"(error|failed|exception)", instance_output, re.I):
        signals.append(ProgressSignal(type="error", confidence=0.95))

    return signals
```

### 2. Predictive Stuck Detection

Use historical data to predict when an instance will get stuck:

```python
class PredictiveStuckDetector:
    """Predict stuck instances before they fully stall."""

    def __init__(self):
        self.history: dict[str, list[ProgressSample]] = {}

    def predict_stuck_probability(self, instance_id: str) -> float:
        """Predict likelihood instance will get stuck in next 5min."""

        samples = self.history.get(instance_id, [])
        if len(samples) < 10:
            return 0.0  # Not enough data

        # Calculate progress velocity (checkpoints per minute)
        recent_velocity = self._calculate_velocity(samples[-10:])
        baseline_velocity = self._calculate_velocity(samples)

        # If velocity dropped >70%, high stuck probability
        if recent_velocity < baseline_velocity * 0.3:
            return 0.85

        # If velocity dropped >50%, medium stuck probability
        if recent_velocity < baseline_velocity * 0.5:
            return 0.6

        return 0.1  # Low probability
```

### 3. Peer Instance Consultation

Supervisor consults other instances before intervening:

```python
async def consult_peer_instances(
    self,
    stuck_instance_id: str,
    issue_description: str
) -> list[PeerRecommendation]:
    """Ask peer instances for advice on resolving issue."""

    # Find similar role instances
    peer_instances = self._find_similar_instances(stuck_instance_id)

    recommendations = []

    for peer_id in peer_instances[:3]:  # Consult top 3 peers
        response = await self.manager.send_to_instance(
            peer_id,
            f"Instance {stuck_instance_id} is experiencing: {issue_description}. "
            f"Based on your experience, what would you recommend?"
        )

        recommendations.append(
            PeerRecommendation(
                peer_id=peer_id,
                recommendation=response,
                confidence=self._assess_peer_expertise(peer_id)
            )
        )

    return recommendations
```

### 4. Adaptive Threshold Learning

Learn optimal thresholds from network behavior:

```python
class AdaptiveThresholdLearner:
    """Learn optimal detection thresholds over time."""

    def __init__(self):
        self.intervention_outcomes: list[InterventionOutcome] = []

    def learn_optimal_threshold(self, metric: str) -> float:
        """Learn optimal threshold for a metric."""

        # Analyze past interventions
        successful = [
            o for o in self.intervention_outcomes
            if o.metric == metric and o.success
        ]
        false_positives = [
            o for o in self.intervention_outcomes
            if o.metric == metric and not o.success
        ]

        if not successful:
            return DEFAULT_THRESHOLDS[metric]

        # Find threshold that maximizes true positives, minimizes false positives
        successful_values = [o.threshold_value for o in successful]
        fp_values = [o.threshold_value for o in false_positives]

        # Simple heuristic: median of successful values
        optimal = statistics.median(successful_values)

        logger.info(f"Learned optimal threshold for {metric}: {optimal}")
        return optimal
```

### 5. Network Health Score

Single metric for overall network health:

```python
def calculate_network_health_score(network: NetworkState) -> float:
    """Calculate overall network health score (0.0 - 1.0)."""

    scores = []

    # 1. Instance Health (40% weight)
    healthy_count = sum(
        1 for i in network.instances.values()
        if i.progress_state == ProgressState.HEALTHY
    )
    instance_health = healthy_count / len(network.instances)
    scores.append((instance_health, 0.4))

    # 2. Progress Rate (30% weight)
    total_checkpoints = sum(
        len(m.checkpoints) for m in network.progress_metrics.values()
    )
    time_running = (datetime.now(UTC) - network.start_time).total_seconds() / 3600
    progress_rate = total_checkpoints / time_running / len(network.instances)
    # Normalize to 0-1 (assume 4 checkpoints/hour/instance is perfect)
    progress_score = min(progress_rate / 4.0, 1.0)
    scores.append((progress_score, 0.3))

    # 3. Error Rate (20% weight)
    total_errors = sum(m.error_count for m in network.progress_metrics.values())
    error_rate = total_errors / total_checkpoints if total_checkpoints > 0 else 0
    error_score = 1.0 - min(error_rate / 0.1, 1.0)  # <10% errors is perfect
    scores.append((error_score, 0.2))

    # 4. Utilization (10% weight)
    total_busy_time = sum(m.busy_time_seconds for m in network.progress_metrics.values())
    total_time = time_running * 3600 * len(network.instances)
    utilization = total_busy_time / total_time
    # Target 70% utilization
    utilization_score = 1.0 - abs(utilization - 0.7) / 0.7
    scores.append((utilization_score, 0.1))

    # Weighted average
    return sum(score * weight for score, weight in scores)
```

### 6. Self-Healing Action History

Track and learn from remediation actions:

```python
class SelfHealingHistory:
    """Track history of self-healing actions."""

    def __init__(self):
        self.actions: list[RemediationAction] = []

    def record_action(
        self,
        instance_id: str,
        issue_type: str,
        action_taken: str,
        success: bool,
        time_to_resolve: float
    ):
        """Record a remediation action."""
        self.actions.append(
            RemediationAction(
                timestamp=datetime.now(UTC),
                instance_id=instance_id,
                issue_type=issue_type,
                action_taken=action_taken,
                success=success,
                time_to_resolve=time_to_resolve
            )
        )

    def get_best_action_for_issue(self, issue_type: str) -> str:
        """Get most effective action for an issue type."""
        relevant_actions = [
            a for a in self.actions
            if a.issue_type == issue_type and a.success
        ]

        if not relevant_actions:
            return "default_action"

        # Find action with best success rate and fastest resolution
        action_stats = {}
        for action in relevant_actions:
            if action.action_taken not in action_stats:
                action_stats[action.action_taken] = {
                    "count": 0,
                    "successes": 0,
                    "avg_time": 0
                }

            stats = action_stats[action.action_taken]
            stats["count"] += 1
            stats["successes"] += 1 if action.success else 0
            stats["avg_time"] += action.time_to_resolve

        # Rank by success rate, then by speed
        best_action = max(
            action_stats.items(),
            key=lambda x: (
                x[1]["successes"] / x[1]["count"],
                -x[1]["avg_time"] / x[1]["count"]
            )
        )[0]

        return best_action
```

---

## Risk Mitigation

### Risk 1: Supervisor Itself Gets Stuck
**Mitigation**: Meta-supervisor watches the supervisor (recursive supervision)

### Risk 2: False Positive Interventions
**Mitigation**: Confidence thresholds, intervention cooldowns, learning from outcomes

### Risk 3: Overhead Too High
**Mitigation**: Lazy evaluation, event batching, sampling strategies

### Risk 4: Supervisor Makes Wrong Decisions
**Mitigation**: Human-in-the-loop mode, decision review queue, undo capability

---

## Success Criteria

- ✅ Autonomous detection of stuck instances <2 minutes
- ✅ Autonomous resolution rate >70%
- ✅ False positive rate <5%
- ✅ Supervision overhead <25% CPU/memory
- ✅ Works with 40+ instance networks
- ✅ Zero user intervention in 70% of issues

---

## Next Steps

1. Review design with team
2. Begin Phase 1 implementation in supervision worktree
3. Set up CI/CD for supervision branch
4. Create tracking issues for each phase
5. Schedule weekly progress reviews
