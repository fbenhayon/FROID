import {
  Controller,
  Post,
  Get,
  Patch,
  Body,
  Param,
  UseGuards,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiBearerAuth } from '@nestjs/swagger';
import { SessionService } from './session.service';
import { JwtAuthGuard } from '../../auth/jwt-auth.guard';

@ApiTags('Sessions')
@ApiBearerAuth('JWT-auth')
@Controller('sessions')
@UseGuards(JwtAuthGuard)
export class SessionController {
  constructor(private sessionService: SessionService) {}

  @Post()
  @ApiOperation({ summary: 'Criar nova sessão' })
  createSession(@Body() body: any) {
    return this.sessionService.createSession(body);
  }

  @Patch(':id/start')
  @ApiOperation({ summary: 'Iniciar sessão (ativa captura)' })
  startSession(@Param('id') id: string) {
    return this.sessionService.startSession(id);
  }

  @Patch(':id/end')
  @ApiOperation({ summary: 'Finalizar sessão' })
  endSession(@Param('id') id: string, @Body() body: { notes?: string }) {
    return this.sessionService.endSession(id, body.notes);
  }

  @Post(':id/analyze-voice')
  @ApiOperation({ summary: 'Enviar áudio para análise' })
  analyzeVoice(@Param('id') id: string, @Body() body: any) {
    return this.sessionService.analyzeVoice(id, body.audioData);
  }

  @Post(':id/analyze-face')
  @ApiOperation({ summary: 'Enviar frame de vídeo para análise' })
  analyzeFace(@Param('id') id: string, @Body() body: any) {
    return this.sessionService.analyzeFace(id, body.imageData);
  }

  @Get(':id/results')
  @ApiOperation({ summary: 'Obter resultados da sessão' })
  getSessionResults(@Param('id') id: string) {
    return this.sessionService.getSessionResults(id);
  }

  @Get('patient/:patientId')
  @ApiOperation({ summary: 'Listar sessões de um paciente' })
  getPatientSessions(@Param('patientId') patientId: string) {
    return this.sessionService.getPatientSessions(patientId);
  }
}
