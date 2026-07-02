import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { IoAdapter } from '@nestjs/platform-socket.io';
import { createAdapter } from '@socket.io/redis-adapter';
import { createClient } from 'redis';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  app.enableCors({ origin: true, credentials: true });

  const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379/0';
  const pubClient = createClient({ url: redisUrl });
  const subClient = pubClient.duplicate();
  await Promise.all([pubClient.connect(), subClient.connect()]);
  const ioAdapter = new IoAdapter(app);
  const server = ioAdapter.createIOServer(0);
  server.adapter(createAdapter(pubClient, subClient));
  app.useWebSocketAdapter(ioAdapter);

  const port = parseInt(process.env.API_PORT || process.env.PORT || '4000', 10);
  await app.listen(port, '0.0.0.0');
  console.log(`API listening on :${port}`);
}
bootstrap();
