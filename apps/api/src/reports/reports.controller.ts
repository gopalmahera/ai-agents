import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { AdminGuard } from '../auth/admin.guard';
import { recentEvents, reportSummary } from '../lib/settings-store';

@Controller('api/v1/reports')
@UseGuards(AdminGuard)
export class ReportsController {
  @Get('summary')
  async summary(@Query('days') days?: string) {
    return reportSummary(days ? parseInt(days, 10) : 7);
  }

  @Get('events')
  async events(
    @Query('days') days?: string,
    @Query('alertname') alertname?: string,
    @Query('outcome') outcome?: string,
    @Query('limit') limit?: string,
    @Query('skip') skip?: string,
  ) {
    return recentEvents({
      days: days ? parseInt(days, 10) : 7,
      alertname,
      outcome,
      limit: limit ? parseInt(limit, 10) : 100,
      skip: skip ? parseInt(skip, 10) : 0,
    });
  }
}
