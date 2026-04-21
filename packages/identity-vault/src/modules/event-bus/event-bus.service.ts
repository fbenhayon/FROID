import { Injectable, OnModuleInit, Logger, Inject, forwardRef } from '@nestjs/common';
import { Redis } from 'ioredis';
import { STREAMS, CONSUMER_GROUPS } from './event-bus.constants';
import { HashChainService } from '../hash-chain/hash-chain.service';
import { PolicyCacheService } from '../policy/redis-cache.service';

@Injectable()
export class EventBusService implements OnModuleInit {
  private readonly logger = new Logger(EventBusService.name);
  private readonly redis: Redis;

  constructor(
    private readonly hashChainService: HashChainService,
    private readonly policyCacheService: PolicyCacheService,
  ) {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    this.redis = new Redis(redisUrl);
  }

  async onModuleInit() {
    this.logger.log('Initializing Event Bus (Redis Streams)...');
    
    // Criar consumer groups se nao existirem
    for (const stream of Object.values(STREAMS)) {
      for (const group of Object.values(CONSUMER_GROUPS)) {
        try {
          await this.redis.xgroup('CREATE', stream, group, '0', 'MKSTREAM');
          this.logger.log(`Consumer group ${group} created for stream ${stream}`);
        } catch (e: any) {
          if (!e.message.includes('BUSYGROUP')) {
            this.logger.error(`Error creating group ${group}: ${e.message}`);
          }
        }
      }
    }
    
    // Iniciar consumers
    this.startConsumers();
  }

  // === PUBLICAR EVENTO ===
  async publish(event: any): Promise<string> {
    const messageId = await this.redis.xadd(
      STREAMS.LEGAL_EVENTS,
      '*',  // auto-generate ID
      'type', event.eventType,
      'payload', JSON.stringify(event),
    );

    // Se for evento de consentimento, publicar tambem no stream especifico
    if (['CONSENT_GRANTED', 'CONSENT_REVOKED', 'CONSENT_DENIED'].includes(event.eventType)) {
      await this.redis.xadd(
        STREAMS.CONSENT_EVENTS,
        '*',
        'type', event.eventType,
        'patientId', event.patientId,
        'scope', event.scope || '',
        'payload', JSON.stringify(event),
      );
    }
    this.logger.debug(`Event published: ${event.eventType} (ID: ${messageId})`);
    return messageId;
  }

  // === CONSUMERS ===
  private async startConsumers() {
    // Consumer 1: Hash Chain - grava cada evento na cadeia imutavel
    this.consumeStream(STREAMS.LEGAL_EVENTS, CONSUMER_GROUPS.HASH_CHAIN,
      async (event: any) => {
        try {
          await this.hashChainService.appendBlock(event);
        } catch (error) {
          this.logger.error(`Hash Chain Consumer error: ${error.message}`);
        }
      }
    );

    // Consumer 2: Policy Cache - invalida cache quando consentimento muda
    this.consumeStream(STREAMS.CONSENT_EVENTS, CONSUMER_GROUPS.POLICY_CACHE,
      async (event: any) => {
        try {
          if (['CONSENT_REVOKED', 'CONSENT_GRANTED'].includes(event.eventType)) {
            await this.policyCacheService.invalidateForPatient(event.patientId);
            this.logger.log(`Policy cache invalidated for patient ${event.patientId} due to ${event.eventType}`);
          }
        } catch (error) {
          this.logger.error(`Policy Cache Consumer error: ${error.message}`);
        }
      }
    );
  }

  private async consumeStream(stream: string, group: string, handler: (event: any) => Promise<void>) {
    const consumerName = `${group}-${process.pid}-${Math.random().toString(36).substring(7)}`;
    
    const poll = async () => {
      try {
        const results = await this.redis.xreadgroup(
          'GROUP', group, consumerName,
          'COUNT', '10',
          'BLOCK', '5000',  // espera 5s por novos eventos
          'STREAMS', stream, '>'
        );

        if (results) {
          const typedResults = results as [string, [string, string[]][]][];
          for (const [streamName, messages] of typedResults) {
            for (const [id, fields] of messages) {
              try {
                // Encontrar o indice do payload
                const payloadIndex = fields.indexOf('payload');
                if (payloadIndex !== -1) {
                  const payload = JSON.parse(fields[payloadIndex + 1]);
                  await handler(payload);
                }
                // Confirmamos o processamento
                await this.redis.xack(stream, group, id);
              } catch (innerError) {
                this.logger.error(`Error processing message ${id} from ${streamName}: ${innerError.message}`);
              }
            }
          }
        }
      } catch (e: any) {
        if (!e.message.includes('Connection is closed')) {
           this.logger.error(`Consumer ${group} error on stream ${stream}: ${e.message}`);
        }
      }
      
      // Re-poll - Use setImmediate to avoid stack overflow and allow other tasks
      setImmediate(poll);
    };

    poll();
  }
}
