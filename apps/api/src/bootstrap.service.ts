import { Injectable, OnModuleInit } from '@nestjs/common';
import { seedIfEmpty } from './lib/settings-store';
import { mongoConfigured } from './lib/mongo';

@Injectable()
export class BootstrapService implements OnModuleInit {
  async onModuleInit(): Promise<void> {
    if (!mongoConfigured()) return;
    await seedIfEmpty();
  }
}
