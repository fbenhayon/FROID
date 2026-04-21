import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { CreateLegalTextDto } from './legal-text.dto';

@Injectable()
export class LegalTextService {
  constructor(private readonly prisma: PrismaService) {}

  // GET /api/legal-texts â€” apenas textos ativos (effectiveTo = null)
  async findAll() {
    return this.prisma.legalText.findMany({
      where: { effectiveTo: null },
      orderBy: { createdAt: 'desc' },
    });
  }

  // GET /api/legal-texts/:id
  async findOne(id: string) {
    const text = await this.prisma.legalText.findUnique({
      where: { legalTextId: id },
    });
    if (!text) {
      throw new NotFoundException('Texto juridico nao encontrado: ' + id);
    }
    return text;
  }

  // GET /api/legal-texts/:id/versions â€” historico completo (percorre cadeia supersedes)
  async findVersions(id: string) {
    const allTexts = await this.prisma.legalText.findMany({
      orderBy: { effectiveFrom: 'desc' },
    });

    const chain: typeof allTexts = [];
    let currentId: string | null = id;

    while (currentId) {
      const found = allTexts.find((t) => t.legalTextId === currentId);
      if (!found) break;
      chain.push(found);
      currentId = found.supersedes;
    }

    return chain;
  }

  // POST /api/legal-texts
  async create(dto: CreateLegalTextDto) {
    return this.prisma.legalText.create({
      data: {
        ...dto,
        legalBasis: dto.legalBasis as any,
      },
    });
  }

  // PUT /api/legal-texts/:id â€” versionamento imutavel
  // Cria nova versao, marca anterior com effectiveTo e supersedes
  async createNewVersion(id: string, dto: CreateLegalTextDto) {
    await this.findOne(id); // garante que o texto atual existe
    const now = new Date();

    // 1. Marcar versao atual como superseded (imutavel â€” nao altera conteudo)
    await this.prisma.legalText.update({
      where: { legalTextId: id },
      data: { effectiveTo: now },
    });

    // 2. Criar nova versao com ID derivado
    const newId = id + '_v' + dto.version.replace(/\./g, '_');
    return this.prisma.legalText.create({
      data: {
        ...dto,
        legalTextId: newId,
        supersedes: id,
        legalBasis: dto.legalBasis as any,
        effectiveFrom: now,
      },
    });
  }

  // GET /api/legal-texts/context/:context
  async findByContext(context: string) {
    return this.prisma.legalText.findMany({
      where: { context, effectiveTo: null },
      orderBy: { createdAt: 'asc' },
    });
  }

  // GET /api/legal-texts/audience/:audience
  async findByAudience(audience: string) {
    return this.prisma.legalText.findMany({
      where: { audience, effectiveTo: null },
      orderBy: { createdAt: 'asc' },
    });
  }
}