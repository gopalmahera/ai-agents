import { WebhooksService } from './webhooks.service';
export declare class WebhooksController {
    private readonly webhooks;
    constructor(webhooks: WebhooksService);
    webhook(body: Record<string, unknown>): Promise<{
        status: string;
        alerts_received: number;
        accepted: number;
    }>;
    webhookEnv(env: string, body: Record<string, unknown>): Promise<{
        status: string;
        alerts_received: number;
        accepted: number;
    } | {
        status: string;
        message: string;
    }>;
}
