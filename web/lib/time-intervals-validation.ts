import type { NamedTimeInterval } from "@/lib/types";

const WEEKDAYS = new Set([
  "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
]);

function isValidTime(value: string): boolean {
  const parts = value.trim().split(":");
  if (parts.length !== 2) return false;
  const h = Number(parts[0]);
  const m = Number(parts[1]);
  return Number.isInteger(h) && Number.isInteger(m) && h >= 0 && h <= 23 && m >= 0 && m <= 59;
}

export type TimeIntervalsValidation = {
  valid: boolean;
  global: string[];
  intervals: Record<number, string>;
};

export function validateTimeIntervals(intervals: NamedTimeInterval[]): TimeIntervalsValidation {
  const result: TimeIntervalsValidation = { valid: true, global: [], intervals: {} };
  const names = new Set<string>();

  intervals.forEach((entry, index) => {
    const name = entry.name.trim();
    if (!name) {
      result.valid = false;
      result.intervals[index] = "Name is required.";
      return;
    }
    if (names.has(name)) {
      result.valid = false;
      result.intervals[index] = "Duplicate interval name.";
      return;
    }
    names.add(name);

    const subs = entry.time_intervals ?? [];
    if (!subs.length) {
      result.valid = false;
      result.intervals[index] = "Add at least one sub-interval.";
      return;
    }
    for (const sub of subs) {
      const times = sub.times ?? [];
      if (!times.length) {
        result.valid = false;
        result.intervals[index] = "Each sub-interval needs a time range.";
        break;
      }
      for (const slot of times) {
        if (!isValidTime(slot.start_time) || !isValidTime(slot.end_time)) {
          result.valid = false;
          result.intervals[index] = "Times must be HH:MM.";
          break;
        }
      }
      for (const day of sub.weekdays ?? []) {
        if (!WEEKDAYS.has(day.toLowerCase())) {
          result.valid = false;
          result.intervals[index] = `Invalid weekday: ${day}`;
        }
      }
    }
  });

  return result;
}
