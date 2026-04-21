import {
  Injectable,
  Logger,
  NotFoundException,
  BadRequestException,
  ConflictException,
} from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { PolicyService } from '../policy/policy.service';
import { ConsentService } from '../consent/consent.service';
import { LegalEventService } from '../legal-event/legal-event.service';
import { StartSessionDto } from './dto/start-session.dto';
import { EndSessionDto } from './dto/end-session.dto';
import { MarkTopicDto } from './dto/mark-topic.dto';
import { SessionResponseDto } from './dto/session-response.dto';
import { computeHash } from '@froid/shared';

// LegalText ID e version para eventos de sessão
const SESSION_LEGAL_TEXT_ID = 'system_policy';
const SESSION_LEGAL_TEXT_VERSION = '1.0.0';

@Injectable()
export class SessionService {
  private readonly logger = new Logger(SessionService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly policyService: PolicyService,
    private readonly consentService: ConsentService,
    private readonly legalEventService: LegalEventService,
  ) {}

  /**
   * Inicia uma sessão terapêutica.
   * 1. Valida Patient e Professional
   * 2. Avalia PolicyService
   * 3. Captura snapshot de consentimentos
   * 4. Cria Session + SessionConsentSnapshot em transação
   * 5. Emite LegalEvent (SESSION_STARTED ou SESSION_BLOCKED)
   */
  async startSession(dto: StartSessionDto): Promise<SessionResponseDto> {
    this.logger.log(`Starting session: patient=${dto.patientId}, professional=${dto.professionalId}`);

    // 1. Validar Patient
    const patient = await this.prisma.patient.findUnique({
      where: { id: dto.patientId },
    });
    if (!patient) {
      throw new NotFoundException(`Patient not found: ${dto.patientId}`);
    }

    // 2. Validar Professional
    const professional = await this.prisma.professional.findUnique({
      where: { id: dto.professionalId },
    });
    if (!professional) {
      throw new NotFoundException(`Professional not found: ${dto.professionalId}`);
    }

    // 3. Avaliar Policy Engine
    const decision = await this.policyService.evaluate({
      patientId: dto.patientId,
      requestedScopes: dto.requestedScopes,
    });

    // 4. Capturar snapshot de consentimentos
    const consentSummary = await this.consentService.getActiveConsents(dto.patientId);
    const snapshotData = consentSummary.consents;
    const snapshotHash = computeHash(snapshotData);

    const protocol = dto.protocol || 'standard';
    const topicsPlanned = dto.topicsPlanned || [];

    if (decision.allow) {
      // ===== SESSÃO PERMITIDA =====
      const sessionPayload = {
        patientId: dto.patientId,
        professionalId: dto.professionalId,
        requestedScopes: dto.requestedScopes,
        effectiveScopes: decision.effectiveScopes,
        legalState: 'valid',
        status: 'active',
        protocol,
        enabledModules: decision.enabledModules,
        blockedModules: decision.blockedModules,
        topicsPlanned,
        topicsCovered: [],
        consentSnapshot: snapshotData,
        createdBy: dto.professionalId,
        metadata: dto.metadata || null,
      };

      const hash = computeHash(sessionPayload);

      // Transação: cria Session + SessionConsentSnapshot
      const result = await this.prisma.$transaction(async (tx) => {
        const session = await tx.session.create({
          data: {
            ...sessionPayload,
            requestedScopes: sessionPayload.requestedScopes as any,
            effectiveScopes: sessionPayload.effectiveScopes as any,
            enabledModules: sessionPayload.enabledModules as any,
            blockedModules: sessionPayload.blockedModules as any,
            topicsPlanned: sessionPayload.topicsPlanned as any,
            topicsCovered: sessionPayload.topicsCovered as any,
            consentSnapshot: sessionPayload.consentSnapshot as any,
            metadata: sessionPayload.metadata as any,
            hash,
          },
        });

        const snapshot = await tx.sessionConsentSnapshot.create({
          data: {
            sessionId: session.sessionId,
            patientId: dto.patientId,
            snapshotData: snapshotData as any,
            snapshotHash,
            activeScopes: consentSummary.activeScopes as any,
            deniedScopes: consentSummary.deniedScopes as any,
            missingScopes: consentSummary.missingScopes as any,
          },
        });

        return { session, snapshot };
      });

      // Emitir LegalEvent SESSION_STARTED
      await this.legalEventService.createEvent({
        eventType: 'SESSION_STARTED',
        actorType: 'professional',
        actorId: dto.professionalId,
        patientId: dto.patientId,
        professionalId: dto.professionalId,
        sessionId: result.session.sessionId,
        legalTextId: SESSION_LEGAL_TEXT_ID,
        legalTextVersion: SESSION_LEGAL_TEXT_VERSION,
        scope: decision.effectiveScopes.join(','),
        purpose: 'Início de sessão terapêutica',
        eventContext: `Sessão iniciada com protocolo ${protocol}. Escopos efetivos: ${decision.effectiveScopes.join(', ')}`,
        metadata: {
          snapshotHash,
          enabledModules: decision.enabledModules,
          blockedModules: decision.blockedModules,
          protocol,
        },
      });

      this.logger.log(`Session STARTED: ${result.session.sessionId}`);
      return this.toResponseDto(result.session, snapshotHash);

    } else {
      // ===== SESSÃO BLOQUEADA =====
      const blockedPayload = {
        patientId: dto.patientId,
        professionalId: dto.professionalId,
        requestedScopes: dto.requestedScopes,
        effectiveScopes: [],
        legalState: 'blocked',
        status: 'blocked',
        protocol,
        enabledModules: [],
        blockedModules: decision.blockedModules,
        topicsPlanned,
        topicsCovered: [],
        blockReason: decision.blockReason || 'Sessão bloqueada pelo Policy Engine',
        consentSnapshot: snapshotData,
        createdBy: dto.professionalId,
        metadata: dto.metadata || null,
      };

      const hash = computeHash(blockedPayload);

      const blockedSession = await this.prisma.session.create({
        data: {
          ...blockedPayload,
          requestedScopes: blockedPayload.requestedScopes as any,
          effectiveScopes: blockedPayload.effectiveScopes as any,
          enabledModules: blockedPayload.enabledModules as any,
          blockedModules: blockedPayload.blockedModules as any,
          topicsPlanned: blockedPayload.topicsPlanned as any,
          topicsCovered: blockedPayload.topicsCovered as any,
          consentSnapshot: blockedPayload.consentSnapshot as any,
          metadata: blockedPayload.metadata as any,
          hash,
        },
      });

      // Emitir LegalEvent SESSION_BLOCKED
      await this.legalEventService.createEvent({
        eventType: 'SESSION_BLOCKED',
        actorType: 'system',
        actorId: 'policy-engine',
        patientId: dto.patientId,
        professionalId: dto.professionalId,
        sessionId: blockedSession.sessionId,
        legalTextId: SESSION_LEGAL_TEXT_ID,
        legalTextVersion: SESSION_LEGAL_TEXT_VERSION,
        scope: dto.requestedScopes.join(','),
        purpose: 'Sessão bloqueada pelo Policy Engine',
        eventContext: `Sessão bloqueada: ${decision.blockReason}`,
        metadata: {
          snapshotHash,
          blockReason: decision.blockReason,
          requestedScopes: dto.requestedScopes,
        },
      });

      this.logger.warn(`Session BLOCKED: ${blockedSession.sessionId} - ${decision.blockReason}`);
      return this.toResponseDto(blockedSession, snapshotHash);
    }
  }

