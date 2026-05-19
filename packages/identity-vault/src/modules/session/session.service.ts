import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';
import axios from 'axios';

@Injectable()
export class SessionService {
  constructor(private prisma: PrismaService) {}

  private readonly VOICE_SERVICE = process.env.VOICE_SERVICE_URL || 'http://froid-voice:3002';
  private readonly FACE_SERVICE = process.env.FACE_SERVICE_URL || 'http://froid-face:3003';

  async createSession(data: {
    patientId: string;
    professionalId: string;
    scheduledFor: Date;
  }) {
    return this.prisma.session.create({
      data: {
        patientId: data.patientId,
        professionalId: data.professionalId,
        scheduledFor: data.scheduledFor,
        status: 'scheduled',
      },
    });
  }

  async startSession(sessionId: string) {
    const session = await this.prisma.session.findUnique({
      where: { id: sessionId },
    });

    if (!session) {
      throw new NotFoundException('Session not found');
    }

    return this.prisma.session.update({
      where: { id: sessionId },
      data: {
        status: 'active',
        startedAt: new Date(),
      },
    });
  }

  async endSession(sessionId: string, notes?: string) {
    return this.prisma.session.update({
      where: { id: sessionId },
      data: {
        status: 'completed',
        endedAt: new Date(),
        clinicalNotes: notes,
      },
    });
  }

  async analyzeVoice(sessionId: string, audioData: any) {
    try {
      const response = await axios.post(`${this.VOICE_SERVICE}/analyze`, {
        sessionId,
        audio: audioData,
      });

      await this.prisma.voiceAnalysis.create({
        data: {
          sessionId,
          data: response.data,
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

      await this.prisma.facialAnalysis.create({
        data: {
          sessionId,
          data: response.data,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Face analysis error:', error.message);
      throw error;
    }
  }

  async getSessionResults(sessionId: string) {
    const session = await this.prisma.session.findUnique({
      where: { id: sessionId },
      include: {
        voiceAnalyses: true,
        facialAnalyses: true,
        fusionAnalyses: true,
      },
    });

    if (!session) {
      throw new NotFoundException('Session not found');
    }

    return session;
  }

  async getPatientSessions(patientId: string) {
    return this.prisma.session.findMany({
      where: { patientId },
      orderBy: { createdAt: 'desc' },
      include: {
        voiceAnalyses: true,
        facialAnalyses: true,
      },
    });
  }
}
