import {
  IsString,
  IsNotEmpty,
  IsArray,
  IsOptional,
  ArrayMinSize,
  IsIn,
} from 'class-validator';

export class StartSessionDto {
  @IsString()
  @IsNotEmpty()
  patientId: string;

  @IsString()
  @IsNotEmpty()
  professionalId: string;

  @IsArray()
  @IsString({ each: true })
  @ArrayMinSize(1)
  requestedScopes: string[];

  @IsString()
  @IsOptional()
  @IsIn(['standard', 'multi_topic', 'crisis', 'assessment'])
  protocol?: string;

  @IsArray()
  @IsString({ each: true })
  @IsOptional()
  topicsPlanned?: string[];

  @IsOptional()
  metadata?: Record<string, any>;
}
