import type { Endpoint, EndpointsConfig } from "@shared/types";
export declare const MASK = "***";
export declare function maskEndpoint(ep: Endpoint): Endpoint;
export declare function maskEndpoints(config: EndpointsConfig): EndpointsConfig;
export declare function mergeEndpointSecrets(incoming: Endpoint, stored?: Endpoint | null): Endpoint;
export declare const AGENT_SENSITIVE_KEYS: Set<string>;
export declare function maskAgentSettings(values: Record<string, unknown>): Record<string, unknown>;
export declare function mergeAgentSecrets(incoming: Record<string, unknown>, stored: Record<string, unknown>): Record<string, unknown>;
