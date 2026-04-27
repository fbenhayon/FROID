import { Controller, Get } from '@nestjs/common';

@Controller()
export class HealthController {
  @Get('health')
  health() {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }

  @Get()
  root() {
    return { message: 'FROID Identity Vault API', version: '1.0.0' };
  }
}
