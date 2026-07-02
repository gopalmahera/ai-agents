import { AgentsRegistry } from '../agents/agents.registry';
import { AgentsGateway } from '../agents/agents.gateway';
export declare class HealthController {
    private readonly registry;
    private readonly agents;
    constructor(registry: AgentsRegistry, agents: AgentsGateway);
    health(): Promise<{
        status: string;
        mongo: boolean;
        redis: boolean;
        agents_online: number;
    }>;
    mcpHealth(): Record<string, unknown>;
}
