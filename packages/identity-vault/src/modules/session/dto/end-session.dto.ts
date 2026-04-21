import { IsString, IsArray, IsOptional } from 'class-validator';

export class EndSessionDto {
  @IsArray()
  @IsString({ each: true })
  @IsOptional()
  topicsCovered?: string[];

  @IsString()
  @IsOptional()
  notes?: string;
}
