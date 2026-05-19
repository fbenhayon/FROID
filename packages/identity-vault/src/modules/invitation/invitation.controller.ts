import { Controller, Post, Get, Delete, Body, Param, UsePipes, ValidationPipe } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { InvitationService } from './invitation.service';
import { CreateInvitationDto } from './dto/create-invitation.dto';

@ApiTags('Invitations')
@Controller('invitations')
export class InvitationController {
  constructor(private invitationService: InvitationService) {}

  @Post()
  @ApiOperation({ summary: 'Enviar convite para paciente por email' })
  @ApiResponse({ status: 201, description: 'Convite criado. Retorna link do convite.' })
  @UsePipes(new ValidationPipe({ transform: true, whitelist: true }))
  create(@Body() dto: CreateInvitationDto) {
    return this.invitationService.create(dto);
  }

  @Get('accept/:token')
  @ApiOperation({ summary: 'Aceitar convite (paciente usa este link)' })
  @ApiResponse({ status: 200, description: 'Convite aceito com sucesso' })
  accept(@Param('token') token: string) {
    return this.invitationService.accept(token);
  }

  @Get('professional/:professionalId')
  @ApiOperation({ summary: 'Listar convites enviados por um profissional' })
  findByProfessional(@Param('professionalId') professionalId: string) {
    return this.invitationService.findByProfessional(professionalId);
  }

  @Delete(':id/professional/:professionalId')
  @ApiOperation({ summary: 'Cancelar convite pendente' })
  cancel(
    @Param('id') id: string,
    @Param('professionalId') professionalId: string,
  ) {
    return this.invitationService.cancel(id, professionalId);
  }
}
