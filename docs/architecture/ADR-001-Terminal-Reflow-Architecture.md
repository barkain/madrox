# ADR-001: Automatic Terminal Reflow Architecture

**Status**: Proposed
**Date**: 2025-10-27
**Decision Makers**: Technical Lead
**Stakeholders**: Frontend Team, UX Team, Madrox Monitor Users

## Context

The Madrox Monitor UI currently uses @dnd-kit for drag-and-drop terminal positioning but lacks automatic layout adjustment when terminals are resized. Users expect that when a terminal is resized to full-screen width, adjacent terminals should automatically reposition below it to prevent overlap.

### Current State
- Manual drag-and-drop positioning via @dnd-kit
- Fixed grid positions
- No automatic reflow on resize
- Terminals can overlap when resized

### Requirements
1. Detect terminal resize events in real-time
2. Calculate optimal grid layout based on terminal dimensions
3. Automatically reposition terminals to prevent overlap
4. Smooth animations during transitions
5. Maintain @dnd-kit compatibility for manual repositioning
6. Handle edge cases (rapid resizing, multiple simultaneous resizes)

## Decision

We will implement a **hybrid grid system** that combines:
1. **Masonry-style layout algorithm** for automatic reflow
2. **Collision detection** to identify overlap scenarios
3. **Position reconciliation** between manual (drag) and automatic (resize) adjustments
4. **CSS Grid + Framer Motion** for smooth animations

## Architecture Components

### 1. Terminal Grid Manager (`TerminalGridManager.ts`)
**Responsibilities**:
- Track terminal positions and dimensions
- Calculate grid layout based on container width
- Detect collisions and overlaps
- Trigger reflow operations

```typescript
interface TerminalPosition {
  id: string;
  x: number;      // Grid column
  y: number;      // Grid row
  width: number;  // Columns span
  height: number; // Rows span
}

class TerminalGridManager {
  private terminals: Map<string, TerminalPosition>;
  private containerWidth: number;
  private columnCount: number;
  private gutterSize: number;

  calculateReflow(resizedTerminalId: string, newWidth: number): TerminalPosition[] {
    // Reflow algorithm implementation
  }

  detectCollisions(): CollisionSet[] {
    // Collision detection
  }
}
```

### 2. Resize Observer Hook (`useTerminalResize.ts`)
**Responsibilities**:
- Monitor terminal dimension changes
- Debounce resize events
- Trigger reflow calculations

```typescript
export function useTerminalResize(
  terminalRef: RefObject<HTMLElement>,
  onResize: (dimensions: Dimensions) => void,
  debounceMs = 150
) {
  // ResizeObserver implementation with debouncing
}
```

### 3. Layout Reconciliation Service (`LayoutReconciler.ts`)
**Responsibilities**:
- Merge manual drag positions with automatic reflow
- Resolve conflicts between user intent and automatic layout
- Maintain layout history for undo/redo

```typescript
class LayoutReconciler {
  reconcilePositions(
    manualPositions: Map<string, Position>,
    calculatedPositions: Map<string, Position>,
    priority: 'manual' | 'automatic'
  ): Map<string, Position> {
    // Reconciliation logic
  }
}
```

### 4. Animation Controller (`TerminalAnimationController.ts`)
**Responsibilities**:
- Orchestrate smooth transitions
- Queue animation sequences
- Handle interruptions (new resize during animation)

```typescript
class TerminalAnimationController {
  animateTransition(
    from: TerminalPosition[],
    to: TerminalPosition[],
    duration: number
  ): Promise<void> {
    // Framer Motion animation orchestration
  }
}
```

## Reflow Algorithm

### Core Logic
```
1. When terminal resizes:
   a. Get new dimensions
   b. Check if new width spans full container width
   c. If yes, move terminal to new row if not already isolated
   d. Push all subsequent terminals down

2. Reflow cascade:
   a. Sort terminals by Y position (top to bottom)
   b. For each terminal:
      - Find leftmost available position in current row
      - If terminal doesn't fit in row, move to next row
      - Update Y position for next terminal

3. Collision resolution:
   a. Build 2D occupancy grid
   b. Mark occupied cells for each terminal
   c. Find overlaps
   d. Shift overlapping terminals to first available position
```

### Pseudo-code
```typescript
function calculateReflow(terminals: Terminal[]): TerminalPosition[] {
  const sorted = sortByPosition(terminals, 'top-to-bottom', 'left-to-right');
  const grid = new OccupancyGrid(containerWidth, maxRows);
  const newPositions: TerminalPosition[] = [];

  for (const terminal of sorted) {
    const position = grid.findNextAvailablePosition(
      terminal.width,
      terminal.height
    );

    grid.markOccupied(position.x, position.y, terminal.width, terminal.height);
    newPositions.push({ ...terminal, ...position });
  }

  return newPositions;
}
```

## Integration with @dnd-kit

### Strategy
1. **Separate concerns**: Drag operations update manual position state, resize operations trigger reflow
2. **Priority system**: Recent manual drag takes precedence over automatic reflow for that terminal
3. **Lock mechanism**: During drag operations, disable automatic reflow
4. **Merge on release**: When drag ends, run reflow to adjust other terminals

