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
var InvestigateProcessor_1;
Object.defineProperty(exports, "__esModule", { value: true });
exports.InvestigateProcessor = void 0;
const bullmq_1 = require("@nestjs/bullmq");
const common_1 = require("@nestjs/common");
const agents_gateway_1 = require("../agents/agents.gateway");
const investigate_constants_1 = require("./investigate.constants");
let InvestigateProcessor = InvestigateProcessor_1 = class InvestigateProcessor extends bullmq_1.WorkerHost {
    constructor(agents) {
        super();
        this.agents = agents;
        this.logger = new common_1.Logger(InvestigateProcessor_1.name);
    }
    async process(job) {
        this.logger.log(`Processing investigate job ${job.data.jobId}`);
        const result = await this.agents.dispatchInvestigate(job.data);
        this.logger.log(`Job ${job.data.jobId} completed`);
        return result;
    }
};
exports.InvestigateProcessor = InvestigateProcessor;
exports.InvestigateProcessor = InvestigateProcessor = InvestigateProcessor_1 = __decorate([
    (0, bullmq_1.Processor)(investigate_constants_1.INVESTIGATE_QUEUE),
    __metadata("design:paramtypes", [agents_gateway_1.AgentsGateway])
], InvestigateProcessor);
//# sourceMappingURL=investigate.processor.js.map