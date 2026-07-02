import type { SilenceRule } from '@shared/types';
export declare function isSilenced(labels: Record<string, string>, activeRules: SilenceRule[]): {
    silenced: boolean;
    silenceId?: string;
};
