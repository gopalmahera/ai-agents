import { Module, forwardRef } from '@nestjs/common';
import { SettingsController } from './settings.controller';
import { LegacyConfigController } from './legacy-config.controller';
import { AgentsModule } from '../agents/agents.module';

@Module({
  imports: [forwardRef(() => AgentsModule)],
  controllers: [SettingsController, LegacyConfigController],
})
export class SettingsModule {}
