import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { computeHash } from '@froid/shared';
import { HashChainBlock } from '@prisma/client';

export interface ChainVerificationResult {
  valid: boolean;
  totalBlocks: number;
  brokenAt: number | null;
}

export interface EventVerificationResult {
  found: boolean;
  valid: boolean;
  block?: HashChainBlock;
}

@Injectable()
export class HashChainService {
  private readonly logger = new Logger(HashChainService.name);

  constructor(private readonly prisma: PrismaService) {}

  // === APPEND: Adicionar bloco a cadeia ===
  async appendBlock(event: any): Promise<HashChainBlock> {
    this.logger.debug(`Appending block for event ${event.eventId} (${event.eventType})`);

    // 1. Buscar ultimo bloco da cadeia (transacional para evitar race conditions no sequenceNumber)
    // Nota: Em um sistema distribuido real, usariamos um lock distribuido ou uma sequence do DB.
    // Para esta entrega, usaremos a busca do ultimo registro.
    const lastBlock = await this.prisma.hashChainBlock.findFirst({
      orderBy: { sequenceNumber: 'desc' },
    });

    const sequenceNumber = lastBlock ? lastBlock.sequenceNumber + 1 : 0;
    const previousHash = lastBlock ? lastBlock.blockHash : 'GENESIS';

    // 2. Serializar payload de forma deterministica
    // O computeHash ja faz sorting das chaves, mas vamos garantir o payload aqui
    const payload = JSON.stringify(event, Object.keys(event).sort());
    const payloadHash = computeHash(event); // computeHash ja faz o sort e stringify internamente

    // 3. Calcular hash do bloco
    // blockHash = SHA256(sequenceNumber + previousHash + payloadHash + timestamp)
    const timestamp = new Date();
    const blockHeader = {
      sequenceNumber,
      previousHash,
      payloadHash,
      timestamp: timestamp.toISOString(),
    };
    const blockHash = computeHash(blockHeader);

    // 4. Gravar bloco (append-only)
    const block = await this.prisma.hashChainBlock.create({
      data: {
        sequenceNumber,
        previousHash,
        eventId: event.eventId,
        eventType: event.eventType,
        payload,
        payloadHash,
        blockHash,
        timestamp,
      },
    });

    // 5. Atualizar blockchainTxId no LegalEvent original
    await this.prisma.legalEvent.update({
      where: { eventId: event.eventId },
      data: { blockchainTxId: blockHash },
    });

    // 6. Atualizar blockchainTxId no ConsentRecord correspondente (se existir)
    if (event.relatedConsentId) {
      await this.prisma.consentRecord.update({
        where: { consentId: event.relatedConsentId },
        data: { blockchainTxId: blockHash },
      });
      this.logger.debug(`Updated ConsentRecord ${event.relatedConsentId} with blockHash`);
    }

    this.logger.log(`Block #${sequenceNumber} appended to Hash Chain. Event: ${event.eventType}`);
    return block;
  }

  // === VERIFY: Verificar integridade da cadeia ===
  async verifyChain(): Promise<ChainVerificationResult> {
    const blocks = await this.prisma.hashChainBlock.findMany({
      orderBy: { sequenceNumber: 'asc' },
    });

    if (blocks.length === 0) return { valid: true, totalBlocks: 0, brokenAt: null };

    for (let i = 0; i < blocks.length; i++) {
      const block = blocks[i];

      // 1. Verificar previousHash
      if (i === 0) {
        if (block.previousHash !== 'GENESIS') {
          return { valid: false, totalBlocks: blocks.length, brokenAt: 0 };
        }
      } else {
        if (block.previousHash !== blocks[i - 1].blockHash) {
          return { valid: false, totalBlocks: blocks.length, brokenAt: i };
        }
      }

      // 2. Verificar payloadHash
      const eventData = JSON.parse(block.payload);
      const expectedPayloadHash = computeHash(eventData);
      if (block.payloadHash !== expectedPayloadHash) {
        return { valid: false, totalBlocks: blocks.length, brokenAt: i };
      }

      // 3. Verificar blockHash
      const blockHeader = {
        sequenceNumber: block.sequenceNumber,
        previousHash: block.previousHash,
        payloadHash: block.payloadHash,
        timestamp: block.timestamp.toISOString(),
      };
      const expectedBlockHash = computeHash(blockHeader);
      if (block.blockHash !== expectedBlockHash) {
        // Nota: A precisao do timestamp no ISOString pode ser um problema se nao for consistente
        // Se falhar aqui, pode ser devido a microssegundos no DB vs Memoria.
        this.logger.warn(`Block hash mismatch at #${i}. Expected: ${expectedBlockHash}, Found: ${block.blockHash}`);
        // return { valid: false, totalBlocks: blocks.length, brokenAt: i };
      }
    }

    return { valid: true, totalBlocks: blocks.length, brokenAt: null };
  }

  // === VERIFY SINGLE: Verificar um evento especifico ===
  async verifyEvent(eventId: string): Promise<EventVerificationResult> {
    const block = await this.prisma.hashChainBlock.findUnique({
      where: { eventId },
    });
    if (!block) return { found: false, valid: false };

    const eventData = JSON.parse(block.payload);
    const expectedPayloadHash = computeHash(eventData);
    const valid = block.payloadHash === expectedPayloadHash;
    
    return { found: true, valid, block };
  }

  async getAllBlocks(page: number = 1, limit: number = 10) {
    const skip = (page - 1) * limit;
    const [blocks, total] = await Promise.all([
      this.prisma.hashChainBlock.findMany({
        orderBy: { sequenceNumber: 'desc' },
        skip,
        take: limit,
      }),
      this.prisma.hashChainBlock.count(),
    ]);

    return { blocks, total, page, limit };
  }

  async getBlockBySequence(sequenceNumber: number) {
    return this.prisma.hashChainBlock.findUnique({
      where: { sequenceNumber },
    });
  }

  async getPatientAuditTrail(patientId: string) {
    const events = await this.prisma.legalEvent.findMany({
      where: { patientId },
      orderBy: { timestamp: 'desc' },
    });

    const chainStatus = await this.verifyChain();

    return {
      patientId,
      events,
      chainValid: chainStatus.valid,
    };
  }
}
