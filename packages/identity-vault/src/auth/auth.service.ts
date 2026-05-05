import { Injectable, UnauthorizedException, ConflictException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcrypt';
import { prisma } from '../prisma/client';
import { RegisterDto, LoginDto } from './dto';

@Injectable()
export class AuthService {
  constructor(private jwt: JwtService) {}

  async register(dto: RegisterDto) {
    const exists = await prisma.user.findUnique({ where: { email: dto.email } });
    if (exists) throw new ConflictException('Email already registered');

    const professional = await prisma.professional.findUnique({ where: { crp: dto.crp } });
    if (professional) throw new ConflictException('CRP already registered');

    const hash = await bcrypt.hash(dto.password, 10);
    const user = await prisma.user.create({
      data: {
        email: dto.email,
        password: hash,
        role: 'professional',
        professional: {
          create: {
            name: dto.name,
            crp: dto.crp,
            specialty: dto.specialty,
          },
        },
      },
      include: { professional: true },
    });

    return { id: user.id, email: user.email, createdAt: user.createdAt };
  }

  async login(dto: LoginDto) {
    const user = await prisma.user.findUnique({
      where: { email: dto.email },
      include: { professional: true },
    });

    if (!user || !(await bcrypt.compare(dto.password, user.password))) {
      throw new UnauthorizedException('Invalid credentials');
    }

    const payload = { sub: user.id, email: user.email };

    return {
      access_token: this.jwt.sign(payload),
      user: {
        id: user.professional?.id || user.id,
        email: user.email,
        name: user.professional?.name || 'Usuário',
        role: user.role,
      },
    };
  }
}
