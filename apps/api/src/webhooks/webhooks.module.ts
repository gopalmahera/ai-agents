import { Module } from '@nestjs/common';
import { BullModule } from '@nestjs/bullmq';
import { WebhooksController } from './webhooks.controller';
import { WebhooksService } from './webhooks.service';
import { INVESTIGATE_QUEUE } from '../jobs/investigate.constants';

@Module({
  imports: [
    BullModule.registerQueue({
      name: INVESTIGATE_QUEUE,
    }),
  ],
  controllers: [WebhooksController],
  providers: [WebhooksService],
})
export class WebhooksModule {}
