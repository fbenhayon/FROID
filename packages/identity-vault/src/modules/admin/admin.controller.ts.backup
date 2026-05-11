import { Controller, Get, Post, Put, Delete, Body, Param, UseGuards } from '@nestjs/common';
import { AdminService } from './admin.service';
import { JwtAuthGuard } from '../../auth/jwt-auth.guard';

@Controller('admin')
@UseGuards(JwtAuthGuard)
export class AdminController {
  constructor(private adminService: AdminService) {}

  @Post('prompts')
  createPrompt(@Body() body: any) {
    return this.adminService.createPrompt(body);
  }

  @Get('prompts')
  getAllPrompts() {
    return this.adminService.getAllPrompts();
  }

  @Get('prompts/category/:category')
  getPromptsByCategory(@Param('category') category: string) {
    return this.adminService.getPromptsByCategory(category);
  }

  @Get('prompts/:id')
  getPromptById(@Param('id') id: string) {
    return this.adminService.getPromptById(id);
  }

  @Put('prompts/:id')
  updatePrompt(@Param('id') id: string, @Body() body: any) {
    return this.adminService.updatePrompt(id, body);
  }

  @Delete('prompts/:id')
  deletePrompt(@Param('id') id: string) {
    return this.adminService.deletePrompt(id);
  }

  @Put('prompts/:id/toggle')
  togglePromptStatus(@Param('id') id: string) {
    return this.adminService.togglePromptStatus(id);
  }
}
