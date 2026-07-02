import { WorkerHost } from '@nestjs/bullmq';
import { Job } from 'bullmq';
import { AgentsGateway } from '../agents/agents.gateway';
import { InvestigateJobPayload } from './investigate.constants';
export declare class InvestigateProcessor extends WorkerHost {
    private readonly agents;
    private readonly logger;
    constructor(agents: AgentsGateway);
    process(job: Job<InvestigateJobPayload>): Promise<Record<string, unknown>>;
}
