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
exports.ReportsController = void 0;
const common_1 = require("@nestjs/common");
const admin_guard_1 = require("../auth/admin.guard");
const settings_store_1 = require("../lib/settings-store");
let ReportsController = class ReportsController {
    async summary(days) {
        return (0, settings_store_1.reportSummary)(days ? parseInt(days, 10) : 7);
    }
    async events(days, alertname, outcome, limit, skip) {
        return (0, settings_store_1.recentEvents)({
            days: days ? parseInt(days, 10) : 7,
            alertname,
            outcome,
            limit: limit ? parseInt(limit, 10) : 100,
            skip: skip ? parseInt(skip, 10) : 0,
        });
    }
};
exports.ReportsController = ReportsController;
__decorate([
    (0, common_1.Get)('summary'),
    __param(0, (0, common_1.Query)('days')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String]),
    __metadata("design:returntype", Promise)
], ReportsController.prototype, "summary", null);
__decorate([
    (0, common_1.Get)('events'),
    __param(0, (0, common_1.Query)('days')),
    __param(1, (0, common_1.Query)('alertname')),
    __param(2, (0, common_1.Query)('outcome')),
    __param(3, (0, common_1.Query)('limit')),
    __param(4, (0, common_1.Query)('skip')),
    __metadata("design:type", Function),
    __metadata("design:paramtypes", [String, String, String, String, String]),
    __metadata("design:returntype", Promise)
], ReportsController.prototype, "events", null);
exports.ReportsController = ReportsController = __decorate([
    (0, common_1.Controller)('api/v1/reports'),
    (0, common_1.UseGuards)(admin_guard_1.AdminGuard)
], ReportsController);
//# sourceMappingURL=reports.controller.js.map