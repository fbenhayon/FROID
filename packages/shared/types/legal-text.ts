/**
 * FROID v3.0 - Shared Types
 * LegalText interfaces e enums
 */

export type LegalTextType = 'notice' | 'consent' | 'warning' | 'policy' | 'term';

export type AudienceType = 'patient' | 'professional' | 'guardian';

export type ContextType =
  | 'signup'
  | 'first_access'
  | 'pre_session'
  | 'report'
  | 'sharing'
  | 'privacy_center';

export interface LegalBasisEntry {
  chapter: string;
  article: string;
  paragraph: string | null;
  tag: string;
}

export interface LegalText {
  legalTextId: string;
  title: string;
  type: LegalTextType;
  audience: AudienceType;
  context: ContextType;
  shortText: string;
  expandedText: string;
  version: string;
  isBlocking: boolean;
  requiresAction: boolean;
  requiresSignature: boolean;
  showCitationInline: boolean; // sempre false na UI principal
  showCitationDetails: boolean; // visivel na central de privacidade
  effectiveFrom: Date;
  effectiveTo: Date | null;
  supersedes: string | null;
  legalBasis: LegalBasisEntry[];
  uiComponent: string;
  enforcementRuleId: string;
  createdAt: Date;
  updatedAt: Date;
}