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
Object.defineProperty(exports, "__esModule", { value: true });
exports.HealthController = void 0;
const common_1 = require("@nestjs/common");
const mongo_1 = require("../lib/mongo");
const redis_1 = require("../lib/redis");
const agents_registry_1 = require("../agents/agents.registry");
const agents_gateway_1 = require("../agents/agents.gateway");
let HealthController = class HealthController {
    constructor(registry, agents) {
        this.registry = registry;
        this.agents = agents;
    }
    async health() {
        const [mongo, redis] = await Promise.all([(0, mongo_1.mongoHealth)(), (0, redis_1.redisHealth)()]);
        return { status: 'ok', mongo, redis, agents_online: this.registry.listOnline().length };
    }
    mcpHealth() {
        return this.agents.getMcpHealthAggregate();
    }
};
exports.HealthController = HealthController;
__decorate([
    (0, common_1.Get)(),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], HealthController.prototype, "health", null);
__decorate([
    (0, common_1.Get)('mcp'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", void 0)
], HealthController.prototype, "mcpHealth", null);
exports.HealthController = HealthController = __decorate([
    (0, common_1.Controller)('api/v1/health'),
    __metadata("design:paramtypes", [agents_registry_1.AgentsRegistry,
        agents_gateway_1.AgentsGateway])
], HealthController);
//# sourceMappingURL=health.controller.js.map