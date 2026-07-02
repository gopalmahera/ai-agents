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
exports.InternalController = void 0;
const common_1 = require("@nestjs/common");
const settings_store_1 = require("../lib/settings-store");
const agents_gateway_1 = require("../agents/agents.gateway");
let InternalController = class InternalController {
    constructor(agents) {
        this.agents = agents;
    }
    async agentConfig() {
        const version = await (0, settings_store_1.getSettingsVersion)();
        const config = await this.agents.buildConfigSnapshot();
        return { version, config };
    }
};
exports.InternalController = InternalController;
__decorate([
    (0, common_1.Get)('agent/config'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], InternalController.prototype, "agentConfig", null);
exports.InternalController = InternalController = __decorate([
    (0, common_1.Controller)('api/v1/internal'),
    __metadata("design:paramtypes", [agents_gateway_1.AgentsGateway])
], InternalController);
//# sourceMappingURL=internal.controller.js.map