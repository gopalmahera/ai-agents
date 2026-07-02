"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
var __param = (this && this.__param) || function (paramIndex, decorator) {
    return function (target, key) { decorator(target, key, paramIndex); }
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.WebhooksService = void 0;
const common_1 = require("@nestjs/common");
const bullmq_1 = require("@nestjs/bullmq");
const bullmq_2 = require("bullmq");
const crypto_1 = require("crypto");
const ioredis_1 = require("ioredis");
const config_1 = require("@nestjs/config");
const settings_store_1 = require("../lib/settings-store");
const silence_util_1 = require("./silence.util");
const investigate_constants_1 = require("../jobs/investigate.constants");
let WebhooksService = class WebhooksService {
    constructor(investigateQueue, config) {
        this.investigateQueue = investigateQueue;
        const url = config.get('REDIS_URL') || 'redis://localhost:6379/0';
        this.redis = new ioredis_1.default(url, { maxRetriesPerRequest: 1 });
    }
    async dedupCheckAndSet(fingerprint, ttlSeconds) {
        const wasNew = await this.redis.set(`dedup:${fingerprint}`, '1', 'EX', ttlSeconds, 'NX');
        return wasNew === null;
    }
    async counterInc(name) {
        await this.redis.incrby(`counter:${name}`, 1);
    }
    async streamAdd(fields) {
        await this.redis.xadd('stream:alerts', 'MAXLEN', '~', '50000', '*', ...Object.entries(fields).flat());
    }
    isAllowedAlertname(alertname, pattern) {
        if (!pattern.trim())
            return true;
        try {
            return new RegExp(pattern).test(alertname);
        }
        catch {
            return true;
        }
    }
    async processWebhook(env, payload) {
        const groupStatus = payload.status || 'unknown';
        const alerts = payload.alerts || [];
        if (groupStatus === 'resolved') {
            return { status: 'ok', alerts_received: alerts.length, accepted: 0 };
        }
        const settings = await (0, settings_store_1.getAgentSettings)(false);
        const dedupTtl = Number(settings.DEDUP_TTL_SECONDS || 900);
        const allowPattern = String(settings.ALLOWED_ALERTNAMES || '');
        const silences = await (0, settings_store_1.getSilencesConfig)();
        const activeRules = silences.silences?.active || [];
        let accepted = 0;
        for (const alert of alerts) {
            const labels = alert.labels || {};
            const alertname = labels.alertname || 'unknown';
            const status = alert.status || 'unknown';
            const fingerprint = alert.fingerprint || 'missing';
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
            const { silenced, silenceId } = (0, silence_util_1.isSilenced)(labels, activeRules);
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
            const jobId = (0, crypto_1.randomUUID)();
            const job = { jobId, env, alert, fingerprint };
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
};
exports.WebhooksService = WebhooksService;
exports.WebhooksService = WebhooksService = __decorate([
    (0, common_1.Injectable)(),
    __param(0, (0, bullmq_1.InjectQueue)(investigate_constants_1.INVESTIGATE_QUEUE)),
    __metadata("design:paramtypes", [bullmq_2.Queue,
        config_1.ConfigService])
], WebhooksService);
//# sourceMappingURL=webhooks.service.js.map