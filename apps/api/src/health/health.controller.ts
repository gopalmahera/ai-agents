import { Controller, Get } from '@nestjs/common';
import { mongoHealth } from '../lib/mongo';
import { redisHealth } from '../lib/redis';
import { AgentsRegistry } from '../agents/agents.registry';
import { AgentsGateway } from '../agents/agents.gateway';

@Controller('api/v1/health')
export class HealthController {
  constructor(
    private readonly registry: AgentsRegistry,
    private readonly agents: AgentsGateway,
  ) {}

  @Get()
  async health() {
    const [mongo, redis] = await Promise.all([mongoHealth(), redisHealth()]);
    return { status: 'ok', mongo, redis, agents_online: this.registry.listOnline().length };
  }

  @Get('mcp')
  mcpHealth() {
    return this.agents.getMcpHealthAggregate();
  }
}
