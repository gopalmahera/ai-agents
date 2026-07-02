import { Module } from '@nestjs/common';
import { InvestigateProcessor } from './investigate.processor';
import { AgentsModule } from '../agents/agents.module';

@Module({
  imports: [AgentsModule],
  providers: [InvestigateProcessor],
})
export class JobsModule {}
