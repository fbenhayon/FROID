import { Controller, Post, Get, Patch, Delete, Body, Param } from '@nestjs/common';
import { PatientService } from './patient.service';

@Controller('patients')
export class PatientController {
  constructor(private readonly patientService: PatientService) {}

  @Post()
  create(@Body() data: any) {
    return this.patientService.create(data);
  }

  @Get('professional/:professionalId')
  listByProfessional(@Param('professionalId') professionalId: string) {
    return this.patientService.findByProfessional(professionalId);
  }

  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.patientService.findOne(id);
  }

  @Patch(':id')
  update(@Param('id') id: string, @Body() data: any) {
    return this.patientService.update(id, data);
  }

  @Delete(':id')
  deactivate(@Param('id') id: string) {
    return this.patientService.deactivate(id);
  }
}
