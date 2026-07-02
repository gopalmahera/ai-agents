"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.AppModule = void 0;
const common_1 = require("@nestjs/common");
const config_1 = require("@nestjs/config");
const bullmq_1 = require("@nestjs/bullmq");
const settings_module_1 = require("./settings/settings.module");
const webhooks_module_1 = require("./webhooks/webhooks.module");
const jobs_module_1 = require("./jobs/jobs.module");
const agents_module_1 = require("./agents/agents.module");
const metrics_module_1 = require("./metrics/metrics.module");
const logs_module_1 = require("./logs/logs.module");
const health_module_1 = require("./health/health.module");
const reports_module_1 = require("./reports/reports.module");
const internal_module_1 = require("./internal/internal.module");
const auth_module_1 = require("./auth/auth.module");
const bootstrap_service_1 = require("./bootstrap.service");
const investigate_constants_1 = require("./jobs/investigate.constants");
let AppModule = class AppModule {
};
exports.AppModule = AppModule;
exports.AppModule = AppModule = __decorate([
    (0, common_1.Module)({
        imports: [
            config_1.ConfigModule.forRoot({ isGlobal: true }),
            bullmq_1.BullModule.forRootAsync({
                imports: [config_1.ConfigModule],
                useFactory: (config) => ({
                    connection: {
                        url: config.get('REDIS_URL') || 'redis://localhost:6379/0',
                    },
                    prefix: config.get('BULLMQ_PREFIX') || 'ai-agent',
                }),
                inject: [config_1.ConfigService],
            }),
            bullmq_1.BullModule.registerQueue({ name: investigate_constants_1.INVESTIGATE_QUEUE }),
            auth_module_1.AuthModule,
            agents_module_1.AgentsModule,
            settings_module_1.SettingsModule,
            webhooks_module_1.WebhooksModule,
            jobs_module_1.JobsModule,
            metrics_module_1.MetricsModule,
            logs_module_1.LogsModule,
            health_module_1.HealthModule,
            reports_module_1.ReportsModule,
            internal_module_1.InternalModule,
        ],
        providers: [bootstrap_service_1.BootstrapService],
    })
], AppModule);
//# sourceMappingURL=app.module.js.map