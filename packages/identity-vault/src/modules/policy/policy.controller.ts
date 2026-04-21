import { Controller, Post, Body, Get, Param, Delete, HttpCode, HttpStatus } from '@nestjs/common';
import { PolicyService } from './policy.service';
import { EvaluatePolicyDto } from './dto/evaluate-policy.dto';
import { PolicyDecision } from './dto/policy-decision.dto';

@Controller('policy')
export class PolicyController {
  constructor(private readonly policyService: PolicyService) {}

  @Post('evaluate')
  @HttpCode(HttpStatus.OK)
  async evaluate(@Body() dto: EvaluatePolicyDto): Promise<PolicyDecision> {
    return this.policyService.evaluate(dto);
  }

  @Get('modules/:patientId')
  async getModules(@Param('patientId') patientId: string) {
    return this.policyService.getModulesForPatient(patientId);
  }

  @Delete('cache/:patientId')
  @HttpCode(HttpStatus.NO_CONTENT)
  async invalidateCache(@Param('patientId') patientId: string): Promise<void> {
    await this.policyService.invalidateCache(patientId);
  }

  @Get('health')
  async checkHealth() {
    const health = await this.policyService.getHealth();
    return { status: 'ok', ...health };
  }
}
