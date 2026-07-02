import { OnGatewayConnection, OnGatewayDisconnect } from '@nestjs/websockets';
import { Server, Socket } from 'socket.io';
import { AgentsRegistry } from './agents.registry';
import { InvestigateJobPayload } from '../jobs/investigate.constants';
export declare class AgentsGateway implements OnGatewayConnection, OnGatewayDisconnect {
    private readonly registry;
    private readonly logger;
    private readonly pending;
    server: Server;
    constructor(registry: AgentsRegistry);
    handleConnection(client: Socket): Promise<void>;
    handleDisconnect(client: Socket): Promise<void>;
    onRegister(client: Socket, body: {
        agentId: string;
        version?: string;
        capabilities?: string[];
        mcpHealth?: Record<string, unknown>;
    }): Promise<{
        ok: boolean;
        error: string;
        configVersion?: undefined;
        config?: undefined;
    } | {
        ok: boolean;
        configVersion: number;
        config: Record<string, unknown>;
        error?: undefined;
    }>;
    onHealthPing(client: Socket, body: {
        agentId?: string;
        mcpHealth?: Record<string, unknown>;
    }): Promise<{
        ok: boolean;
    }>;
    onJobResult(body: {
        jobId: string;
        result: Record<string, unknown>;
    }): Promise<{
        ok: boolean;
    }>;
    broadcastConfigUpdated(): Promise<void>;
    buildConfigSnapshot(): Promise<Record<string, unknown>>;
    dispatchInvestigate(job: InvestigateJobPayload, timeoutMs?: number): Promise<Record<string, unknown>>;
    getMcpHealthAggregate(): Record<string, unknown>;
}
