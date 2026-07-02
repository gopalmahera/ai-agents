export const INVESTIGATE_QUEUE = 'investigate';

export type InvestigateJobPayload = {
  jobId: string;
  env: string | null;
  alert: Record<string, unknown>;
  fingerprint: string;
};
