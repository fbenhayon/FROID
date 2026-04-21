export interface PolicyDecision {
  allow: boolean;
  effectiveScopes: string[];
  enabledModules: string[];
  blockedModules: string[];
  blockReason?: string;
  evaluatedAt: string;
  fromCache: boolean;
  cacheExpiresAt: string;
}
