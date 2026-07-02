import { Injectable } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { randomUUID } from 'crypto';
import Redis from 'ioredis';
import { ConfigService } from '@nestjs/config';
import { getAgentSettings, getSilencesConfig } from '../lib/settings-store';
import { isSilenced } from './silence.util';
import { INVESTIGATE_QUEUE, InvestigateJobPayload } from '../jobs/investigate.constants';

@Injectable()
export class WebhooksService {
  private readonly redis: Redis;

  constructor(
    @InjectQueue(INVESTIGATE_QUEUE) private readonly investigateQueue: Queue<InvestigateJobPayload>,
    config: ConfigService,
  ) {
    const url = config.get<string>('REDIS_URL') || 'redis://localhost:6379/0';
    this.redis = new Redis(url, { maxRetriesPerRequest: 1 });
  }

  private async dedupCheckAndSet(fingerprint: string, ttlSeconds: number): Promise<boolean> {
    const wasNew = await this.redis.set(`dedup:${fingerprint}`, '1', 'EX', ttlSeconds, 'NX');
    return wasNew === null;
  }

  private async counterInc(name: string): Promise<void> {
    await this.redis.incrby(`counter:${name}`, 1);
  }

  private async streamAdd(fields: Record<string, string>): Promise<void> {
    await this.redis.xadd('stream:alerts', 'MAXLEN', '~', '50000', '*', ...Object.entries(fields).flat());
  }

  private isAllowedAlertname(alertname: string, pattern: string): boolean {
    if (!pattern.trim()) return true;
    try {
      return new RegExp(pattern).test(alertname);
    } catch {
      return true;
    }
  }

  async processWebhook(env: string | null, payload: Record<string, unknown>) {
    const groupStatus = (payload.status as string) || 'unknown';
    const alerts = (payload.alerts as Record<string, unknown>[]) || [];

    if (groupStatus === 'resolved') {
      return { status: 'ok', alerts_received: alerts.length, accepted: 0 };
    }

    const settings = await getAgentSettings(false);
    const dedupTtl = Number(settings.DEDUP_TTL_SECONDS || 900);
    const allowPattern = String(settings.ALLOWED_ALERTNAMES || '');
    const silences = await getSilencesConfig();
    const activeRules = silences.silences?.active || [];

    let accepted = 0;
    for (const alert of alerts) {
      const labels = (alert.labels as Record<string, string>) || {};
      const alertname = labels.alertname || 'unknown';
      const status = (alert.status as string) || 'unknown';
      const fingerprint = (alert.fingerprint as string) || 'missing';

      await this.counterInc('alerts_received');
      await this.redis.hincrby('alertname:counts', alertname, 1);

      if (status !== 'firing') {
        await this.counterInc('alerts_skipped');
        continue;
      }

      if (!this.isAllowedAlertname(alertname, allowPattern)) {
        await this.counterInc('alerts_skipped');
        continue;
      }

      const { silenced, silenceId } = isSilenced(labels, activeRules);
      if (silenced) {
        await this.counterInc('alerts_silenced');
        await this.streamAdd({
          alertname,
          outcome: 'silenced',
          namespace: labels.namespace || '',
          fingerprint,
          silence_id: silenceId || '',
        });
        continue;
      }

      if (await this.dedupCheckAndSet(fingerprint, dedupTtl)) {
        await this.counterInc('alerts_deduplicated');
        continue;
      }

      const jobId = randomUUID();
      const job: InvestigateJobPayload = { jobId, env, alert, fingerprint };
      await this.investigateQueue.add('investigate', job, {
        jobId,
        removeOnComplete: 1000,
        removeOnFail: 5000,
        attempts: 3,
        backoff: { type: 'exponential', delay: 5000 },
      });

      await this.counterInc('alerts_accepted');
      await this.streamAdd({
        alertname,
        outcome: 'accepted',
        namespace: labels.namespace || '',
        fingerprint,
      });
      accepted += 1;
    }

    return { status: 'ok', alerts_received: alerts.length, accepted };
  }
}
