import { Controller, Post, Get, Patch, Body, Param } from '@nestjs/common';
import { SessionService } from './session.service';

@Controller('sessions')
export class SessionController {
  constructor(private sessionService: SessionService) {}

  @Post()
  create(@Body() data: any) {
    return this.sessionService.create(data);
  }

  @Get('patient/:patientId')
  listByPatient(@Param('patientId') patientId: string) {
    return this.sessionService.findByPatient(patientId);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.sessionService.findOne(id);
  }

  @Patch(':id/end')
  endSession(@Param('id') id: string) {
    return this.sessionService.endSession(id);
  }
}
