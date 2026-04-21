import { IsArray, IsString, IsNotEmpty, ArrayMinSize } from 'class-validator';

export class EvaluatePolicyDto {
  @IsString()
  @IsNotEmpty()
  patientId: string;

  @IsArray()
  @IsString({ each: true })
  @ArrayMinSize(1)
  requestedScopes: string[];
}
