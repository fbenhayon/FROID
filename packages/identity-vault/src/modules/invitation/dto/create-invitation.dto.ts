import { IsEmail, IsString, IsOptional } from 'class-validator';

export class CreateInvitationDto {
  @IsString()
  professionalId: string;

  @IsEmail({}, { message: 'Email do paciente inválido' })
  patientEmail: string;

  @IsOptional()
  @IsString()
  message?: string;
}
