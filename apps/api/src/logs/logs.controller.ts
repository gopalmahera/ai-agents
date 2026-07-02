import {
  Controller,
  Delete,
  Get,
  NotFoundException,
  Param,
  Query,
  UseGuards,
} from '@nestjs/common';
import { AdminGuard } from '../auth/admin.guard';
import { deleteLog, listLogs, readLog } from '../lib/logs';

@Controller('api/v1/logs')
@UseGuards(AdminGuard)
export class LogsController {
  @Get()
  list(@Query('q') q?: string, @Query('type') type?: string, @Query('limit') limit?: string) {
    return listLogs(q || '', type || '', limit ? parseInt(limit, 10) : 100);
  }

  @Get(':filename')
  get(@Param('filename') filename: string) {
    try {
      return { filename, content: readLog(filename) };
    } catch (e) {
      throw new NotFoundException({ error: String(e) });
    }
  }

  @Delete(':filename')
  remove(@Param('filename') filename: string) {
    try {
      deleteLog(filename);
      return { ok: true };
    } catch (e) {
      throw new NotFoundException({ error: String(e) });
    }
  }
}
