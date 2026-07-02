import type { NamedTimeInterval } from "@shared/types";
export type TimeIntervalsValidation = {
    valid: boolean;
    global: string[];
    intervals: Record<number, string>;
};
export declare function validateTimeIntervals(intervals: NamedTimeInterval[]): TimeIntervalsValidation;
