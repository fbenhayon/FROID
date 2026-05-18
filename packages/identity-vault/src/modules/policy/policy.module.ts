import { PrismaModule } from '../../prisma/prisma.module';
import { Module, forwardRef } from '@nestjs/common';
import { PolicyService } from './policy.service';
import { PolicyController } from './policy.controller';
import { PolicyCacheService } from './redis-cache.service';
import { ConsentModule } from '../consent/consent.module';

@Module({
  imports: [PrismaModule],
  imports: [forwardRef(() => ConsentModule)],
  controllers: [PolicyController],
  providers: [PolicyService, PolicyCacheService],
  exports: [PolicyService, PolicyCacheService],
})
export class PolicyModule {}
