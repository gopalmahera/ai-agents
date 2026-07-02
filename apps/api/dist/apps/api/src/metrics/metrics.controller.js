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
exports.MetricsController = void 0;
const common_1 = require("@nestjs/common");
const admin_guard_1 = require("../auth/admin.guard");
const redis_1 = require("../lib/redis");
let MetricsController = class MetricsController {
    async stats() {
        return (0, redis_1.getMetricsStats)();
    }
    async stream(sinceMs, count) {
        const since = sinceMs ? parseInt(sinceMs, 10) : Date.now() - 7 * 86400000;
        const entries = await (0, redis_1.streamRange)(since, count ? parseInt(count, 10) : 50000);
        return { entries };
    }
};
exports.MetricsController = MetricsController;
__decorate([
    (0, common_1.Get)('stats'),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", []),
    __metadata("design:returntype", Promise)
], MetricsController.prototype, "stats", null);
__decorate([
    (0, common_1.Get)('stream'),
    __param(0, (0, common_1.Query)('since_ms')),
    __param(1, (0, common_1.Query)('count')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String]),
    __metadata("design:returntype", Promise)
], MetricsController.prototype, "stream", null);
exports.MetricsController = MetricsController = __decorate([
    (0, common_1.Controller)('api/v1/metrics'),
    (0, common_1.UseGuards)(admin_guard_1.AdminGuard)
], MetricsController);
//# sourceMappingURL=metrics.controller.js.map