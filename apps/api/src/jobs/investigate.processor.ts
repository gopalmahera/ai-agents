import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { Job } from 'bullmq';
import { AgentsGateway } from '../agents/agents.gateway';
import { INVESTIGATE_QUEUE, InvestigateJobPayload } from './investigate.constants';

@Processor(INVESTIGATE_QUEUE)
export class InvestigateProcessor extends WorkerHost {
  private readonly logger = new Logger(InvestigateProcessor.name);

  constructor(private readonly agents: AgentsGateway) {
    super();
  }

  async process(job: Job<InvestigateJobPayload>): Promise<Record<string, unknown>> {
    this.logger.log(`Processing investigate job ${job.data.jobId}`);
    const result = await this.agents.dispatchInvestigate(job.data);
    this.logger.log(`Job ${job.data.jobId} completed`);
    return result;
  }
}
