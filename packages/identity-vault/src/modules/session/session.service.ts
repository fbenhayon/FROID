import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import { SessionTimerService } from './session-timer.service';
import { randomUUID } from 'crypto';
import axios from 'axios';

@Injectable()
export class SessionService {
  constructor(
    private prisma: PrismaService,
    private timerService: SessionTimerService,
  ) {}

  private readonly VOICE_SERVICE = process.env.VOICE_SERVICE_URL || 'http://froid-voice:3002';
  private readonly FACE_SERVICE = process.env.FACE_SERVICE_URL || 'http://froid-face:3003';

  async createSession(data: {
    patientId: string;
    professionalId: string;
    scheduledFor: Date;
  }) {
    return this.prisma.sessions.create({
      data: {
        patientId: data.patientId,
        professionalId: data.professionalId,
        scheduledFor: data.scheduledFor,
        status: 'scheduled',
      },
    });
  }

  async startSession(sessionId: string) {
    const session = await this.prisma.sessions.findUnique({
      where: { id: sessionId },
    });

    if (!session) {
      throw new NotFoundException('Session not found');
    }

    const startedAt = new Date();
    const updated = await this.prisma.sessions.update({
      where: { id: sessionId },
      data: {
        status: 'active',
        startedAt,
      },
    });

    this.timerService.start(sessionId, startedAt);
    return updated;
  }

  async endSession(sessionId: string, notes?: string) {
    this.timerService.cancel(sessionId);
    return this.prisma.sessions.update({
      where: { id: sessionId },
      data: {
        status: 'completed',
        endedAt: new Date(),
        notes,
      },
    });
  }

  async getTimerStatus(sessionId: string) {
    const session = await this.prisma.sessions.findUnique({
      where: { id: sessionId },
      select: { id: true, status: true, startedAt: true, creditCharged: true },
    });

    if (!session) {
      throw new NotFoundException('Session not found');
    }

    return {
      ...this.timerService.getStatus(sessionId, session.startedAt),
      creditCharged: session.creditCharged,
      sessionStatus: session.status,
    };
  }

  async analyzeVoice(sessionId: string, audioData: any) {
    try {
      const response = await axios.post(`${this.VOICE_SERVICE}/analyze`, {
        sessionId,
        audio: audioData,
      });

      await this.prisma.voice_analyses.create({
        data: {
          id: randomUUID(),
          sessionId,
          zonalEnergies: response.data.zonalEnergies || {},
          spectralBands: response.data.spectralBands || {},
          rawFeatures: response.data,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Voice analysis error:', error.message);
      throw error;
    }
  }

  async analyzeFace(sessionId: string, imageData: any) {
    try {
      const response = await axios.post(`${this.FACE_SERVICE}/analyze`, {
        sessionId,
        image: imageData,
      });

      await this.prisma.facial_analyses.create({
        data: {
          id: randomUUID(),
          sessionId,
          actionUnits: response.data.actionUnits || {},
          rawLandmarks: response.data,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Face analysis error:', error.message);
      throw error;
    }
  }

  async getSessionResults(sessionId: string) {
    const session = await this.prisma.sessions.findUnique({
      where: { id: sessionId },
      include: {
        voice_analyses: true,
        facial_analyses: true,
        fusion_analyses: true,
      },
    });

    if (!session) {
      throw new NotFoundException('Session not found');
    }

    return session;
  }

  async getPatientSessions(patientId: string) {
    return this.prisma.sessions.findMany({
      where: { patientId },
      orderBy: { createdAt: 'desc' },
      include: {
        voice_analyses: true,
        facial_analyses: true,
      },
    });
  }
}
