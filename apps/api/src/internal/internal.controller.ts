import { Controller, Get } from '@nestjs/common';
import { getSettingsVersion } from '../lib/settings-store';
import { AgentsGateway } from '../agents/agents.gateway';

@Controller('api/v1/internal')
export class InternalController {
  constructor(private readonly agents: AgentsGateway) {}

  @Get('agent/config')
  async agentConfig() {
    const version = await getSettingsVersion();
    const config = await this.agents.buildConfigSnapshot();
    return { version, config };
  }
}
