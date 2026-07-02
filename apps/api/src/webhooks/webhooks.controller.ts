import { Body, Controller, Param, Post } from '@nestjs/common';
import { WebhooksService } from './webhooks.service';

@Controller('api/v1/webhook')
export class WebhooksController {
  constructor(private readonly webhooks: WebhooksService) {}

  @Post()
  async webhook(@Body() body: Record<string, unknown>) {
    return this.webhooks.processWebhook(null, body);
  }

  @Post(':env')
  async webhookEnv(@Param('env') env: string, @Body() body: Record<string, unknown>) {
    if (env === 'test') {
      return { status: 'error', message: 'Use authenticated test endpoint' };
    }
    return this.webhooks.processWebhook(env, body);
  }
}
