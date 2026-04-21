import {
  Controller,
  Post,
  Get,
  Patch,
  Param,
  Body,
  Query,
} from '@nestjs/common';
import { SessionService } from './session.service';
import { StartSessionDto } from './dto/start-session.dto';
import { EndSessionDto } from './dto/end-session.dto';
import { MarkTopicDto } from './dto/mark-topic.dto';

@Controller('sessions')
export class SessionController {
  constructor(private readonly sessionService: SessionService) {}

  /**
   * POST /sessions/start
   * Inicia uma nova sessão terapêutica
   */
  @Post('start')
  async startSession(@Body() dto: StartSessionDto) {
    return this.sessionService.startSession(dto);
  }

  /**
   * GET /sessions/patient/:patientId
   * Lista sessões de um paciente
   * IMPORTANTE: rotas estáticas ANTES de :sessionId
   */
  @Get('patient/:patientId')
  async listByPatient(@Param('patientId') patientId: string) {
    return this.sessionService.listSessionsByPatient(patientId);
  }

  /**
   * GET /sessions/professional/:professionalId
   * Lista sessões de um profissional
   */
  @Get('professional/:professionalId')
  async listByProfessional(@Param('professionalId') professionalId: string) {
    return this.sessionService.listSessionsByProfessional(professionalId);
  }

  /**
   * GET /sessions/:sessionId/snapshot
   * Retorna o snapshot de consentimentos da sessão
   */
  @Get(':sessionId/snapshot')
  async getSnapshot(@Param('sessionId') sessionId: string) {
    return this.sessionService.getConsentSnapshot(sessionId);
  }

  /**
   * GET /sessions/:sessionId
   * Busca sessão por ID
   * IMPORTANTE: rota dinâmica por ÚLTIMO entre os GETs
   */
  @Get(':sessionId')
  async getSession(@Param('sessionId') sessionId: string) {
    return this.sessionService.getSession(sessionId);
  }

  /**
   * PATCH /sessions/:sessionId/end
   * Encerra uma sessão ativa
   */
  @Patch(':sessionId/end')
  async endSession(
    @Param('sessionId') sessionId: string,
    @Body() dto: EndSessionDto,
  ) {
    return this.sessionService.endSession(sessionId, dto);
  }

  /**
   * PATCH /sessions/:sessionId/topic
   * Marca tópico como coberto (multi_topic protocol)
   */
  @Patch(':sessionId/topic')
  async markTopic(
    @Param('sessionId') sessionId: string,
    @Body() dto: MarkTopicDto,
  ) {
    return this.sessionService.markTopic(sessionId, dto);
  }
}
