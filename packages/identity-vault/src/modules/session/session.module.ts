import { PrismaModule } from '../../prisma/prisma.module';
import { Module } from '@nestjs/common';
import { SessionController } from './session.controller';
import { SessionService } from './session.service';
import { SessionTimerService } from './session-timer.service';
import { PrismaService } from '../../prisma/prisma.service';

@Module({
  imports: [PrismaModule],
  controllers: [SessionController],
  providers: [SessionService, SessionTimerService, PrismaService],
  exports: [SessionService],
})
export class SessionModule {}
