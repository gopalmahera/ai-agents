import { Module, forwardRef } from '@nestjs/common';
import { AgentsGateway } from './agents.gateway';
import { AgentsRegistry } from './agents.registry';

@Module({
  providers: [AgentsGateway, AgentsRegistry],
  exports: [AgentsGateway, AgentsRegistry],
})
export class AgentsModule {}
