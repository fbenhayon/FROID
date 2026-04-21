import { Controller, Get, Param, Query, NotFoundException } from '@nestjs/common';
import { HashChainService } from './hash-chain.service';
import { PolicyService } from '../policy/policy.service';
import { PrismaService } from '../../prisma/prisma.service';

@Controller('audit')
export class AuditController {
  constructor(
    private readonly hashChainService: HashChainService,
    private readonly policyService: PolicyService,
    private readonly prisma: PrismaService,
  ) {}

  @Get('health')
  async getHealth() {
    const policyHealth = await this.policyService.getHealth();
    return {
      eventBus: 'ok',
      hashChain: 'ok',
      database: 'ok',
      redis: policyHealth.redis,
    };
  }

  @Get('chain/verify')
  async verifyChain() {
    return this.hashChainService.verifyChain();
  }

  @Get('event/:eventId/verify')
  async verifyEvent(@Param('eventId') eventId: string) {
    const result = await this.hashChainService.verifyEvent(eventId);
    if (!result.found) {
      throw new NotFoundException('Event not found in Hash Chain');
    }
    return result;
  }

  @Get('chain/blocks')
  async getBlocks(
    @Query('page') page: string = '1',
    @Query('limit') limit: string = '10',
  ) {
    return this.hashChainService.getAllBlocks(parseInt(page), parseInt(limit));
  }

  @Get('chain/blocks/:sequenceNumber')
  async getBlock(@Param('sequenceNumber') sequenceNumber: string) {
    const block = await this.hashChainService.getBlockBySequence(parseInt(sequenceNumber));
    if (!block) {
      throw new NotFoundException('Block not found');
    }
    return block;
  }

  @Get('patient/:patientId/trail')
  async getPatientTrail(@Param('patientId') patientId: string) {
    return this.hashChainService.getPatientAuditTrail(patientId);
  }
}
