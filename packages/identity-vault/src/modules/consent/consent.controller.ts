import { Controller, Post, Get, Body, Param, Req, Query } from '@nestjs/common';
import { Request } from 'express';
import { ConsentService } from './consent.service';
import { GrantConsentDto } from './dto/grant-consent.dto';
import { RevokeConsentDto } from './dto/revoke-consent.dto';
import { GrantBulkConsentDto } from './dto/grant-bulk-consent.dto';

@Controller('consents')
export class ConsentController {
  constructor(private readonly consentService: ConsentService) {}

  @Post('grant')
  async grantConsent(@Body() dto: GrantConsentDto, @Req() req: Request) {
    return this.consentService.grantConsent(dto, (req as any).context);
  }

  @Post('deny')
  async denyConsent(@Body() dto: GrantConsentDto, @Req() req: Request) {
    return this.consentService.denyConsent(dto, (req as any).context);
  }

  @Post('revoke')
  async revokeConsent(@Body() dto: RevokeConsentDto, @Req() req: Request) {
    return this.consentService.revokeConsent(dto, (req as any).context);
  }

  @Post('grant-bulk')
  async grantBulkConsent(@Body() dto: GrantBulkConsentDto, @Req() req: Request) {
    const results = [];
    for (const scope of dto.scopes) {
      const singleDto: GrantConsentDto = {
        patientId: dto.patientId,
        professionalId: dto.professionalId,
        sessionId: dto.sessionId,
        scope,
        purpose: dto.purpose,
        collectionContext: dto.collectionContext,
      };
      
      try {
        const result = await this.consentService.grantConsent(singleDto, (req as any).context);
        results.push({ scope, status: 'success', data: result });
      } catch (error: any) {
        results.push({ scope, status: 'failed', error: error.message });
      }
    }
    return results;
  }

  @Get('active/:patientId')
  async getActiveConsents(@Param('patientId') patientId: string) {
    return this.consentService.getActiveConsents(patientId);
  }

  @Get('history/:patientId')
  async getConsentHistory(@Param('patientId') patientId: string, @Query('scope') scope?: string) {
    return this.consentService.getConsentHistory(patientId, scope);
  }

  @Get(':consentId')
  async getSingleConsent(@Param('consentId') consentId: string) {
    return this.consentService.getConsentById(consentId);
  }
}
