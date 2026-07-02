import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { RedisIoAdapter } from './redis-io.adapter';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({ origin: true, credentials: true });

  const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379/0';
  const redisIoAdapter = new RedisIoAdapter(app);
  await redisIoAdapter.connectToRedis(redisUrl);
  app.useWebSocketAdapter(redisIoAdapter);

  const port = parseInt(process.env.API_PORT || process.env.PORT || '4000', 10);
  await app.listen(port, '0.0.0.0');
  console.log(`API listening on :${port}`);
}
bootstrap();