  /**
   * Encerra uma sessão ativa.
   */
  async endSession(sessionId: string, dto: EndSessionDto): Promise<SessionResponseDto> {
    const session = await this.prisma.session.findUnique({
      where: { sessionId },
    });

    if (!session) {
      throw new NotFoundException(`Session not found: ${sessionId}`);
    }

    if (session.status !== 'active') {
      throw new BadRequestException(`Session is not active. Current status: ${session.status}`);
    }

    const endedAt = new Date();
    const topicsCovered = dto.topicsCovered || (session.topicsCovered as string[]) || [];

    const updatedSession = await this.prisma.session.update({
      where: { sessionId },
      data: {
        status: 'completed',
        endedAt,
        topicsCovered: topicsCovered as any,
        notes: dto.notes || null,
      },
    });

    // Emitir LegalEvent SESSION_ENDED
    await this.legalEventService.createEvent({
      eventType: 'SESSION_ENDED',
      actorType: 'professional',
      actorId: session.professionalId,
      patientId: session.patientId,
      professionalId: session.professionalId,
      sessionId,
      legalTextId: SESSION_LEGAL_TEXT_ID,
      legalTextVersion: SESSION_LEGAL_TEXT_VERSION,
      purpose: 'Encerramento de sessão terapêutica',
      eventContext: `Sessão encerrada. Duração: ${Math.round((endedAt.getTime() - session.startedAt.getTime()) / 60000)} minutos`,
      metadata: {
        topicsCovered,
        durationMinutes: Math.round((endedAt.getTime() - session.startedAt.getTime()) / 60000),
      },
    });

    this.logger.log(`Session ENDED: ${sessionId}`);

    // Buscar snapshot hash
    const snapshot = await this.prisma.sessionConsentSnapshot.findFirst({
      where: { sessionId },
    });

    return this.toResponseDto(updatedSession, snapshot?.snapshotHash);
  }

