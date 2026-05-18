import { IsString, IsOptional } from 'class-validator';

export class CreateProfessionalDto {
  @IsString()
  userId: string;

  @IsString()
  name: string;

  @IsString()
  crp: string;

  @IsString()
  specialty: string;

  @IsOptional()
  @IsString()
  phone?: string;
}

export class UpdateProfessionalDto {
  @IsOptional()
  @IsString()
  name?: string;

  @IsOptional()
  @IsString()
  specialty?: string;

  @IsOptional()
  @IsString()
  phone?: string;
}
