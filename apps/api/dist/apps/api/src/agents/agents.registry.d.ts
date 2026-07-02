import { ConfigService } from '@nestjs/config';
export type AgentPresence = {
    agentId: string;
    socketId: string;
    version?: string;
    capabilities?: string[];
    mcpHealth?: Record<string, unknown>;
    connectedAt: string;
};
export declare class AgentsRegistry {
    private readonly redis;
    private readonly local;
    constructor(config: ConfigService);
    register(presence: AgentPresence): Promise<void>;
    unregister(agentId: string): Promise<void>;
    heartbeat(agentId: string): Promise<void>;
    listOnline(): AgentPresence[];
    get(agentId: string): AgentPresence | undefined;
    pickAgent(): AgentPresence | undefined;
}
