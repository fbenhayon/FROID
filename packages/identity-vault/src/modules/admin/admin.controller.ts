import { Controller, Post, Get, Body, Param, UseGuards, Query } from '@nestjs/common';
import { AdminService } from './admin.service';
import { SuperAdminGuard } from './admin.guard';
import { JwtAuthGuard } from '../../auth/jwt-auth.guard';

@Controller('admin')
@UseGuards(JwtAuthGuard, SuperAdminGuard)
export class AdminController {
  constructor(private adminService: AdminService) {}

  @Post('grant-credits')
  async grantCredits(@Body() body: { userId: string; credits: number; reason: string }) {
    return this.adminService.grantCredits(body.userId, body.credits, body.reason);
  }

  @Post('cancel-subscription/:id')
  async cancelSubscription(@Param('id') id: string, @Body() body: { reason: string }) {
    return this.adminService.cancelSubscription(id, body.reason);
  }

  @Get('users')
  async getAllUsers() {
    return this.adminService.getAllUsers();
  }

  @Get('transactions')
  async getAllTransactions() {
    return this.adminService.getAllTransactions();
  }

  @Post('execute-sql')
  async executeSQL(@Body() body: { query: string }) {
    return this.adminService.executeSQL(body.query);
  }

  @Get('sessions')
  async getSessionLogs(@Query('sessionId') sessionId?: string) {
    return this.adminService.getSessionLogs(sessionId);
  }

  @Get('stats')
  async getSystemStats() {
    return this.adminService.getSystemStats();
  }
}
