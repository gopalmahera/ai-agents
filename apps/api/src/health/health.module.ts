import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
import { AgentsModule } from '../agents/agents.module';

@Module({
  imports: [AgentsModule],
  controllers: [HealthController],
})
export class HealthModule {}
