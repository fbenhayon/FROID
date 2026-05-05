import { Controller, Get, Post, Param, Body, UseGuards } from '@nestjs/common';
import { QuarantineService } from './quarantine.service';

@Controller('quarantine')
export class QuarantineController {
  constructor(private quarantineService: QuarantineService) {}

  @Get()
  listPending() {
    return this.quarantineService.listPending();
  }

  @Post(':id/approve')
  approve(@Param('id') id: string, @Body() data: any) {
    return this.quarantineService.approve(id, data.reviewedBy, data.notes);
  }

  @Post(':id/deny')
  deny(@Param('id') id: string, @Body() data: any) {
    return this.quarantineService.deny(id, data.reviewedBy, data.notes);
  }
}
