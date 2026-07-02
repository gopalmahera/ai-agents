import { AgentsGateway } from '../agents/agents.gateway';
export declare class SettingsController {
    private readonly agents;
    constructor(agents: AgentsGateway);
    private notifyConfig;
    getAgent(): Promise<Record<string, unknown>>;
    putAgent(body: Record<string, unknown>): Promise<Record<string, unknown>>;
    getEndpoints(q?: string, type?: string): Promise<import("@shared/types").Endpoint[]>;
    postEndpoint(body: Record<string, unknown>): Promise<import("@shared/types").Endpoint>;
    getEndpointByName(name: string): Promise<import("@shared/types").Endpoint>;
    putEndpointByName(name: string, body: Record<string, unknown>): Promise<import("@shared/types").Endpoint>;
    deleteEndpointByName(name: string): Promise<{
        ok: boolean;
    }>;
    getEnvironments(q?: string): Promise<import("@shared/types").Environment[]>;
    postEnvironment(body: Record<string, unknown>): Promise<import("@shared/types").Environment>;
    getEnvironmentByName(name: string): Promise<import("@shared/types").Environment>;
    putEnvironmentByName(name: string, body: Record<string, unknown>): Promise<import("@shared/types").Environment>;
    deleteEnvironmentByName(name: string): Promise<{
        ok: boolean;
    }>;
    getRouting(): Promise<import("@shared/types").RoutingConfig>;
    putRoutingMeta(body: {
        default_slack_webhook_url?: string;
    }): Promise<{
        ok: boolean;
    }>;
    getRoutingRules(): Promise<import("../lib/settings-store").RoutingRuleDoc[]>;
    postRoutingRule(body: Record<string, unknown>): Promise<import("../lib/settings-store").RoutingRuleDoc>;
    putRoutingRuleById(id: string, body: Record<string, unknown>): Promise<import("../lib/settings-store").RoutingRuleDoc>;
    deleteRoutingRuleById(id: string): Promise<{
        ok: boolean;
    }>;
    reorderRouting(body: {
        ids: string[];
    }): Promise<{
        ok: boolean;
    }>;
    getTimeIntervals(): Promise<import("@shared/types").TimeIntervalsConfig>;
    postTimeInterval(body: Record<string, unknown>): Promise<import("../lib/settings-store").TimeIntervalDoc>;
    putTimeIntervalByName(name: string, body: Record<string, unknown>): Promise<import("../lib/settings-store").TimeIntervalDoc>;
    deleteTimeIntervalByName(name: string): Promise<{
        ok: boolean;
    }>;
    reorderTimeIntervalsRoute(body: {
        names: string[];
    }): Promise<{
        ok: boolean;
    }>;
    getSilences(status?: 'active' | 'disabled'): Promise<import("@shared/types").SilenceRule[]>;
    postSilence(body: Record<string, unknown>): Promise<import("@shared/types").SilenceRule>;
    putSilenceById(id: string, body: Record<string, unknown>): Promise<import("@shared/types").SilenceRule>;
    deleteSilenceById(id: string): Promise<{
        ok: boolean;
    }>;
    disableSilenceById(id: string): Promise<{
        ok: boolean;
    }>;
    enableSilenceById(id: string, body: Record<string, unknown>): Promise<{
        ok: boolean;
    }>;
}
