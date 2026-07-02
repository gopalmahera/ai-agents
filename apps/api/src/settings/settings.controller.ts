import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  NotFoundException,
  Param,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import { AdminGuard } from '../auth/admin.guard';
import {
  getAgentSettings,
  updateAgentSettings,
  listEndpoints,
  getEndpoint,
  createEndpoint,
  updateEndpoint,
  deleteEndpoint,
  listEnvironments,
  getEnvironment,
  createEnvironment,
  updateEnvironment,
  deleteEnvironment,
  listRoutingRules,
  createRoutingRule,
  updateRoutingRule,
  deleteRoutingRule,
  reorderRoutingRules,
  getRoutingConfig,
  updateRoutingMeta,
  getTimeIntervalsConfig,
  createTimeInterval,
  updateTimeInterval,
  deleteTimeInterval,
  reorderTimeIntervals,
  listSilences,
  createSilence,
  updateSilence,
  deleteSilence,
  disableSilence,
  enableSilence,
  ValidationError,
  NotFoundError,
} from '../lib/settings-store';
import { AgentsGateway } from '../agents/agents.gateway';

function mapError(err: unknown): never {
  if (err instanceof ValidationError) {
    throw new BadRequestException({ error: err.message, details: err.details });
  }
  if (err instanceof NotFoundError) {
    throw new NotFoundException({ error: err.message });
  }
  throw err;
}

@Controller('api/v1/settings')
@UseGuards(AdminGuard)
export class SettingsController {
  constructor(private readonly agents: AgentsGateway) {}

  private async notifyConfig(): Promise<void> {
    await this.agents.broadcastConfigUpdated();
  }

  @Get('agent')
  async getAgent() {
    return getAgentSettings(true);
  }

  @Put('agent')
  async putAgent(@Body() body: Record<string, unknown>) {
    try {
      const result = await updateAgentSettings(body);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Get('endpoints')
  async getEndpoints(@Query('q') q?: string, @Query('type') type?: string) {
    return listEndpoints(q, type);
  }

  @Post('endpoints')
  async postEndpoint(@Body() body: Record<string, unknown>) {
    try {
      const result = await createEndpoint(body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Get('endpoints/:name')
  async getEndpointByName(@Param('name') name: string) {
    const ep = await getEndpoint(name);
    if (!ep) throw new NotFoundException({ error: `Endpoint "${name}" not found` });
    return ep;
  }

  @Put('endpoints/:name')
  async putEndpointByName(@Param('name') name: string, @Body() body: Record<string, unknown>) {
    try {
      const result = await updateEndpoint(name, body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Delete('endpoints/:name')
  async deleteEndpointByName(@Param('name') name: string) {
    try {
      await deleteEndpoint(name);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('environments')
  async getEnvironments(@Query('q') q?: string) {
    return listEnvironments(q);
  }

  @Post('environments')
  async postEnvironment(@Body() body: Record<string, unknown>) {
    try {
      const result = await createEnvironment(body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Get('environments/:name')
  async getEnvironmentByName(@Param('name') name: string) {
    const env = await getEnvironment(name);
    if (!env) throw new NotFoundException({ error: `Environment "${name}" not found` });
    return env;
  }

  @Put('environments/:name')
  async putEnvironmentByName(@Param('name') name: string, @Body() body: Record<string, unknown>) {
    try {
      const result = await updateEnvironment(name, body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Delete('environments/:name')
  async deleteEnvironmentByName(@Param('name') name: string) {
    try {
      await deleteEnvironment(name);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('routing')
  async getRouting() {
    return getRoutingConfig();
  }

  @Put('routing/meta')
  async putRoutingMeta(@Body() body: { default_slack_webhook_url?: string }) {
    await updateRoutingMeta(body.default_slack_webhook_url || '');
    await this.notifyConfig();
    return { ok: true };
  }

  @Get('routing/rules')
  async getRoutingRules() {
    return listRoutingRules();
  }

  @Post('routing/rules')
  async postRoutingRule(@Body() body: Record<string, unknown>) {
    try {
      const result = await createRoutingRule(body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Put('routing/rules/:id')
  async putRoutingRuleById(@Param('id') id: string, @Body() body: Record<string, unknown>) {
    try {
      const result = await updateRoutingRule(id, body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Delete('routing/rules/:id')
  async deleteRoutingRuleById(@Param('id') id: string) {
    try {
      await deleteRoutingRule(id);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Put('routing/reorder')
  async reorderRouting(@Body() body: { ids: string[] }) {
    await reorderRoutingRules(body.ids || []);
    await this.notifyConfig();
    return { ok: true };
  }

  @Get('time-intervals')
  async getTimeIntervals() {
    return getTimeIntervalsConfig();
  }

  @Post('time-intervals')
  async postTimeInterval(@Body() body: Record<string, unknown>) {
    try {
      const result = await createTimeInterval(body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Put('time-intervals/:name')
  async putTimeIntervalByName(@Param('name') name: string, @Body() body: Record<string, unknown>) {
    try {
      const result = await updateTimeInterval(name, body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Delete('time-intervals/:name')
  async deleteTimeIntervalByName(@Param('name') name: string) {
    try {
      await deleteTimeInterval(name);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Put('time-intervals/reorder')
  async reorderTimeIntervalsRoute(@Body() body: { names: string[] }) {
    await reorderTimeIntervals(body.names || []);
    await this.notifyConfig();
    return { ok: true };
  }

  @Get('silences')
  async getSilences(@Query('status') status?: 'active' | 'disabled') {
    return listSilences(status);
  }

  @Post('silences')
  async postSilence(@Body() body: Record<string, unknown>) {
    try {
      const result = await createSilence(body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Put('silences/:id')
  async putSilenceById(@Param('id') id: string, @Body() body: Record<string, unknown>) {
    try {
      const result = await updateSilence(id, body as never);
      await this.notifyConfig();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Delete('silences/:id')
  async deleteSilenceById(@Param('id') id: string) {
    try {
      await deleteSilence(id);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Post('silences/:id/disable')
  async disableSilenceById(@Param('id') id: string) {
    try {
      await disableSilence(id);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Post('silences/:id/enable')
  async enableSilenceById(@Param('id') id: string, @Body() body: Record<string, unknown>) {
    try {
      await enableSilence(id, body as never);
      await this.notifyConfig();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }
}
