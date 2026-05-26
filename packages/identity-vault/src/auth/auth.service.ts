import { Injectable, UnauthorizedException, ConflictException, BadRequestException } from '@nestjs/common';
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
    } else if (!user[providerIdField]) {
      user = await this.prisma.users.update({
        where: { id: user.id },
        data: { 
          [providerIdField]: providerId,
          picture: profile.picture || user.picture,
        },
      });
    }

    const payload = { sub: user.id, email: user.email };
    return {
      access_token: this.jwtService.sign(payload),
      user: { id: user.id, email: user.email, role: user.role },
    };
  }

  async googleLogin(profile: any) {
    return this.oauthLogin(profile, 'google');
  }

  async register(dto: any) {
    if (!dto.name || !dto.crp || !dto.specialty) {
      throw new BadRequestException('name, crp e specialty são obrigatórios');
    }

    const existingUser = await this.prisma.users.findUnique({
      where: { email: dto.email },
    });
    if (existingUser) {
      throw new ConflictException('Email já cadastrado');
    }

    const existingCrp = await this.prisma.professionals.findUnique({
      where: { crp: dto.crp },
    });
    if (existingCrp) {
      throw new ConflictException('CRP já cadastrado');
    }

    const hashedPassword = await bcrypt.hash(dto.password, 10);

    return this.prisma.$transaction(async (tx) => {
      const user = await tx.users.create({
        data: {
          email: dto.email,
          password: hashedPassword,
          role: 'professional',
        },
      });

      const professional = await tx.professionals.create({
        data: {
          userId: user.id,
          name: dto.name,
          crp: dto.crp,
          specialty: dto.specialty,
          phone: dto.phone || null,
        },
      });

      const payload = { sub: user.id, email: user.email };
      return {
        access_token: this.jwtService.sign(payload),
        user: {
          id: user.id,
          email: user.email,
          role: user.role,
          professionalId: professional.id,
        },
        professional: {
          id: professional.id,
          name: professional.name,
          crp: professional.crp,
          specialty: professional.specialty,
        },
      };
    });
  }
}
