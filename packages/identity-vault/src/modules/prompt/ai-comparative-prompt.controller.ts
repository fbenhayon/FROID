import { Controller, Get, Post, Patch, Delete, Body, Param, UseGuards, Request } from '@nestjs/common';
import { AIComparativePromptService } from './ai-comparative-prompt.service';
import { JwtAuthGuard } from '../../auth/jwt-auth.guard';

@Controller('ai-prompts')
@UseGuards(JwtAuthGuard)
export class AIComparativePromptController {
  constructor(private service: AIComparativePromptService) {}

  @Get()
  async list(@Request() req) {
    return this.service.listPrompts(req.user.sub);
  }

  @Get(':id')
  async get(@Param('id') id: string, @Request() req) {
    return this.service.getPrompt(id, req.user.sub);
  }

  @Post()
  async create(@Body() body: any, @Request() req) {
    return this.service.createPrompt(req.user.sub, body);
  }

  @Post(':id/clone')
  async clone(@Param('id') id: string, @Request() req) {
    return this.service.clonePrompt(id, req.user.sub);
  }

  @Patch(':id')
  async update(@Param('id') id: string, @Body() body: any, @Request() req) {
    return this.service.updatePrompt(id, req.user.sub, body);
  }

  @Delete(':id')
  async delete(@Param('id') id: string, @Request() req) {
    return this.service.deletePrompt(id, req.user.sub);
  }
}
