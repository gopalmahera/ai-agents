import { AgentsGateway } from '../agents/agents.gateway';
export declare class InternalController {
    private readonly agents;
    constructor(agents: AgentsGateway);
    agentConfig(): Promise<{
        version: number;
        config: Record<string, unknown>;
    }>;
}
