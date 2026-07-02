import { Injectable } from '@nestjs/common';
import Redis from 'ioredis';
import { ConfigService } from '@nestjs/config';

export type AgentPresence = {
  agentId: string;
  socketId: string;
  version?: string;
  capabilities?: string[];
  mcpHealth?: Record<string, unknown>;
  connectedAt: string;
};

@Injectable()
export class AgentsRegistry {
  private readonly redis: Redis;
  private readonly local = new Map<string, AgentPresence>();

  constructor(config: ConfigService) {
    const url = config.get<string>('REDIS_URL') || 'redis://localhost:6379/0';
    this.redis = new Redis(url, { maxRetriesPerRequest: 1 });
  }

  async register(presence: AgentPresence): Promise<void> {
    this.local.set(presence.agentId, presence);
    await this.redis.set(
      `agent:online:${presence.agentId}`,
      JSON.stringify(presence),
      'EX',
      120,
    );
  }

  async unregister(agentId: string): Promise<void> {
    this.local.delete(agentId);
    await this.redis.del(`agent:online:${agentId}`);
  }

  async heartbeat(agentId: string): Promise<void> {
    await this.redis.expire(`agent:online:${agentId}`, 120);
  }

  listOnline(): AgentPresence[] {
    return [...this.local.values()];
  }

  get(agentId: string): AgentPresence | undefined {
    return this.local.get(agentId);
  }

  pickAgent(): AgentPresence | undefined {
    const online = this.listOnline();
    return online[0];
  }
}
