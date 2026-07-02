import { Module } from '@nestjs/common';
import { InternalController } from './internal.controller';
import { AgentsModule } from '../agents/agents.module';

@Module({
  imports: [AgentsModule],
  controllers: [InternalController],
})
export class InternalModule {}
