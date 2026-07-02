import type { EndpointsConfig, EndpointType } from "@shared/types";
export declare const ENDPOINT_TYPES: {
    value: EndpointType;
    label: string;
}[];
export type EditableEndpoint = {
    id: string;
    name: string;
    type: EndpointType;
    url: string;
    http_auth_mode: string;
    username: string;
    password: string;
    bearer_token: string;
    kube_context: string;
    api_server: string;
    kube_token: string;
    ca_cert: string;
    region: string;
    aws_auth_mode: string;
    role_arn: string;
    access_key_id: string;
    secret_access_key: string;
};
export declare function blankEndpoint(type: EndpointType, id: string): EditableEndpoint;
export declare function toEndpointsConfig(eps: EditableEndpoint[]): EndpointsConfig;
export declare function fromEndpointsConfig(cfg: EndpointsConfig | undefined): EditableEndpoint[];
export type EndpointValidation = {
    valid: boolean;
    eps: Record<string, string>;
};
export declare function validateEndpoints(eps: EditableEndpoint[]): EndpointValidation;
export declare function endpointsByType(eps: EditableEndpoint[]): Record<string, string>;
