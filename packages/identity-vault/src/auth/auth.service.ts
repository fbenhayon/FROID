import { Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';
import * as bcrypt from 'bcrypt';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
  ) {}

  async login(dto: { email: string; password: string }) {
    const user = await this.prisma.user.findUnique({
      where: { email: dto.email },
    });
    if (!user) throw new UnauthorizedException('Credenciais inválidas');

    const isPasswordValid = await bcrypt.compare(dto.password, user.password);
    if (!isPasswordValid) throw new UnauthorizedException('Credenciais inválidas');

    const professional = await this.prisma.professional.findUnique({
      where: { userId: user.id },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        professionalId: professional?.id || null,
      },
    };
  }

  async oauthLogin(profile: any, provider: 'google' | 'github') {
    let user = await this.prisma.user.findUnique({
      where: { email: profile.email },
    });

    const providerIdField = provider === 'google' ? 'googleId' : 'githubId';
    const providerId = provider === 'google' ? profile.googleId : profile.githubId;

    if (!user) {
      user = await this.prisma.user.create({
        data: {
          email: profile.email,
          name: profile.name || profile.email,
          password: '',
          role: 'professional',
          [providerIdField]: providerId,
          picture: profile.picture,
        },
      });

      // Auto-criar registro de Professional para login OAuth
      await this.prisma.professional.create({
        data: {
          userId: user.id,
          name: user.name,
          crp: `PENDENTE-${user.id.slice(0, 8)}`,
          specialty: 'A definir',
        },
      });
    } else if (!user[providerIdField]) {
      user = await this.prisma.user.update({
        where: { id: user.id },
        data: {
          [providerIdField]: providerId,
          picture: profile.picture || user.picture,
        },
      });
    }

    const professional = await this.prisma.professional.findUnique({
      where: { userId: user.id },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        professionalId: professional?.id || null,
      },
    };
  }

  async googleLogin(profile: any) {
    return this.oauthLogin(profile, 'google');
  }

  async register(dto: any) {
    const hashedPassword = await bcrypt.hash(dto.password, 10);

    const user = await this.prisma.user.create({
      data: {
        email: dto.email,
        name: dto.name || dto.email,
        password: hashedPassword,
        role: 'professional',
      },
    });

    // Auto-criar registro de Professional vinculado ao usuário
    const professional = await this.prisma.professional.create({
      data: {
        userId: user.id,
        name: dto.name || dto.email,
        crp: dto.crp || `PENDENTE-${user.id.slice(0, 8)}`,
        specialty: dto.specialty || null,
      },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: user.name,
        role: user.role,
        professionalId: professional.id,
      },
    };
  }
}
