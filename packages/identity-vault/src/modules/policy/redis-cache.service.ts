import { Injectable, Logger, OnModuleDestroy, OnModuleInit } from '@nestjs/common';
import { Redis } from 'ioredis';
import { PolicyDecision } from './dto/policy-decision.dto';

@Injectable()
export class PolicyCacheService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PolicyCacheService.name);
  private redisClient: Redis;
  private readonly TTL_SECONDS = 60; // 60 segundos conforme spec

  onModuleInit() {
    const redisUrl = process.env.REDIS_URL || 'redis://localhost:6379';
    this.redisClient = new Redis(redisUrl);
    
    this.redisClient.on('connect', () => {
      this.logger.log(`Connected to Redis at ${redisUrl}`);
    });

    this.redisClient.on('error', (err) => {
      this.logger.error('Redis connection error', err);
    });
  }

  onModuleDestroy() {
    if (this.redisClient) {
      this.redisClient.quit();
    }
  }

  private getKey(patientId: string, requestedScopes: string[]): string {
    const sortedScopes = [...requestedScopes].sort().join(',');
    return `policy:${patientId}:${sortedScopes}`;
  }

  async getDecision(patientId: string, requestedScopes: string[]): Promise<PolicyDecision | null> {
    try {
      const key = this.getKey(patientId, requestedScopes);
      const cached = await this.redisClient.get(key);
      if (cached) {
        return JSON.parse(cached) as PolicyDecision;
      }
      return null;
    } catch (error) {
      this.logger.warn(`Failed to get cache for patient ${patientId}`, error);
      return null;
    }
  }

  async saveDecision(patientId: string, requestedScopes: string[], decision: PolicyDecision): Promise<void> {
    try {
      const key = this.getKey(patientId, requestedScopes);
      await this.redisClient.set(key, JSON.stringify(decision), 'EX', this.TTL_SECONDS);
    } catch (error) {
      this.logger.warn(`Failed to save cache for patient ${patientId}`, error);
    }
  }

  async invalidateForPatient(patientId: string): Promise<void> {
    try {
      const pattern = `policy:${patientId}:*`;
      const keys = await this.redisClient.keys(pattern);
      if (keys.length > 0) {
        await this.redisClient.del(...keys);
        this.logger.log(`Invalidated ${keys.length} cache entries for patient ${patientId}`);
      }
    } catch (error) {
      this.logger.error(`Failed to invalidate cache for patient ${patientId}`, error);
    }
  }
}
