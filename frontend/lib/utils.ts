import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Format uptime from seconds to human-readable string
export function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 24) {
    const days = Math.floor(hours / 24);
    return `${days}d ${hours % 24}h`;
  }

  return `${hours}h ${minutes}m`;
}

// Format timestamp to relative time
export function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (diffInSeconds < 60) {
    return `${diffInSeconds}s ago`;
  }

  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes}m ago`;
  }

  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours}h ago`;
  }

  const diffInDays = Math.floor(diffInHours / 24);
  return `${diffInDays}d ago`;
}

// Format number with change indicator
export function formatChange(change: number): string {
  const sign = change >= 0 ? '+' : '';
  return `${sign}${change}`;
}

// Get status color classes
export function getStatusColor(status: 'healthy' | 'warning' | 'critical'): string {
  switch (status) {
    case 'healthy':
      return 'text-green-600 bg-green-50 dark:bg-green-950 dark:text-green-400';
    case 'warning':
      return 'text-yellow-600 bg-yellow-50 dark:bg-yellow-950 dark:text-yellow-400';
    case 'critical':
      return 'text-red-600 bg-red-50 dark:bg-red-950 dark:text-red-400';
  }
}

// Get status icon
export function getStatusIcon(status: 'healthy' | 'warning' | 'critical'): string {
  switch (status) {
    case 'healthy':
      return '●';
    case 'warning':
      return '⚠';
    case 'critical':
      return '✗';
  }
}

// Get severity emoji
export function getSeverityEmoji(severity: 'critical' | 'warning' | 'info'): string {
  switch (severity) {
    case 'critical':
      return '🔴';
    case 'warning':
      return '🟡';
    case 'info':
      return '🔵';
  }
}

// Format bytes to human-readable
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';

  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
}

// Format milliseconds to readable time
export function formatMilliseconds(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}
