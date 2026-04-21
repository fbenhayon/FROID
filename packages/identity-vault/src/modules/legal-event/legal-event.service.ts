import { Injectable, Logger } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { EventType } from './legal-event.constants';
import { computeHash } from '@froid/shared';
import { EventBusService } from '../event-bus/event-bus.service';

export interface CreateLegalEventParams {
  eventType: EventType;
  actorType: 'patient' | 'professional' | 'system' | 'admin';
  actorId: string;
  patientId: string;
  professionalId?: string;
  sessionId?: string;
  relatedConsentId?: string;
  legalTextId: string;
  legalTextVersion: string;
  scope?: string;
  purpose?: string;
  eventContext: string;
  metadata?: Record<string, any>;
}

@Injectable()
export class LegalEventService {
  private readonly logger = new Logger(LegalEventService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly eventBusService: EventBusService,
  ) {}

  async createEvent(params: CreateLegalEventParams) {
    const { metadata, ...restParams } = params;
    const payload = { ...params, timestamp: new Date().toISOString() };
    const hash = computeHash(payload);
    
    // 1. Grava no PostgreSQL
    const savedEvent = await this.prisma.legalEvent.create({
      data: {
        ...restParams,
        metadata: metadata ? metadata : undefined,
        hash,
        blockchainTxId: null,  // Hash Chain preenchera via Event Bus
        integrityStatus: 'valid',
      },
    });

    // 2. Publica no Event Bus (Redis Streams)
    try {
      await this.eventBusService.publish({
        ...savedEvent,
        // Garantimos que campos opcionais que vem como undefined no params
        // mas sao null no DB sejam tratados corretamente
        professionalId: savedEvent.professionalId || undefined,
        sessionId: savedEvent.sessionId || undefined,
        relatedConsentId: savedEvent.relatedConsentId || undefined,
        scope: savedEvent.scope || undefined,
        purpose: savedEvent.purpose || undefined,
      });
    } catch (error: any) {
      this.logger.error(`Failed to publish event ${savedEvent.eventId}: ${error.message}`);
      // Nao falhamos a requisicao principal se o barramento falhar,
      // mas logamos o erro para auditoria posterior.
    }

    return savedEvent;
  }
}
