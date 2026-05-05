import { Controller, Post, Get, Patch, Delete, Body, Param } from '@nestjs/common';
import { PromptService } from './prompt.service';

@Controller('prompts')
export class PromptController {
  constructor(private promptService: PromptService) {}

  @Post('execute')
  execute(@Body() data: any) {
    return this.promptService.executePrompt(data);
  }

  @Get('professional/:professionalId')
  listByProfessional(@Param('professionalId') professionalId: string) {
    return this.promptService.findByProfessional(professionalId);
  }

  @Post()
  create(@Body() data: any) {
    return this.promptService.create(data);
  }

  @Patch(':id')
  update(@Param('id') id: string, @Body() data: any) {
    return this.promptService.update(id, data);
  }

  @Delete(':id')
  delete(@Param('id') id: string) {
    return this.promptService.delete(id);
  }
}
