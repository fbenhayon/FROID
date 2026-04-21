import {
  IsString,
  IsBoolean,
  IsOptional,
  IsArray,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';

export class LegalBasisEntryDto {
  @IsString()
  chapter: string;

  @IsString()
  article: string;

  @IsOptional()
  @IsString()
  paragraph?: string | null;

  @IsString()
  tag: string;
}

export class CreateLegalTextDto {
  @IsString()
  legalTextId: string;

  @IsString()
  title: string;

  @IsString()
  type: string;

  @IsString()
  audience: string;

  @IsString()
  context: string;

  @IsString()
  shortText: string;

  @IsString()
  expandedText: string;

  @IsString()
  version: string;

  @IsOptional()
  @IsBoolean()
  isBlocking?: boolean;

  @IsOptional()
  @IsBoolean()
  requiresAction?: boolean;

  @IsOptional()
  @IsBoolean()
  requiresSignature?: boolean;

  @IsOptional()
  @IsBoolean()
  showCitationInline?: boolean;

  @IsOptional()
  @IsBoolean()
  showCitationDetails?: boolean;

  @IsOptional()
  @IsString()
  supersedes?: string;

  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => LegalBasisEntryDto)
  legalBasis: LegalBasisEntryDto[];

  @IsString()
  uiComponent: string;

  @IsString()
  enforcementRuleId: string;
}