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
var AgentsGateway_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.AgentsGateway = void 0;
const websockets_1 = require("@nestjs/websockets");
const common_1 = require("@nestjs/common");
const socket_io_1 = require("socket.io");
const agents_registry_1 = require("./agents.registry");
const settings_store_1 = require("../lib/settings-store");
let AgentsGateway = AgentsGateway_1 = class AgentsGateway {
    constructor(registry) {
        this.registry = registry;
        this.logger = new common_1.Logger(AgentsGateway_1.name);
        this.pending = new Map();
    }
    async handleConnection(client) {
        this.logger.log(`Agent socket connected: ${client.id}`);
    }
    async handleDisconnect(client) {
        const agentId = client.data.agentId;
        if (agentId) {
            await this.registry.unregister(agentId);
            this.logger.log(`Agent disconnected: ${agentId}`);
        }
    }
    async onRegister(client, body) {
        const agentId = body.agentId?.trim();
        if (!agentId)
            return { ok: false, error: 'agentId required' };
        client.data.agentId = agentId;
        await client.join(`agent:${agentId}`);
        await this.registry.register({
            agentId,
            socketId: client.id,
            version: body.version,
            capabilities: body.capabilities,
            mcpHealth: body.mcpHealth,
            connectedAt: new Date().toISOString(),
        });
        const version = await (0, settings_store_1.getSettingsVersion)();
        const config = await this.buildConfigSnapshot();
        return { ok: true, configVersion: version, config };
    }
    async onHealthPing(client, body) {
        const agentId = (body.agentId || client.data.agentId);
        if (agentId)
            await this.registry.heartbeat(agentId);
        return { ok: true };
    }
    async onJobResult(body) {
        const pending = this.pending.get(body.jobId);
        if (pending) {
            clearTimeout(pending.timer);
            this.pending.delete(body.jobId);
            pending.resolve(body.result || {});
        }
        return { ok: true };
    }
    async broadcastConfigUpdated() {
        const version = await (0, settings_store_1.getSettingsVersion)();
        const config = await this.buildConfigSnapshot();
        this.server.emit('config.updated', { version, config });
    }
    async buildConfigSnapshot() {
        const { getAgentSettings, getRoutingConfig, getSilencesConfig, getTimeIntervalsConfig, listEndpoints, listEnvironments } = await Promise.resolve().then(() => require('../lib/settings-store'));
        const [agent, routing, silences, intervals, endpoints, environments] = await Promise.all([
            getAgentSettings(false),
            getRoutingConfig(),
            getSilencesConfig(),
            getTimeIntervalsConfig(),
            listEndpoints(),
            listEnvironments(),
        ]);
        return { agent, routing, silences, intervals, endpoints, environments };
    }
    async dispatchInvestigate(job, timeoutMs = 300_000) {
        const agent = this.registry.pickAgent();
        if (!agent) {
            throw new Error('No agent online');
        }
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(job.jobId);
                reject(new Error(`Investigation timed out for job ${job.jobId}`));
            }, timeoutMs);
            this.pending.set(job.jobId, { resolve, reject, timer });
            this.server.to(`agent:${agent.agentId}`).emit('investigate', job);
        });
    }
    getMcpHealthAggregate() {
        const online = this.registry.listOnline();
        const merged = {};
        for (const a of online) {
            if (a.mcpHealth)
                Object.assign(merged, a.mcpHealth);
        }
        return merged;
    }
};
exports.AgentsGateway = AgentsGateway;
__decorate([
    (0, websockets_1.WebSocketServer)(),
    __metadata("design:type", socket_io_1.Server)
], AgentsGateway.prototype, "server", void 0);
__decorate([
    (0, websockets_1.SubscribeMessage)('register'),
    __param(0, (0, websockets_1.ConnectedSocket)()),
    __param(1, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [socket_io_1.Socket, Object]),
    __metadata("design:returntype", Promise)
], AgentsGateway.prototype, "onRegister", null);
__decorate([
    (0, websockets_1.SubscribeMessage)('health.ping'),
    __param(0, (0, websockets_1.ConnectedSocket)()),
    __param(1, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [socket_io_1.Socket, Object]),
    __metadata("design:returntype", Promise)
], AgentsGateway.prototype, "onHealthPing", null);
__decorate([
    (0, websockets_1.SubscribeMessage)('job.result'),
    __param(0, (0, websockets_1.MessageBody)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], AgentsGateway.prototype, "onJobResult", null);
exports.AgentsGateway = AgentsGateway = AgentsGateway_1 = __decorate([
    (0, common_1.Injectable)(),
    (0, websockets_1.WebSocketGateway)({ namespace: '/agents', cors: { origin: '*' } }),
    __metadata("design:paramtypes", [agents_registry_1.AgentsRegistry])
], AgentsGateway);
//# sourceMappingURL=agents.gateway.js.map