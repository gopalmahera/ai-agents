import {
  ConnectedSocket,
  MessageBody,
  OnGatewayConnection,
  OnGatewayDisconnect,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Injectable, Logger, forwardRef, Inject } from '@nestjs/common';
import { Server, Socket } from 'socket.io';
import { AgentsRegistry } from './agents.registry';
import { getSettingsVersion } from '../lib/settings-store';
import { InvestigateJobPayload } from '../jobs/investigate.constants';

type PendingJob = {
  resolve: (value: Record<string, unknown>) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
};

@Injectable()
@WebSocketGateway({ namespace: '/agents', cors: { origin: '*' } })
export class AgentsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  private readonly logger = new Logger(AgentsGateway.name);
  private readonly pending = new Map<string, PendingJob>();

  @WebSocketServer()
  server!: Server;

  constructor(private readonly registry: AgentsRegistry) {}

  async handleConnection(client: Socket): Promise<void> {
    this.logger.log(`Agent socket connected: ${client.id}`);
  }

  async handleDisconnect(client: Socket): Promise<void> {
    const agentId = client.data.agentId as string | undefined;
    if (agentId) {
      await this.registry.unregister(agentId);
      this.logger.log(`Agent disconnected: ${agentId}`);
    }
  }

  @SubscribeMessage('register')
  async onRegister(
    @ConnectedSocket() client: Socket,
    @MessageBody()
    body: { agentId: string; version?: string; capabilities?: string[]; mcpHealth?: Record<string, unknown> },
  ) {
    const agentId = body.agentId?.trim();
    if (!agentId) return { ok: false, error: 'agentId required' };
    client.data.agentId = agentId;
    await client.join(`agent:${agentId}`);
    await this.registry.register({
      agentId,
      socketId: client.id,
      version: body.version,
      capabilities: body.capabilities,
      mcpHealth: body.mcpHealth,
      connectedAt: new Date().toISOString(),
    });
    const version = await getSettingsVersion();
    const config = await this.buildConfigSnapshot();
    return { ok: true, configVersion: version, config };
  }

  @SubscribeMessage('health.ping')
  async onHealthPing(
    @ConnectedSocket() client: Socket,
    @MessageBody() body: { agentId?: string; mcpHealth?: Record<string, unknown> },
  ) {
    const agentId = (body.agentId || client.data.agentId) as string;
    if (agentId) await this.registry.heartbeat(agentId);
    return { ok: true };
  }

  @SubscribeMessage('job.result')
  async onJobResult(@MessageBody() body: { jobId: string; result: Record<string, unknown> }) {
    const pending = this.pending.get(body.jobId);
    if (pending) {
      clearTimeout(pending.timer);
      this.pending.delete(body.jobId);
      pending.resolve(body.result || {});
    }
    return { ok: true };
  }

  async broadcastConfigUpdated(): Promise<void> {
    const version = await getSettingsVersion();
    const config = await this.buildConfigSnapshot();
    this.server.emit('config.updated', { version, config });
  }

  async buildConfigSnapshot(): Promise<Record<string, unknown>> {
    const { getAgentSettings, getRoutingConfig, getSilencesConfig, getTimeIntervalsConfig, listEndpoints, listEnvironments } =
      await import('../lib/settings-store');
    const [agent, routing, silences, intervals, endpoints, environments] = await Promise.all([
      getAgentSettings(false),
      getRoutingConfig(),
      getSilencesConfig(),
      getTimeIntervalsConfig(),
      listEndpoints(),
      listEnvironments(),
    ]);
    return { agent, routing, silences, intervals, endpoints, environments };
  }

  async dispatchInvestigate(job: InvestigateJobPayload, timeoutMs = 300_000): Promise<Record<string, unknown>> {
    const agent = this.registry.pickAgent();
    if (!agent) {
      throw new Error('No agent online');
    }
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(job.jobId);
        reject(new Error(`Investigation timed out for job ${job.jobId}`));
      }, timeoutMs);
      this.pending.set(job.jobId, { resolve, reject, timer });
      this.server.to(`agent:${agent.agentId}`).emit('investigate', job);
    });
  }

  getMcpHealthAggregate(): Record<string, unknown> {
    const online = this.registry.listOnline();
    const merged: Record<string, unknown> = {};
    for (const a of online) {
      if (a.mcpHealth) Object.assign(merged, a.mcpHealth);
    }
    return merged;
  }
}
