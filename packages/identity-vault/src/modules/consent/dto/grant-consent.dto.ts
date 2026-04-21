import { IsString, IsNotEmpty, IsEnum, IsOptional, IsUUID } from 'class-validator';
import { ConsentScope, VALID_SCOPES } from '../consent.constants';

export class GrantConsentDto {
  @IsUUID()
  @IsNotEmpty()
  patientId: string;

  @IsUUID()
  @IsOptional()
  professionalId?: string;

  @IsUUID()
  @IsOptional()
  sessionId?: string;

  @IsEnum(VALID_SCOPES, { message: `scope must be one of: ${VALID_SCOPES.join(', ')}` })
  @IsNotEmpty()
  scope: ConsentScope;

  @IsString()
  @IsNotEmpty()
  purpose: string;

  @IsEnum(['signup', 'session', 'settings'])
  @IsNotEmpty()
  collectionContext: 'signup' | 'session' | 'settings';
}
