import type { EnvironmentsConfig } from "@shared/types";
export type EditableEnv = {
    id: string;
    name: string;
    prometheus: string;
    loki: string;
    kubernetes: string;
    aws: string;
};
export declare function toEnvConfig(envs: EditableEnv[]): EnvironmentsConfig;
export declare function fromEnvConfig(cfg: EnvironmentsConfig | undefined): EditableEnv[];
export type EnvValidation = {
    valid: boolean;
    envs: Record<string, string>;
};
export declare function validateEnvironments(envs: EditableEnv[], endpointsByType: Record<string, string>): EnvValidation;
