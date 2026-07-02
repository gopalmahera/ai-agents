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
exports.SettingsController = void 0;
const common_1 = require("@nestjs/common");
const admin_guard_1 = require("../auth/admin.guard");
const settings_store_1 = require("../lib/settings-store");
const agents_gateway_1 = require("../agents/agents.gateway");
function mapError(err) {
    if (err instanceof settings_store_1.ValidationError) {
        throw new common_1.BadRequestException({ error: err.message, details: err.details });
    }
    if (err instanceof settings_store_1.NotFoundError) {
        throw new common_1.NotFoundException({ error: err.message });
    }
    throw err;
}
let SettingsController = class SettingsController {
    constructor(agents) {
        this.agents = agents;
    }
    async notifyConfig() {
        await this.agents.broadcastConfigUpdated();
    }
    async getAgent() {
        return (0, settings_store_1.getAgentSettings)(true);
    }
    async putAgent(body) {
        try {
            const result = await (0, settings_store_1.updateAgentSettings)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEndpoints(q, type) {
        return (0, settings_store_1.listEndpoints)(q, type);
    }
    async postEndpoint(body) {
        try {
            const result = await (0, settings_store_1.createEndpoint)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEndpointByName(name) {
        const ep = await (0, settings_store_1.getEndpoint)(name);
        if (!ep)
            throw new common_1.NotFoundException({ error: `Endpoint "${name}" not found` });
        return ep;
    }
    async putEndpointByName(name, body) {
        try {
            const result = await (0, settings_store_1.updateEndpoint)(name, body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async deleteEndpointByName(name) {
        try {
            await (0, settings_store_1.deleteEndpoint)(name);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEnvironments(q) {
        return (0, settings_store_1.listEnvironments)(q);
    }
    async postEnvironment(body) {
        try {
            const result = await (0, settings_store_1.createEnvironment)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async getEnvironmentByName(name) {
        const env = await (0, settings_store_1.getEnvironment)(name);
        if (!env)
            throw new common_1.NotFoundException({ error: `Environment "${name}" not found` });
        return env;
    }
    async putEnvironmentByName(name, body) {
        try {
            const result = await (0, settings_store_1.updateEnvironment)(name, body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async deleteEnvironmentByName(name) {
        try {
            await (0, settings_store_1.deleteEnvironment)(name);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async getRouting() {
        return (0, settings_store_1.getRoutingConfig)();
    }
    async putRoutingMeta(body) {
        await (0, settings_store_1.updateRoutingMeta)(body.default_slack_webhook_url || '');
        await this.notifyConfig();
        return { ok: true };
    }
    async getRoutingRules() {
        return (0, settings_store_1.listRoutingRules)();
    }
    async postRoutingRule(body) {
        try {
            const result = await (0, settings_store_1.createRoutingRule)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async putRoutingRuleById(id, body) {
        try {
            const result = await (0, settings_store_1.updateRoutingRule)(id, body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async deleteRoutingRuleById(id) {
        try {
            await (0, settings_store_1.deleteRoutingRule)(id);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async reorderRouting(body) {
        await (0, settings_store_1.reorderRoutingRules)(body.ids || []);
        await this.notifyConfig();
        return { ok: true };
    }
    async getTimeIntervals() {
        return (0, settings_store_1.getTimeIntervalsConfig)();
    }
    async postTimeInterval(body) {
        try {
            const result = await (0, settings_store_1.createTimeInterval)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async putTimeIntervalByName(name, body) {
        try {
            const result = await (0, settings_store_1.updateTimeInterval)(name, body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async deleteTimeIntervalByName(name) {
        try {
            await (0, settings_store_1.deleteTimeInterval)(name);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async reorderTimeIntervalsRoute(body) {
        await (0, settings_store_1.reorderTimeIntervals)(body.names || []);
        await this.notifyConfig();
        return { ok: true };
    }
    async getSilences(status) {
        return (0, settings_store_1.listSilences)(status);
    }
    async postSilence(body) {
        try {
            const result = await (0, settings_store_1.createSilence)(body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async putSilenceById(id, body) {
        try {
            const result = await (0, settings_store_1.updateSilence)(id, body);
            await this.notifyConfig();
            return result;
        }
        catch (e) {
            mapError(e);
        }
    }
    async deleteSilenceById(id) {
        try {
            await (0, settings_store_1.deleteSilence)(id);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async disableSilenceById(id) {
        try {
            await (0, settings_store_1.disableSilence)(id);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
    async enableSilenceById(id, body) {
        try {
            await (0, settings_store_1.enableSilence)(id, body);
            await this.notifyConfig();
            return { ok: true };
        }
        catch (e) {
            mapError(e);
        }
    }
};
exports.SettingsController = SettingsController;
__decorate([
    (0, common_1.Get)('agent'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getAgent", null);
__decorate([
    (0, common_1.Put)('agent'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putAgent", null);
__decorate([
    (0, common_1.Get)('endpoints'),
    __param(0, (0, common_1.Query)('q')),
    __param(1, (0, common_1.Query)('type')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getEndpoints", null);
__decorate([
    (0, common_1.Post)('endpoints'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "postEndpoint", null);
__decorate([
    (0, common_1.Get)('endpoints/:name'),
    __param(0, (0, common_1.Param)('name')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getEndpointByName", null);
__decorate([
    (0, common_1.Put)('endpoints/:name'),
    __param(0, (0, common_1.Param)('name')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putEndpointByName", null);
__decorate([
    (0, common_1.Delete)('endpoints/:name'),
    __param(0, (0, common_1.Param)('name')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "deleteEndpointByName", null);
__decorate([
    (0, common_1.Get)('environments'),
    __param(0, (0, common_1.Query)('q')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getEnvironments", null);
__decorate([
    (0, common_1.Post)('environments'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "postEnvironment", null);
__decorate([
    (0, common_1.Get)('environments/:name'),
    __param(0, (0, common_1.Param)('name')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getEnvironmentByName", null);
__decorate([
    (0, common_1.Put)('environments/:name'),
    __param(0, (0, common_1.Param)('name')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putEnvironmentByName", null);
__decorate([
    (0, common_1.Delete)('environments/:name'),
    __param(0, (0, common_1.Param)('name')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "deleteEnvironmentByName", null);
__decorate([
    (0, common_1.Get)('routing'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getRouting", null);
__decorate([
    (0, common_1.Put)('routing/meta'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putRoutingMeta", null);
__decorate([
    (0, common_1.Get)('routing/rules'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getRoutingRules", null);
__decorate([
    (0, common_1.Post)('routing/rules'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "postRoutingRule", null);
__decorate([
    (0, common_1.Put)('routing/rules/:id'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putRoutingRuleById", null);
__decorate([
    (0, common_1.Delete)('routing/rules/:id'),
    __param(0, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "deleteRoutingRuleById", null);
__decorate([
    (0, common_1.Put)('routing/reorder'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "reorderRouting", null);
__decorate([
    (0, common_1.Get)('time-intervals'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getTimeIntervals", null);
__decorate([
    (0, common_1.Post)('time-intervals'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "postTimeInterval", null);
__decorate([
    (0, common_1.Put)('time-intervals/:name'),
    __param(0, (0, common_1.Param)('name')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putTimeIntervalByName", null);
__decorate([
    (0, common_1.Delete)('time-intervals/:name'),
    __param(0, (0, common_1.Param)('name')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "deleteTimeIntervalByName", null);
__decorate([
    (0, common_1.Put)('time-intervals/reorder'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "reorderTimeIntervalsRoute", null);
__decorate([
    (0, common_1.Get)('silences'),
    __param(0, (0, common_1.Query)('status')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "getSilences", null);
__decorate([
    (0, common_1.Post)('silences'),
    __param(0, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "postSilence", null);
__decorate([
    (0, common_1.Put)('silences/:id'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "putSilenceById", null);
__decorate([
    (0, common_1.Delete)('silences/:id'),
    __param(0, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "deleteSilenceById", null);
__decorate([
    (0, common_1.Post)('silences/:id/disable'),
    __param(0, (0, common_1.Param)('id')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "disableSilenceById", null);
__decorate([
    (0, common_1.Post)('silences/:id/enable'),
    __param(0, (0, common_1.Param)('id')),
    __param(1, (0, common_1.Body)()),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, Object]),
    __metadata("design:returntype", Promise)
], SettingsController.prototype, "enableSilenceById", null);
exports.SettingsController = SettingsController = __decorate([
    (0, common_1.Controller)('api/v1/settings'),
    (0, common_1.UseGuards)(admin_guard_1.AdminGuard),
    __metadata("design:paramtypes", [agents_gateway_1.AgentsGateway])
], SettingsController);
//# sourceMappingURL=settings.controller.js.map