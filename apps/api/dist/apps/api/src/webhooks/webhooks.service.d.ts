import { Queue } from 'bullmq';
import { ConfigService } from '@nestjs/config';
import { InvestigateJobPayload } from '../jobs/investigate.constants';
export declare class WebhooksService {
    private readonly investigateQueue;
    private readonly redis;
    constructor(investigateQueue: Queue<InvestigateJobPayload>, config: ConfigService);
    private dedupCheckAndSet;
    private counterInc;
    private streamAdd;
    private isAllowedAlertname;
    processWebhook(env: string | null, payload: Record<string, unknown>): Promise<{
        status: string;
        alerts_received: number;
        accepted: number;
    }>;
}
