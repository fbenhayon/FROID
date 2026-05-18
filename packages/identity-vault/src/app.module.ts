import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AuthModule } from './auth/auth.module';
import { PrismaService } from './prisma/prisma.service';
import { AdminModule } from './modules/admin/admin.module';
import { SessionModule } from './modules/session/session.module';
import { PatientModule } from './modules/patient/patient.module';
import { ProfessionalModule } from './modules/professional/professional.module';
import { PromptModule } from './modules/prompt/prompt.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    AuthModule,
    AdminModule,
    SessionModule,
    PatientModule,
    ProfessionalModule,
    PromptModule,
  ],
  providers: [PrismaService],
})
export class AppModule {}
