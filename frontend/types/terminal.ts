/**
 * Terminal Grid Type Definitions
 * Defines core interfaces for the terminal reflow system
 */

export interface TerminalDimensions {
  width: number;
  height: number;
}

export interface GridPosition {
  x: number; // Column index (0-based)
  y: number; // Row index (0-based)
}

export interface TerminalPosition extends GridPosition {
  id: string;
  width: number;  // Number of columns spanned
  height: number; // Number of rows spanned
}

export interface Terminal {
  id: string;
  title: string;
  content: React.ReactNode;
  position: TerminalPosition;
  pixelDimensions?: TerminalDimensions; // Actual pixel size
  isResizing?: boolean;
  isDragging?: boolean;
}

export interface GridConfig {
  containerWidth: number;
  columnCount: number;
  columnWidth: number;
  rowHeight: number;
  gutterSize: number;
}

export interface CollisionInfo {
  terminal1: string; // Terminal ID
  terminal2: string; // Terminal ID
  overlapArea: number;
}

export interface ReflowResult {
  positions: TerminalPosition[];
  collisions: CollisionInfo[];
  hasChanges: boolean;
}

export interface AnimationConfig {
  duration: number;
  stiffness: number;
  damping: number;
  mass: number;
}

export interface LayoutConstraints {
  minTerminalWidth: number;
  minTerminalHeight: number;
  maxTerminalWidth: number;
  maxTerminalHeight: number;
  snapToGrid: boolean;
}

export type ResizeDirection =
  | 'n' | 's' | 'e' | 'w'
  | 'ne' | 'nw' | 'se' | 'sw';

export interface ResizeEvent {
  terminalId: string;
  oldDimensions: TerminalDimensions;
  newDimensions: TerminalDimensions;
  direction: ResizeDirection;
  timestamp: number;
}

export interface DragEvent {
  terminalId: string;
  oldPosition: GridPosition;
  newPosition: GridPosition;
  timestamp: number;
}

export type LayoutEvent = ResizeEvent | DragEvent;

export interface LayoutHistory {
  past: TerminalPosition[][];
  present: TerminalPosition[];
  future: TerminalPosition[][];
}

export interface OccupancyCell {
  occupied: boolean;
  terminalId: string | null;
}

export type OccupancyGrid = OccupancyCell[][];
