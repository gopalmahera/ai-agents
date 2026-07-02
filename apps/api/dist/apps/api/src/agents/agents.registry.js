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
exports.AgentsRegistry = void 0;
const common_1 = require("@nestjs/common");
const ioredis_1 = require("ioredis");
const config_1 = require("@nestjs/config");
let AgentsRegistry = class AgentsRegistry {
    constructor(config) {
        this.local = new Map();
        const url = config.get('REDIS_URL') || 'redis://localhost:6379/0';
        this.redis = new ioredis_1.default(url, { maxRetriesPerRequest: 1 });
    }
    async register(presence) {
        this.local.set(presence.agentId, presence);
        await this.redis.set(`agent:online:${presence.agentId}`, JSON.stringify(presence), 'EX', 120);
    }
    async unregister(agentId) {
        this.local.delete(agentId);
        await this.redis.del(`agent:online:${agentId}`);
    }
    async heartbeat(agentId) {
        await this.redis.expire(`agent:online:${agentId}`, 120);
    }
    listOnline() {
        return [...this.local.values()];
    }
    get(agentId) {
        return this.local.get(agentId);
    }
    pickAgent() {
        const online = this.listOnline();
        return online[0];
    }
};
exports.AgentsRegistry = AgentsRegistry;
exports.AgentsRegistry = AgentsRegistry = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [config_1.ConfigService])
], AgentsRegistry);
//# sourceMappingURL=agents.registry.js.map