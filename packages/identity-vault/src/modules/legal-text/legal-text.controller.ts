import { Controller, Get, Post, Put, Body, Param, HttpCode, HttpStatus } from '@nestjs/common';
import { LegalTextService } from './legal-text.service';
import { CreateLegalTextDto } from './legal-text.dto';

@Controller('legal-texts')
export class LegalTextController {
  constructor(private readonly legalTextService: LegalTextService) {}

  // GET /api/legal-texts
  @Get()
  findAll() {
    return this.legalTextService.findAll();
  }

  // GET /api/legal-texts/context/:context
  // IMPORTANTE: rota especifica definida ANTES de :id para evitar conflito
  @Get('context/:context')
  findByContext(@Param('context') context: string) {
    return this.legalTextService.findByContext(context);
  }

  // GET /api/legal-texts/audience/:audience
  @Get('audience/:audience')
  findByAudience(@Param('audience') audience: string) {
    return this.legalTextService.findByAudience(audience);
  }

  // GET /api/legal-texts/:id/versions
  @Get(':id/versions')
  findVersions(@Param('id') id: string) {
    return this.legalTextService.findVersions(id);
  }

  // GET /api/legal-texts/:id
  @Get(':id')
  findOne(@Param('id') id: string) {
    return this.legalTextService.findOne(id);
  }

  // POST /api/legal-texts
  @Post()
  @HttpCode(HttpStatus.CREATED)
  create(@Body() dto: CreateLegalTextDto) {
    return this.legalTextService.create(dto);
  }

  // PUT /api/legal-texts/:id â€” cria nova versao (imutavel)
  @Put(':id')
  createNewVersion(@Param('id') id: string, @Body() dto: CreateLegalTextDto) {
    return this.legalTextService.createNewVersion(id, dto);
  }
}