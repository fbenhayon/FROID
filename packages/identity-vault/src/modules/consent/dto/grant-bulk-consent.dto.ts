import { IsString, IsNotEmpty, IsEnum, IsOptional, IsUUID, IsArray, ArrayNotEmpty } from 'class-validator';
import { ConsentScope, VALID_SCOPES } from '../consent.constants';

export class GrantBulkConsentDto {
  @IsUUID()
  @IsNotEmpty()
  patientId: string;

  @IsUUID()
  @IsOptional()
  professionalId?: string;

  @IsUUID()
  @IsOptional()
  sessionId?: string;

  @IsArray()
  @ArrayNotEmpty()
  @IsEnum(VALID_SCOPES, { each: true, message: `each scope must be one of: ${VALID_SCOPES.join(', ')}` })
  scopes: ConsentScope[];

  @IsString()
  @IsNotEmpty()
  purpose: string;

  @IsEnum(['signup', 'session', 'settings'])
  @IsNotEmpty()
  collectionContext: 'signup' | 'session' | 'settings';
}
