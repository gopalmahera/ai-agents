"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const core_1 = require("@nestjs/core");
const app_module_1 = require("./app.module");
const platform_socket_io_1 = require("@nestjs/platform-socket.io");
const redis_adapter_1 = require("@socket.io/redis-adapter");
const redis_1 = require("redis");
async function bootstrap() {
    const app = await core_1.NestFactory.create(app_module_1.AppModule);
    app.enableCors({ origin: true, credentials: true });
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379/0';
    const pubClient = (0, redis_1.createClient)({ url: redisUrl });
    const subClient = pubClient.duplicate();
    await Promise.all([pubClient.connect(), subClient.connect()]);
    const ioAdapter = new platform_socket_io_1.IoAdapter(app);
    const server = ioAdapter.createIOServer(0);
    server.adapter((0, redis_adapter_1.createAdapter)(pubClient, subClient));
    app.useWebSocketAdapter(ioAdapter);
    const port = parseInt(process.env.API_PORT || process.env.PORT || '4000', 10);
    await app.listen(port, '0.0.0.0');
    console.log(`API listening on :${port}`);
}
bootstrap();
//# sourceMappingURL=main.js.map