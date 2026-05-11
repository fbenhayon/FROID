import { Controller, Get, Post, Put, Delete, Body, Param, UseGuards } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiBearerAuth, ApiBody, ApiParam } from '@nestjs/swagger';
import { AdminService } from './admin.service';
import { JwtAuthGuard } from '../../auth/jwt-auth.guard';

@ApiTags('Admin')
@ApiBearerAuth('JWT-auth')
@Controller('admin')
@UseGuards(JwtAuthGuard)
export class AdminController {
  constructor(private adminService: AdminService) {}

  @Post('prompts')
  @ApiOperation({ summary: 'Criar novo prompt clínico' })
  @ApiResponse({ status: 201, description: 'Prompt criado com sucesso' })
  @ApiBody({
    schema: {
      properties: {
        title: { type: 'string', example: 'Análise de Tom Emocional' },
        category: { type: 'string', enum: ['voice', 'face', 'fusion'], example: 'voice' },
        promptText: { type: 'string', example: 'Analise o tom emocional...' },
        createdBy: { type: 'string', example: 'user-uuid' },
      },
    },
  })
  createPrompt(@Body() body: any) {
    return this.adminService.createPrompt(body);
  }

  @Get('prompts')
  @ApiOperation({ summary: 'Listar todos os prompts' })
  @ApiResponse({ status: 200, description: 'Lista de prompts retornada' })
  getAllPrompts() {
    return this.adminService.getAllPrompts();
  }

  @Get('prompts/category/:category')
  @ApiOperation({ summary: 'Buscar prompts por categoria' })
  @ApiParam({ name: 'category', enum: ['voice', 'face', 'fusion'] })
  @ApiResponse({ status: 200, description: 'Prompts filtrados por categoria' })
  getPromptsByCategory(@Param('category') category: string) {
    return this.adminService.getPromptsByCategory(category);
  }

  @Get('prompts/:id')
  @ApiOperation({ summary: 'Buscar prompt por ID' })
  @ApiParam({ name: 'id', type: 'string' })
  @ApiResponse({ status: 200, description: 'Prompt encontrado' })
  @ApiResponse({ status: 404, description: 'Prompt não encontrado' })
  getPromptById(@Param('id') id: string) {
    return this.adminService.getPromptById(id);
  }

  @Put('prompts/:id')
  @ApiOperation({ summary: 'Atualizar prompt' })
  @ApiParam({ name: 'id', type: 'string' })
  @ApiResponse({ status: 200, description: 'Prompt atualizado' })
  updatePrompt(@Param('id') id: string, @Body() body: any) {
    return this.adminService.updatePrompt(id, body);
  }

  @Delete('prompts/:id')
  @ApiOperation({ summary: 'Deletar prompt' })
  @ApiParam({ name: 'id', type: 'string' })
  @ApiResponse({ status: 200, description: 'Prompt deletado' })
  deletePrompt(@Param('id') id: string) {
    return this.adminService.deletePrompt(id);
  }

  @Put('prompts/:id/toggle')
  @ApiOperation({ summary: 'Ativar/desativar prompt' })
  @ApiParam({ name: 'id', type: 'string' })
  @ApiResponse({ status: 200, description: 'Status do prompt alterado' })
  togglePromptStatus(@Param('id') id: string) {
    return this.adminService.togglePromptStatus(id);
  }
}
