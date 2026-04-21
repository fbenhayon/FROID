import { IsString, IsNotEmpty, IsOptional, IsDateString } from 'class-validator';

export class MarkTopicDto {
  @IsString()
  @IsNotEmpty()
  topic: string;

  @IsDateString()
  @IsOptional()
  timestamp?: string;
}
