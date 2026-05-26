import { Injectable } from '@nestjs/common';
import { PrismaService } from '../../prisma/prisma.service';

const WARNING_MS = 50 * 60 * 1000;
const CHARGE_MS = 55 * 60 * 1000;

interface TimerEntry {
  warning: NodeJS.Timeout;
  charge: NodeJS.Timeout;
  startedAt: Date;
  warningFired: boolean;
}

@Injectable()
export class SessionTimerService {
  private timers = new Map<string, TimerEntry>();

  constructor(private prisma: PrismaService) {}

  start(sessionId: string, startedAt: Date) {
    this.cancel(sessionId);

    const entry: TimerEntry = {
      startedAt,
      warningFired: false,
      warning: null,
      charge: null,
    };

    entry.warning = setTimeout(() => {
      console.log(`[FROID-TIMER] Sessão ${sessionId}: aviso de 50 minutos`);
      entry.warningFired = true;
    }, WARNING_MS);

    entry.charge = setTimeout(async () => {
      console.log(`[FROID-TIMER] Sessão ${sessionId}: 55 minutos atingidos, cobrando crédito`);
      await this.chargeSession(sessionId);
    }, CHARGE_MS);

    this.timers.set(sessionId, entry);
  }

  cancel(sessionId: string) {
    const entry = this.timers.get(sessionId);
    if (entry) {
      clearTimeout(entry.warning);
      clearTimeout(entry.charge);
      this.timers.delete(sessionId);
    }
  }

  getStatus(sessionId: string, startedAt: Date | null) {
    if (!startedAt) {
      return { running: false, elapsedMinutes: 0, warningAt50: false, chargedAt55: false };
    }

    const elapsedMs = Date.now() - startedAt.getTime();
    const elapsedMinutes = Math.floor(elapsedMs / 60000);
    const entry = this.timers.get(sessionId);

    return {
      running: !!entry,
      elapsedMinutes,
      elapsedSeconds: Math.floor(elapsedMs / 1000),
      warningAt50: elapsedMinutes >= 50,
      chargedAt55: elapsedMinutes >= 55,
    };
  }

  private async chargeSession(sessionId: string) {
    try {
      await this.prisma.sessions.update({
        where: { id: sessionId },
        data: { creditCharged: true },
      });
      console.log(`[FROID-TIMER] Crédito debitado para sessão ${sessionId}`);
    } catch (err) {
      console.error(`[FROID-TIMER] Falha ao debitar crédito para sessão ${sessionId}:`, err.message);
    } finally {
      this.timers.delete(sessionId);
    }
  }
}
