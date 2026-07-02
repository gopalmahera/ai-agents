import {
  CanActivate,
  ExecutionContext,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const token = this.config.get<string>('ADMIN_TOKEN') || '';
    if (!token) return true;
    const req = context.switchToHttp().getRequest<{ headers: { authorization?: string } }>();
    const auth = req.headers.authorization || '';
    if (auth !== `Bearer ${token}`) {
      throw new UnauthorizedException('Unauthorized');
    }
    return true;
  }
}
