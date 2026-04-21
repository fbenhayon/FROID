import { IsString, IsEmail, IsDateString, IsOptional, IsEnum } from 'class-validator';

export class CreatePatientDto {
  @IsString()
  fullName: string;

  @IsString()
  cpf: string;

  @IsEmail()
  email: string;

  @IsOptional()
  @IsString()
  phone?: string;

  @IsDateString()
  dateOfBirth: string;

  @IsEnum(['M', 'F', 'NB', 'O'])
  gender: string;

  @IsString()
  region: string;

  @IsOptional()
  @IsString()
  guardianId?: string;

  @IsOptional()
  @IsString()
  tenantId?: string;
}

export class UpdatePatientDto {
  @IsOptional()
  @IsString()
  fullName?: string;

  @IsOptional()
  @IsEmail()
  email?: string;

  @IsOptional()
  @IsString()
  phone?: string;

  @IsOptional()
  @IsString()
  region?: string;
}