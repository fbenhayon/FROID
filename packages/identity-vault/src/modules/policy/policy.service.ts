import { Injectable, Logger } from '@nestjs/common';
import { PolicyCacheService } from './redis-cache.service';
import { EvaluatePolicyDto } from './dto/evaluate-policy.dto';
import { PolicyDecision } from './dto/policy-decision.dto';
import { ConsentService } from '../consent/consent.service';

// Mapeamento de escopos para módulos FROID
const SCOPE_TO_MODULE: Record<string, string> = {
  audio_recording: 'froid-voice',
  video_recording: 'froid-face',
  voice_analysis:  'froid-voice',
  facial_analysis: 'froid-face',
  transcription:   'froid-transcribe',
  ai_report:       'froid-nlp',
  benchmark:       'feature-extractor',
};

const ALL_MODULES = [
  'froid-voice',
  'froid-face',
  'froid-transcribe',
  'froid-nlp',
  'froid-fusion',
  'feature-extractor',
];

@Injectable()
export class PolicyService {
  private readonly logger = new Logger(PolicyService.name);

  constructor(
    private readonly policyCache: PolicyCacheService,
    private readonly consentService: ConsentService,
  ) {}

  async evaluate(dto: EvaluatePolicyDto): Promise<PolicyDecision> {
    // 1. Tenta carregar do cache
    const cached = await this.policyCache.getDecision(dto.patientId, dto.requestedScopes);
    if (cached) {
      this.logger.debug(`Cache hit for patient ${dto.patientId}`);
      return {
        ...cached,
        fromCache: true,
      };
    }

    this.logger.debug(`Cache miss for patient ${dto.patientId}. Evaluating via embedded policy engine...`);

    // 2. Buscar histórico de consentimentos
    const summary = await this.consentService.getActiveConsents(dto.patientId);
    
    // Mapear o status mais recente para cada escopo
    const latestStatusMap = new Map<string, string>();
    // Ordenar por grantedAt desc para garantir que o primeiro de cada escopo seja o mais recente
    const sortedConsents = [...summary.consents].sort((a, b) => 
      new Date(b.grantedAt).getTime() - new Date(a.grantedAt).getTime()
    );

    for (const c of sortedConsents) {
      if (!latestStatusMap.has(c.scope)) {
        latestStatusMap.set(c.scope, c.status);
      }
    }

    // 3. Calcular effective scopes and check for revocations among REQUESTED scopes
    const effectiveScopes: string[] = [];
    let hasRevocation = false;
    let explicitDenial = false;

    for (const scope of dto.requestedScopes) {
      const status = latestStatusMap.get(scope);
      if (status === 'granted') {
        effectiveScopes.push(scope);
      } else if (status === 'revoked') {
        hasRevocation = true;
      } else if (status === 'denied') {
        explicitDenial = true;
      }
    }

    // 4. Mapear escopos para módulos
    const enabledModules = [...new Set(
      effectiveScopes.map(s => SCOPE_TO_MODULE[s]).filter(Boolean),
    )];
    const blockedModules = ALL_MODULES.filter(m => !enabledModules.includes(m));

    // 5. Decisão final
    // Regra FROID: Se QUALQUER escopo solicitado estiver revogado, bloqueia tudo (LGPD compliance rigoroso)
    // Se não houver revogação mas também nada concedido, bloqueia por falta de interseção
    const allow = effectiveScopes.length > 0 && !hasRevocation;
    let blockReason = 'Permitido';
    
    if (!allow) {
      if (hasRevocation) {
        blockReason = 'Escopo revogado pelo titular';
      } else if (explicitDenial) {
        blockReason = 'Escopo negado pelo titular';
      } else if (effectiveScopes.length === 0) {
        blockReason = 'Nenhum escopo valido na intersecao';
      }
    }

    const decision: PolicyDecision = {
      allow,
      effectiveScopes,
      enabledModules,
      blockedModules,
      blockReason,
      evaluatedAt: new Date().toISOString(),
      fromCache: false,
      cacheExpiresAt: new Date(Date.now() + 60000).toISOString(),
    };

    this.logger.debug(`Decision for ${dto.patientId}: allow=${allow}, reason=${blockReason}, scopes=${effectiveScopes.join(',')}`);

    // 7. Salva no cache
    await this.policyCache.saveDecision(dto.patientId, dto.requestedScopes, decision);

    return decision;
  }

  async getModulesForPatient(patientId: string): Promise<{ enabledModules: string[]; blockedModules: string[] }> {
    const summary = await this.consentService.getActiveConsents(patientId);

    const enabledModules = [...new Set(
      summary.activeScopes.map((s: string) => SCOPE_TO_MODULE[s]).filter(Boolean),
    )];
    const blockedModules = ALL_MODULES.filter(m => !enabledModules.includes(m));

    return { enabledModules, blockedModules };
  }

  async invalidateCache(patientId: string): Promise<void> {
    await this.policyCache.invalidateForPatient(patientId);
  }

  async getHealth(): Promise<{ opa: string; redis: string }> {
    return { opa: 'embedded', redis: 'ok' };
  }
}
