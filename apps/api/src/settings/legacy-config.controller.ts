import {
  BadRequestException,
  Body,
  Controller,
  Get,
  Param,
  Post,
  Put,
  UseGuards,
} from '@nestjs/common';
import { AdminGuard } from '../auth/admin.guard';
import {
  getAgentSettings,
  updateAgentSettings,
  listEndpoints,
  listEnvironments,
  getRoutingConfig,
  getSilencesConfig,
  getTimeIntervalsConfig,
  saveEndpointsBulk,
  saveEnvironmentsBulk,
  saveRoutingBulk,
  saveSilencesBulk,
  saveTimeIntervalsBulk,
  disableSilence,
  enableSilence,
  ValidationError,
} from '../lib/settings-store';
import { AgentsGateway } from '../agents/agents.gateway';

function mapError(err: unknown): never {
  if (err instanceof ValidationError) {
    throw new BadRequestException({ error: err.message, details: err.details });
  }
  throw err;
}

/** Legacy /api/config shim for one release. */
@Controller('api/config')
@UseGuards(AdminGuard)
export class LegacyConfigController {
  constructor(private readonly agents: AgentsGateway) {}

  private async notify(): Promise<void> {
    await this.agents.broadcastConfigUpdated();
  }

  @Get()
  async getConfig() {
    return getAgentSettings(true);
  }

  @Put()
  @Post()
  async putConfig(@Body() body: Record<string, unknown>) {
    try {
      const result = await updateAgentSettings(body);
      await this.notify();
      return result;
    } catch (e) {
      mapError(e);
    }
  }

  @Get('endpoints')
  async getEndpoints() {
    const endpoints = await listEndpoints();
    return { endpoints };
  }

  @Put('endpoints')
  @Post('endpoints')
  async putEndpoints(@Body() body: { endpoints: unknown[] }) {
    try {
      await saveEndpointsBulk(body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('environments')
  async getEnvironments() {
    const environments = await listEnvironments();
    return { environments };
  }

  @Put('environments')
  @Post('environments')
  async putEnvironments(@Body() body: { environments: unknown[] }) {
    try {
      await saveEnvironmentsBulk(body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('routing')
  async getRouting() {
    return getRoutingConfig();
  }

  @Put('routing')
  @Post('routing')
  async putRouting(@Body() body: Record<string, unknown>) {
    try {
      await saveRoutingBulk(body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('time-intervals')
  async getTimeIntervals() {
    return getTimeIntervalsConfig();
  }

  @Put('time-intervals')
  @Post('time-intervals')
  async putTimeIntervals(@Body() body: Record<string, unknown>) {
    try {
      await saveTimeIntervalsBulk(body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Get('mute')
  async getMute() {
    return getSilencesConfig();
  }

  @Put('mute')
  @Post('mute')
  async putMute(@Body() body: Record<string, unknown>) {
    try {
      await saveSilencesBulk(body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Post('mute/silences/:id/disable')
  async disableSilenceRoute(@Param('id') id: string) {
    try {
      await disableSilence(id);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }

  @Post('mute/silences/:id/enable')
  async enableSilenceRoute(@Param('id') id: string, @Body() body: Record<string, unknown>) {
    try {
      await enableSilence(id, body as never);
      await this.notify();
      return { ok: true };
    } catch (e) {
      mapError(e);
    }
  }
}
