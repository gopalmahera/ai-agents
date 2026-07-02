import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { BullModule } from '@nestjs/bullmq';
import { SettingsModule } from './settings/settings.module';
import { WebhooksModule } from './webhooks/webhooks.module';
import { JobsModule } from './jobs/jobs.module';
import { AgentsModule } from './agents/agents.module';
import { MetricsModule } from './metrics/metrics.module';
import { LogsModule } from './logs/logs.module';
import { HealthModule } from './health/health.module';
import { ReportsModule } from './reports/reports.module';
import { InternalModule } from './internal/internal.module';
import { AuthModule } from './auth/auth.module';
import { BootstrapService } from './bootstrap.service';
import { INVESTIGATE_QUEUE } from './jobs/investigate.constants';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    BullModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (config: ConfigService) => ({
        connection: {
          url: config.get<string>('REDIS_URL') || 'redis://localhost:6379/0',
        },
        prefix: config.get<string>('BULLMQ_PREFIX') || 'dai',
      }),
      inject: [ConfigService],
    }),
    BullModule.registerQueue({ name: INVESTIGATE_QUEUE }),
    AuthModule,
    AgentsModule,
    SettingsModule,
    WebhooksModule,
    JobsModule,
    MetricsModule,
    LogsModule,
    HealthModule,
    ReportsModule,
    InternalModule,
  ],
  providers: [BootstrapService],
})
export class AppModule {}
