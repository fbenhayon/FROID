import { Module } from '@nestjs/common';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { PatientModule } from './modules/patient/patient.module';
import { QuarantineModule } from './modules/quarantine/quarantine.module';
import { SessionModule } from './modules/session/session.module';
import { PromptModule } from './modules/prompt/prompt.module';

@Module({
  imports: [PrismaModule, AuthModule, PatientModule, QuarantineModule, SessionModule, PromptModule],
  controllers: [],
  providers: [],
})
export class AppModule {}
