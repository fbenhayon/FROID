import { Injectable, NotFoundException, ConflictException, BadRequestException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { RequestContext } from '../../middleware/request-context.middleware';
import { LegalEventService } from '../legal-event/legal-event.service';
import { GrantConsentDto } from './dto/grant-consent.dto';
import { RevokeConsentDto } from './dto/revoke-consent.dto';
import { ConsentScope, SCOPE_TO_LEGAL_TEXT, VALID_SCOPES } from './consent.constants';
import { computeHash } from '@froid/shared';

export interface ActiveConsentSummary {
  patientId: string;
  activeScopes: ConsentScope[];
  deniedScopes: ConsentScope[];
  missingScopes: ConsentScope[];
  consents: any[];
  timestamp: string;
}

@Injectable()
export class ConsentService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly legalEventService: LegalEventService,
  ) {}

  async grantConsent(dto: GrantConsentDto, req: RequestContext) {
    if (!VALID_SCOPES.includes(dto.scope)) {
      throw new BadRequestException('Invalid scope');
    }

    const patient = await this.prisma.patient.findUnique({
      where: { id: dto.patientId },
    });
    if (!patient) throw new NotFoundException('Patient not found');

    const legalTextId = SCOPE_TO_LEGAL_TEXT[dto.scope];
    const legalText = await this.prisma.legalText.findFirst({
      where: { legalTextId, effectiveTo: null },
      orderBy: { createdAt: 'desc' },
    });

    if (!legalText) throw new NotFoundException('Active Legal Text not found for scope');

    const activeConsent = await this.prisma.consentRecord.findFirst({
      where: {
        patientId: dto.patientId,
        scope: dto.scope,
        status: 'granted',
        revokedAt: null,
      },
    });

    if (activeConsent) {
      throw new ConflictException('Consentimento já ativo para este escopo');
    }

    const payload = {
      patientId: dto.patientId,
      professionalId: dto.professionalId || null,
      sessionId: dto.sessionId || null,
      scope: dto.scope,
      purpose: dto.purpose,
      status: 'granted',
      legalTextId: legalText.legalTextId,
      legalTextVersion: legalText.version,
      collectionContext: dto.collectionContext,
      ipAddress: req.ipAddress,
      userAgent: req.userAgent,
      geoLocation: req.geoLocation,
      blockchainTxId: null,
      legalBasisSnapshot: legalText.legalBasis,
      processingPurpose: dto.purpose,
      dataOrigin: 'user_input',
      processingType: 'collection',
      createdBy: dto.patientId, 
    };

    const hash = computeHash(payload);

    const consentRecord = await this.prisma.consentRecord.create({
      data: {
        ...payload,
        hash,
        legalBasisSnapshot: legalText.legalBasis as any,
      },
    });

    await this.legalEventService.createEvent({
      eventType: 'CONSENT_GRANTED',
      actorType: 'patient',
      actorId: dto.patientId,
      patientId: dto.patientId,
      professionalId: dto.professionalId,
      sessionId: dto.sessionId,
      relatedConsentId: consentRecord.consentId,
      legalTextId: legalText.legalTextId,
      legalTextVersion: legalText.version,
      scope: dto.scope,
      purpose: dto.purpose,
      eventContext: 'Concessão voluntária pelo titular',
    });

    return consentRecord;
  }

  async denyConsent(dto: GrantConsentDto, req: RequestContext) {
    if (!VALID_SCOPES.includes(dto.scope)) {
      throw new BadRequestException('Invalid scope');
    }

    const patient = await this.prisma.patient.findUnique({
      where: { id: dto.patientId },
    });
    if (!patient) throw new NotFoundException('Patient not found');

    const legalTextId = SCOPE_TO_LEGAL_TEXT[dto.scope];
    const legalText = await this.prisma.legalText.findFirst({
      where: { legalTextId, effectiveTo: null },
      orderBy: { createdAt: 'desc' },
    });

    if (!legalText) throw new NotFoundException('Active Legal Text not found for scope');

    const payload = {
      patientId: dto.patientId,
      professionalId: dto.professionalId || null,
      sessionId: dto.sessionId || null,
      scope: dto.scope,
      purpose: dto.purpose,
      status: 'denied',
      legalTextId: legalText.legalTextId,
      legalTextVersion: legalText.version,
      collectionContext: dto.collectionContext,
      ipAddress: req.ipAddress,
      userAgent: req.userAgent,
      geoLocation: req.geoLocation,
      blockchainTxId: null,
      legalBasisSnapshot: legalText.legalBasis,
      processingPurpose: dto.purpose,
      dataOrigin: 'user_input',
      processingType: 'collection',
      createdBy: dto.patientId, 
    };

    const hash = computeHash(payload);

    const consentRecord = await this.prisma.consentRecord.create({
      data: {
        ...payload,
        hash,
        legalBasisSnapshot: legalText.legalBasis as any,
      },
    });

    await this.legalEventService.createEvent({
      eventType: 'CONSENT_DENIED',
      actorType: 'patient',
      actorId: dto.patientId,
      patientId: dto.patientId,
      professionalId: dto.professionalId,
      sessionId: dto.sessionId,
      relatedConsentId: consentRecord.consentId,
      legalTextId: legalText.legalTextId,
      legalTextVersion: legalText.version,
      scope: dto.scope,
      purpose: dto.purpose,
      eventContext: 'Recusa explícita pelo titular',
    });

    return consentRecord;
  }

  async revokeConsent(dto: RevokeConsentDto, req: RequestContext) {
    const activeConsent = await this.prisma.consentRecord.findFirst({
      where: {
        patientId: dto.patientId,
        scope: dto.scope,
        status: 'granted',
        revokedAt: null,
      },
    });

    if (!activeConsent) {
      throw new NotFoundException('Nenhum consentimento ativo para este escopo');
    }

    const revokedAt = new Date();
    
    // Calcula um novo hash para refletir a atualizacao
    const updatePayload = {
      ...activeConsent,
      status: 'revoked',
      revokedAt: revokedAt.toISOString(),
      updatedAt: revokedAt.toISOString()
    };
    
    // Removemos os campos nao confiaveis no payload do hash dinamico
    delete updatePayload.hash;
    
    const newHash = computeHash(updatePayload);

    const consentRecord = await this.prisma.consentRecord.update({
      where: { consentId: activeConsent.consentId },
      data: {
        status: 'revoked',
        revokedAt,
        hash: newHash,
      },
    });

    await this.legalEventService.createEvent({
      eventType: 'CONSENT_REVOKED',
      actorType: 'patient',
      actorId: dto.patientId,
      patientId: dto.patientId,
      relatedConsentId: consentRecord.consentId,
      legalTextId: consentRecord.legalTextId,
      legalTextVersion: consentRecord.legalTextVersion,
      scope: dto.scope,
      eventContext: dto.reason || 'Revogação voluntária pelo titular',
    });

    return consentRecord;
  }

  async getActiveConsents(patientId: string): Promise<ActiveConsentSummary> {
    const allConsents = await this.prisma.consentRecord.findMany({
      where: { patientId },
      orderBy: { grantedAt: 'asc' },
    });

    const now = new Date();
    const activeConsents = allConsents.filter(
      (c) =>
        c.status === 'granted' &&
        c.revokedAt === null &&
        (c.expiresAt === null || c.expiresAt > now),
    );

    const activeScopes = activeConsents.map((c) => c.scope as ConsentScope);
    
    const deniedMap = new Map<string, boolean>();
    const grantMap = new Map<string, boolean>();

    for (const c of allConsents) {
      if (c.status === 'granted' && c.revokedAt === null && (c.expiresAt === null || c.expiresAt > now)) {
        grantMap.set(c.scope, true);
        deniedMap.set(c.scope, false);
      } else if (c.status === 'denied') {
        deniedMap.set(c.scope, true);
      } else if (c.status === 'revoked') {
        grantMap.set(c.scope, false);
      }
    }

    const deniedScopes = Array.from(deniedMap.entries())
      .filter(([scope, isDenied]) => isDenied && !grantMap.get(scope))
      .map(([scope]) => scope as ConsentScope);

    const missingScopes = VALID_SCOPES.filter(
      (scope) => !activeScopes.includes(scope) && !deniedScopes.includes(scope),
    );

    return {
      patientId,
      activeScopes,
      deniedScopes,
      missingScopes,
      // Retorna TODOS os registros (incluindo revogados) para que o PolicyService
      // possa detectar escopos revogados ao avaliar decisões de autorização.
      consents: allConsents,
      timestamp: new Date().toISOString(),
    };
  }

  async getConsentHistory(patientId: string, scope?: string) {
    const whereClause: any = { patientId };
    if (scope) {
      whereClause.scope = scope;
    }

    return this.prisma.consentRecord.findMany({
      where: whereClause,
      orderBy: { grantedAt: 'desc' },
    });
  }

  async getConsentById(consentId: string) {
    const consent = await this.prisma.consentRecord.findUnique({
      where: { consentId }
    });
    if (!consent) throw new NotFoundException('Consent not found');
    return consent;
  }
}
