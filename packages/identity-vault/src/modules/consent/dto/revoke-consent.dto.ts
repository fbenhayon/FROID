import { IsNotEmpty, IsEnum, IsUUID, IsString, IsOptional } from 'class-validator';
import { ConsentScope, VALID_SCOPES } from '../consent.constants';

export class RevokeConsentDto {
  @IsUUID()
  @IsNotEmpty()
  patientId: string;

  @IsEnum(VALID_SCOPES, { message: `scope must be one of: ${VALID_SCOPES.join(', ')}` })
  @IsNotEmpty()
  scope: ConsentScope;

  @IsString()
  @IsOptional()
  reason?: string;
}
