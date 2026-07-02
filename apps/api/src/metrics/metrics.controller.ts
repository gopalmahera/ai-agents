import { Controller, Get, Query, UseGuards } from '@nestjs/common';
import { AdminGuard } from '../auth/admin.guard';
import { getMetricsStats, streamRange } from '../lib/redis';

@Controller('api/v1/metrics')
@UseGuards(AdminGuard)
export class MetricsController {
  @Get('stats')
  async stats() {
    return getMetricsStats();
  }

  @Get('stream')
  async stream(@Query('since_ms') sinceMs?: string, @Query('count') count?: string) {
    const since = sinceMs ? parseInt(sinceMs, 10) : Date.now() - 7 * 86400000;
    const entries = await streamRange(since, count ? parseInt(count, 10) : 50000);
    return { entries };
  }
}
