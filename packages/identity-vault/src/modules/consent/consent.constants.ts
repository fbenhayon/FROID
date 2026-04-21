export const VALID_SCOPES = [
  'audio_recording',    // Gravação de áudio da sessão
  'video_recording',    // Gravação de vídeo da sessão
  'voice_analysis',     // Análise vocal por IA (openSMILE, Hume)
  'facial_analysis',    // Análise facial por IA (MediaPipe, Hume)
  'transcription',      // Transcrição automática (Whisper)
  'ai_report',          // Geração de relatório por IA (Claude)
  'benchmark',          // Uso anonimizado para referências clínicas
] as const;

export type ConsentScope = typeof VALID_SCOPES[number];

export const CONSENT_STATUS = ['granted', 'revoked', 'denied'] as const;
export type ConsentStatus = typeof CONSENT_STATUS[number];

// Mapa de escopo → LegalText ID (do seed da Entrega 1)
export const SCOPE_TO_LEGAL_TEXT: Record<ConsentScope, string> = {
  audio_recording:  'tcle_audio',
  video_recording:  'tcle_video',
  voice_analysis:   'tcle_voice',
  facial_analysis:  'tcle_facial',
  transcription:    'tcle_transcript',
  ai_report:        'tcle_ai_report',
  benchmark:        'tcle_benchmark',
};
