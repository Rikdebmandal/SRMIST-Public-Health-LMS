import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(value?: string | Date | null, withTime = false): string {
  if (!value) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  const options: Intl.DateTimeFormatOptions = {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    ...(withTime ? { hour: '2-digit', minute: '2-digit' } : {}),
  };
  return new Intl.DateTimeFormat('en-IN', options).format(date);
}

export function relativeTime(value?: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  const diffMs = date.getTime() - Date.now();
  const diffDays = Math.round(diffMs / 86_400_000);
  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  if (Math.abs(diffDays) >= 1) return formatter.format(diffDays, 'day');
  const diffHours = Math.round(diffMs / 3_600_000);
  if (Math.abs(diffHours) >= 1) return formatter.format(diffHours, 'hour');
  return formatter.format(Math.round(diffMs / 60_000), 'minute');
}

export function percent(value?: number | null, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(digits)}%`;
}

const HONORIFICS = new Set(['dr', 'dr.', 'prof', 'prof.', 'mr', 'mr.', 'ms', 'ms.', 'mrs', 'mrs.']);

/** First name for greetings, skipping an honorific like "Dr." */
export function firstName(name?: string): string {
  const parts = (name ?? '').split(' ').filter(Boolean);
  const meaningful = parts.filter((part) => !HONORIFICS.has(part.toLowerCase()));
  return meaningful[0] ?? parts[0] ?? '';
}

export function initials(name?: string): string {
  if (!name) return '?';
  const parts = name.split(' ').filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/** Colour token for an attendance / risk status. */
export function statusTone(status?: string): 'success' | 'warning' | 'danger' | 'muted' {
  switch (status) {
    case 'ok':
    case 'low':
    case 'PUBLISHED':
    case 'ACTIVE':
    case 'GRADED':
    case 'ACCEPTED':
      return 'success';
    case 'warning':
    case 'moderate':
    case 'IMPORTANT':
    case 'SUBMITTED':
    case 'PENDING':
      return 'warning';
    case 'critical':
    case 'high':
    case 'URGENT':
    case 'LATE':
    case 'DECLINED':
      return 'danger';
    default:
      return 'muted';
  }
}

export function truncate(text: string, length = 120): string {
  if (!text) return '';
  return text.length > length ? `${text.slice(0, length).trimEnd()}…` : text;
}

export function fileSize(bytes?: number): string {
  if (!bytes) return '—';
  const units = ['B', 'KB', 'MB', 'GB'];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(1)} ${units[unit]}`;
}