```typescript
const onDragEnd = (event: DragEndEvent) => {
  const { active, over } = event;

  // Update manual position
  updateManualPosition(active.id, over.position);

  // Trigger reflow for other terminals (excluding dragged terminal)
  const otherTerminals = terminals.filter(t => t.id !== active.id);
  const reflowedPositions = calculateReflow(otherTerminals);

  // Reconcile
  const finalPositions = reconcilePositions(
    { [active.id]: over.position },
    reflowedPositions,
    'manual'
  );

  animateTransition(currentPositions, finalPositions);
};
```

## Animation Strategy

### Approach: Framer Motion with Spring Physics
```typescript
<motion.div
  layout
  transition={{
    type: "spring",
    stiffness: 300,
    damping: 30,
    mass: 0.8
  }}
  style={{
    gridColumn: `${position.x + 1} / span ${position.width}`,
    gridRow: `${position.y + 1} / span ${position.height}`
  }}
>
  {terminalContent}
</motion.div>
```

### Performance Optimizations
1. **Will-change hints**: Add `will-change: transform` during animations
2. **GPU acceleration**: Use `transform: translate3d()` instead of `top/left`
3. **Animation batching**: Group multiple terminal moves into single animation frame
4. **Interrupt handling**: Cancel in-progress animations when new resize occurs

## Edge Cases

### 1. Rapid Resizing
**Solution**: Debounce resize events (150ms), cancel pending reflow on new resize

### 2. Multiple Simultaneous Resizes
**Solution**: Queue reflow operations, process in order

### 3. Container Resize
**Solution**: Recalculate entire grid layout, adjust column count

### 4. Terminal Deletion During Animation
**Solution**: Abort animation for deleted terminal, continue for others

### 5. Full-Width Terminal in Middle of Grid
**Solution**: Move terminal to new row, push all terminals below it down

## Data Flow

```
User resizes terminal
  → ResizeObserver detects change
  → Debounce (150ms)
  → TerminalGridManager.calculateReflow()
  → LayoutReconciler.reconcilePositions()
  → TerminalAnimationController.animateTransition()
  → Update React state
  → Render new positions with Framer Motion
```

## Performance Considerations

### Metrics
- **Reflow calculation**: < 16ms (60 FPS)
- **Animation duration**: 300-500ms (smooth but not sluggish)
- **Debounce delay**: 150ms (balance responsiveness vs. CPU)

### Optimizations
1. **Memoization**: Cache reflow calculations for identical inputs
2. **Virtual grid**: Only calculate positions for visible terminals
3. **Web Workers**: Offload heavy calculations to background thread
4. **RequestAnimationFrame**: Batch DOM updates

## Testing Strategy

### Unit Tests
- Reflow algorithm correctness
- Collision detection accuracy
- Position reconciliation logic

### Integration Tests
- @dnd-kit compatibility
- Animation sequencing
- State management

### E2E Tests
- User resizes terminal to full width
- Multiple terminals reflow correctly
- Drag-and-drop still works
- Performance under load (20+ terminals)

## Rollout Plan

### Phase 1: Core Algorithm (Week 1)
- Implement TerminalGridManager
- Implement reflow algorithm
- Unit tests

### Phase 2: React Integration (Week 2)
- Create hooks (useTerminalResize, useGridLayout)
- Integrate with existing component
- Integration tests

### Phase 3: Animation (Week 3)
- Implement TerminalAnimationController
- Add Framer Motion transitions
- Polish and optimize

### Phase 4: @dnd-kit Integration (Week 4)
- Implement LayoutReconciler
- Test drag + reflow interactions
- Edge case handling

### Phase 5: Polish & Ship (Week 5)
- Performance optimizations
- E2E tests
- Documentation
- Release

## Alternatives Considered

### Alternative 1: CSS Grid Auto-Flow
**Pros**: Simple, native browser support
**Cons**: Limited control over position, hard to integrate with @dnd-kit
**Decision**: Rejected - insufficient control

### Alternative 2: React-Grid-Layout
**Pros**: Battle-tested library, built-in features
**Cons**: Large bundle size, opinionated API, potential conflicts with @dnd-kit
**Decision**: Rejected - too heavyweight

### Alternative 3: Custom Flexbox Layout
**Pros**: Flexible, good browser support
**Cons**: Difficult to achieve masonry-style layout, reflow logic complex
**Decision**: Rejected - CSS Grid is better suited

## Consequences

### Positive
- Users get intuitive terminal management
- Prevents overlap issues
- Smooth, polished UX
- Maintains drag-and-drop flexibility

### Negative
- Increased code complexity
- Performance overhead (mitigated by optimizations)
- Potential for animation jank on low-end devices
- Learning curve for maintaining reflow logic

## Success Metrics

1. **Functional**: 100% of resize scenarios result in no overlaps
2. **Performance**: Reflow calculation < 16ms for up to 50 terminals
3. **UX**: User testing shows 90%+ satisfaction with behavior
4. **Stability**: < 1% bug rate in production after 1 month

## References

- [CSS Grid Layout Spec](https://www.w3.org/TR/css-grid-1/)
- [@dnd-kit Documentation](https://docs.dndkit.com/)
- [Framer Motion Layout Animations](https://www.framer.com/motion/layout-animations/)
- [ResizeObserver API](https://developer.mozilla.org/en-US/docs/Web/API/ResizeObserver)