  /**
   * Marca um tópico como coberto durante sessão multi_topic.
   */
  async markTopic(sessionId: string, dto: MarkTopicDto): Promise<SessionResponseDto> {
    const session = await this.prisma.session.findUnique({
      where: { sessionId },
    });

    if (!session) {
      throw new NotFoundException(`Session not found: ${sessionId}`);
    }

    if (session.status !== 'active') {
      throw new BadRequestException(`Session is not active. Current status: ${session.status}`);
    }

    if (session.protocol !== 'multi_topic') {
      throw new BadRequestException(`Mark topic is only available for multi_topic protocol. Current: ${session.protocol}`);
    }

    const currentTopics = (session.topicsCovered as string[]) || [];
    if (currentTopics.includes(dto.topic)) {
      throw new ConflictException(`Topic already marked: ${dto.topic}`);
    }

    const updatedTopics = [...currentTopics, dto.topic];

    const updatedSession = await this.prisma.session.update({
      where: { sessionId },
      data: {
        topicsCovered: updatedTopics as any,
      },
    });

    this.logger.log(`Topic marked in session ${sessionId}: ${dto.topic}`);

    const snapshot = await this.prisma.sessionConsentSnapshot.findFirst({
      where: { sessionId },
    });

    return this.toResponseDto(updatedSession, snapshot?.snapshotHash);
  }

  /**
   * Busca sessão por ID.
   */
  async getSession(sessionId: string): Promise<SessionResponseDto> {
    const session = await this.prisma.session.findUnique({
      where: { sessionId },
    });

    if (!session) {
      throw new NotFoundException(`Session not found: ${sessionId}`);
    }

    const snapshot = await this.prisma.sessionConsentSnapshot.findFirst({
      where: { sessionId },
    });

    return this.toResponseDto(session, snapshot?.snapshotHash);
  }

  /**
   * Lista sessões por paciente.
   */
  async listSessionsByPatient(patientId: string): Promise<SessionResponseDto[]> {
    const sessions = await this.prisma.session.findMany({
      where: { patientId },
      orderBy: { startedAt: 'desc' },
    });

    const snapshots = await this.prisma.sessionConsentSnapshot.findMany({
      where: { patientId },
    });

    const snapshotMap = new Map(snapshots.map((s) => [s.sessionId, s.snapshotHash]));

    return sessions.map((s) => this.toResponseDto(s, snapshotMap.get(s.sessionId)));
  }

  /**
   * Lista sessões por profissional.
   */
  async listSessionsByProfessional(professionalId: string): Promise<SessionResponseDto[]> {
    const sessions = await this.prisma.session.findMany({
      where: { professionalId },
      orderBy: { startedAt: 'desc' },
    });

    const sessionIds = sessions.map((s) => s.sessionId);
    const snapshots = await this.prisma.sessionConsentSnapshot.findMany({
      where: { sessionId: { in: sessionIds } },
    });

    const snapshotMap = new Map(snapshots.map((s) => [s.sessionId, s.snapshotHash]));

    return sessions.map((s) => this.toResponseDto(s, snapshotMap.get(s.sessionId)));
  }

  /**
   * Retorna o snapshot de consentimentos de uma sessão.
   */
  async getConsentSnapshot(sessionId: string) {
    const snapshot = await this.prisma.sessionConsentSnapshot.findFirst({
      where: { sessionId },
    });

    if (!snapshot) {
      throw new NotFoundException(`Consent snapshot not found for session: ${sessionId}`);
    }

    return snapshot;
  }

  /**
   * Converte entidade Session para DTO de resposta.
   */
  private toResponseDto(session: any, snapshotHash?: string): SessionResponseDto {
    return {
      sessionId: session.sessionId,
      patientId: session.patientId,
      professionalId: session.professionalId,
      status: session.status,
      legalState: session.legalState,
      protocol: session.protocol,
      requestedScopes: (session.requestedScopes as string[]) || [],
      effectiveScopes: (session.effectiveScopes as string[]) || [],
      enabledModules: (session.enabledModules as string[]) || [],
      blockedModules: (session.blockedModules as string[]) || [],
      blockReason: session.blockReason ?? undefined,
      topicsPlanned: (session.topicsPlanned as string[]) || [],
      topicsCovered: (session.topicsCovered as string[]) || [],
      notes: session.notes ?? undefined,
      metadata: (session.metadata as Record<string, any>) ?? undefined,
      consentSnapshotHash: snapshotHash ?? undefined,
      startedAt: session.startedAt.toISOString(),
      endedAt: session.endedAt ? session.endedAt.toISOString() : undefined,
      createdAt: session.createdAt?.toISOString() || session.startedAt.toISOString(),
      updatedAt: session.updatedAt?.toISOString() || session.startedAt.toISOString(),
    };
  }
}
