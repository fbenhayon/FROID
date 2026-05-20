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
    const user = await this.prisma.users.findUnique({
      where: { email: dto.email },
    });
    if (!user) throw new UnauthorizedException('Credenciais inválidas');

    const isPasswordValid = await bcrypt.compare(dto.password, user.password);
    if (!isPasswordValid) throw new UnauthorizedException('Credenciais inválidas');

    const professional = await this.prisma.professionals.findUnique({
      where: { userId: user.id },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: professional?.name || user.email,
        role: user.role,
        professionalId: professional?.id || null,
      },
    };
  }

  async oauthLogin(profile: any, provider: 'google' | 'github') {
    let user = await this.prisma.users.findUnique({
      where: { email: profile.email },
    });

    const providerIdField = provider === 'google' ? 'googleId' : 'githubId';
    const providerId = provider === 'google' ? profile.googleId : profile.githubId;

    if (!user) {
      user = await this.prisma.users.create({
        data: {
          email: profile.email,
          password: '',
          role: 'professional',
          [providerIdField]: providerId,
          picture: profile.picture,
        },
      });

      await this.prisma.professionals.create({
        data: {
          userId: user.id,
          name: profile.name || user.email,
          crp: `PENDENTE-${user.id.slice(0, 8)}`,
          specialty: 'A definir',
        },
      });
    } else if (!user[providerIdField]) {
      user = await this.prisma.users.update({
        where: { id: user.id },
        data: {
          [providerIdField]: providerId,
          picture: profile.picture || user.picture,
        },
      });
    }

    const professional = await this.prisma.professionals.findUnique({
      where: { userId: user.id },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: professional?.name || user.email,
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

    const user = await this.prisma.users.create({
      data: {
        email: dto.email,
        password: hashedPassword,
        role: 'professional',
      },
    });

    const professional = await this.prisma.professionals.create({
      data: {
        userId: user.id,
        name: dto.name || dto.email,
        crp: dto.crp || `PENDENTE-${user.id.slice(0, 8)}`,
        specialty: dto.specialty || 'A definir',
      },
    });

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: {
        id: user.id,
        email: user.email,
        name: professional.name,
        role: user.role,
        professionalId: professional.id,
      },
    };
  }
}
