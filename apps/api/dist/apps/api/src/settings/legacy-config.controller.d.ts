import { AgentsGateway } from '../agents/agents.gateway';
export declare class LegacyConfigController {
    private readonly agents;
    constructor(agents: AgentsGateway);
    private notify;
    getConfig(): Promise<Record<string, unknown>>;
    putConfig(body: Record<string, unknown>): Promise<Record<string, unknown>>;
    getEndpoints(): Promise<{
        endpoints: import("@shared/types").Endpoint[];
    }>;
    putEndpoints(body: {
        endpoints: unknown[];
    }): Promise<{
        ok: boolean;
    }>;
    getEnvironments(): Promise<{
        environments: import("@shared/types").Environment[];
    }>;
    putEnvironments(body: {
        environments: unknown[];
    }): Promise<{
        ok: boolean;
    }>;
    getRouting(): Promise<import("@shared/types").RoutingConfig>;
    putRouting(body: Record<string, unknown>): Promise<{
        ok: boolean;
    }>;
    getTimeIntervals(): Promise<import("@shared/types").TimeIntervalsConfig>;
    putTimeIntervals(body: Record<string, unknown>): Promise<{
        ok: boolean;
    }>;
    getMute(): Promise<import("@shared/types").SilencesConfig>;
    putMute(body: Record<string, unknown>): Promise<{
        ok: boolean;
    }>;
    disableSilenceRoute(id: string): Promise<{
        ok: boolean;
    }>;
    enableSilenceRoute(id: string, body: Record<string, unknown>): Promise<{
        ok: boolean;
    }>;
}
