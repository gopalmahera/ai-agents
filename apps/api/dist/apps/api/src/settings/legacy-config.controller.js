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
exports.LegacyConfigController = void 0;
const common_1 = require("@nestjs/common");
const admin_guard_1 = require("../auth/admin.guard");
const settings_store_1 = require("../lib/settings-store");
const agents_gateway_1 = require("../agents/agents.gateway");
function mapError(err) {
    if (err instanceof settings_store_1.ValidationError) {
        throw new common_1.BadRequestException({ error: err.message, details: err.details });
    }
    throw err;
}
let LegacyConfigController = class LegacyConfigController {
    constructor(agents) {
        this.agents = agents;
    }
    async notify() {
        await this.agents.broadcastConfigUpdated();
    }
    async getConfig() {
        return (0, settings_store_1.getAgentSettings)(true);
    }
    async putConfig(body) {
        try {
            const result = await (0, settings_store_1.updateAgentSettings)(body);
            await this.notify();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEndpoints() {
        const endpoints = await (0, settings_store_1.listEndpoints)();
        return { endpoints };
    }
    async putEndpoints(body) {
        try {
            await (0, settings_store_1.saveEndpointsBulk)(body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEnvironments() {
        const environments = await (0, settings_store_1.listEnvironments)();
        return { environments };
    }
    async putEnvironments(body) {
        try {
            await (0, settings_store_1.saveEnvironmentsBulk)(body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getRouting() {
        return (0, settings_store_1.getRoutingConfig)();
    }
    async putRouting(body) {
        try {
            await (0, settings_store_1.saveRoutingBulk)(body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getTimeIntervals() {
        return (0, settings_store_1.getTimeIntervalsConfig)();
    }
    async putTimeIntervals(body) {
        try {
            await (0, settings_store_1.saveTimeIntervalsBulk)(body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getMute() {
        return (0, settings_store_1.getSilencesConfig)();
    }
    async putMute(body) {
        try {
            await (0, settings_store_1.saveSilencesBulk)(body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async disableSilenceRoute(id) {
        try {
            await (0, settings_store_1.disableSilence)(id);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async enableSilenceRoute(id, body) {
        try {
            await (0, settings_store_1.enableSilence)(id, body);
            await this.notify();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
};
exports.LegacyConfigController = LegacyConfigController;
__decorate([
    (0, common_1.Get)(),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getConfig", null);
__decorate([
    (0, common_1.Put)(),
    (0, common_1.Post)(),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putConfig", null);
__decorate([
    (0, common_1.Get)('endpoints'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getEndpoints", null);
__decorate([
    (0, common_1.Put)('endpoints'),
    (0, common_1.Post)('endpoints'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putEndpoints", null);
__decorate([
    (0, common_1.Get)('environments'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getEnvironments", null);
__decorate([
    (0, common_1.Put)('environments'),
    (0, common_1.Post)('environments'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putEnvironments", null);
__decorate([
    (0, common_1.Get)('routing'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getRouting", null);
__decorate([
    (0, common_1.Put)('routing'),
    (0, common_1.Post)('routing'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putRouting", null);
__decorate([
    (0, common_1.Get)('time-intervals'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getTimeIntervals", null);
__decorate([
    (0, common_1.Put)('time-intervals'),
    (0, common_1.Post)('time-intervals'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putTimeIntervals", null);
__decorate([
    (0, common_1.Get)('mute'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "getMute", null);
__decorate([
    (0, common_1.Put)('mute'),
    (0, common_1.Post)('mute'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "putMute", null);
__decorate([
    (0, common_1.Post)('mute/silences/:id/disable'),
    __param(0, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "disableSilenceRoute", null);
__decorate([
    (0, common_1.Post)('mute/silences/:id/enable'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], LegacyConfigController.prototype, "enableSilenceRoute", null);
exports.LegacyConfigController = LegacyConfigController = __decorate([
    (0, common_1.Controller)('api/config'),
    (0, common_1.UseGuards)(admin_guard_1.AdminGuard),
    __metadata("design:paramtypes", [agents_gateway_1.AgentsGateway])
], LegacyConfigController);
//# sourceMappingURL=legacy-config.controller.js.map