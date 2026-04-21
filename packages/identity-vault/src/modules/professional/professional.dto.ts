import { IsString, IsEmail, IsOptional, IsEnum } from 'class-validator';

export class CreateProfessionalDto {
  @IsString()
  fullName: string;

  @IsString()
  cpf: string;

  @IsEmail()
  email: string;

  @IsString()
  registrationNumber: string;

  @IsEnum(['CRP', 'CRM'])
  registrationType: string;

  @IsOptional()
  @IsString()
  specialty?: string;

  @IsOptional()
  @IsString()
  tenantId?: string;
}

export class UpdateProfessionalDto {
  @IsOptional()
  @IsString()
  fullName?: string;

  @IsOptional()
  @IsEmail()
  email?: string;

  @IsOptional()
  @IsString()
  specialty?: string;

  @IsOptional()
  @IsString()
  registrationNumber?: string;
}