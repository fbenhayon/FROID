"""Language configuration for FROID clinical-session processing.

Locale codes are kept separate from provider-specific language hints so a
session can preserve its original language and produce a report in another
supported language without overwriting the literal transcript.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SessionLanguage:
    locale: str
    provider_language: str
    english_name: str
    native_name: str
    transcription_instruction: str
    summary_instruction: str
    no_speech_theme: str
    no_speech_summary: str
    pending_theme: str


SESSION_LANGUAGES: dict[str, SessionLanguage] = {
    "pt-BR": SessionLanguage(
        locale="pt-BR",
        provider_language="pt",
        english_name="Brazilian Portuguese",
        native_name="Português (Brasil)",
        transcription_instruction="Transcreva literalmente em português do Brasil",
        summary_instruction="Responda em português do Brasil",
        no_speech_theme="Sem fala transcrita",
        no_speech_summary="Nenhuma fala foi transcrita neste intervalo.",
        pending_theme="Tema em apuração",
    ),
    "en-US": SessionLanguage(
        locale="en-US",
        provider_language="en",
        english_name="American English",
        native_name="English (United States)",
        transcription_instruction="Transcribe literally in American English",
        summary_instruction="Respond in American English",
        no_speech_theme="No transcribed speech",
        no_speech_summary="No speech was transcribed during this interval.",
        pending_theme="Theme being assessed",
    ),
    "fr-FR": SessionLanguage(
        locale="fr-FR",
        provider_language="fr",
        english_name="French (France)",
        native_name="Français (France)",
        transcription_instruction="Transcrivez littéralement en français de France",
        summary_instruction="Répondez en français de France",
        no_speech_theme="Aucune parole transcrite",
        no_speech_summary="Aucune parole n’a été transcrite pendant cet intervalle.",
        pending_theme="Thème en cours d’évaluation",
    ),
    "es-ES": SessionLanguage(
        locale="es-ES",
        provider_language="es",
        english_name="Spanish (Spain)",
        native_name="Español (España)",
        transcription_instruction="Transcriba literalmente en español de España",
        summary_instruction="Responda en español de España",
        no_speech_theme="Sin habla transcrita",
        no_speech_summary="No se transcribió ninguna intervención durante este intervalo.",
        pending_theme="Tema en evaluación",
    ),
}

DEFAULT_SESSION_LOCALE = "pt-BR"

_LOCALE_ALIASES = {
    "pt": "pt-BR",
    "pt-br": "pt-BR",
    "en": "en-US",
    "en-us": "en-US",
    "fr": "fr-FR",
    "fr-fr": "fr-FR",
    "es": "es-ES",
    "es-es": "es-ES",
}


def normalize_session_locale(value: object, default: str = DEFAULT_SESSION_LOCALE) -> str:
    candidate = str(value or "").strip()
    if candidate in SESSION_LANGUAGES:
        return candidate
    normalized = _LOCALE_ALIASES.get(candidate.lower())
    if normalized:
        return normalized
    return default if default in SESSION_LANGUAGES else DEFAULT_SESSION_LOCALE


def session_language(value: object) -> SessionLanguage:
    return SESSION_LANGUAGES[normalize_session_locale(value)]


def transcription_prompt(locale: object, previous_context: object = "") -> str:
    language = session_language(locale)
    prompt = (
        f"{language.transcription_instruction}. Transcribe only clearly audible human speech "
        "with natural punctuation. Do not translate, summarize, complete sentences, infer "
        "missing content, or invent words. Preserve technical terms, names, acronyms, and the "
        "speaker's original wording. Return an empty result when there is no clear human speech. "
        "Required vocabulary: spell FROID as FROID, never Freud; preserve IPM, IDM, MFCC, "
        "biomarkers, subharmonics, bioacoustics, dissonances, patient, and professional in the "
        "language in which they were spoken."
    )
    context = str(previous_context or "").strip()[-900:]
    if context:
        prompt += (
            "\n\nImmediately preceding literal transcript. Use it only for continuity and "
            f"punctuation; do not repeat it:\n{context}"
        )
    return prompt


def summary_prompt(
    transcript: object,
    start_minute: int,
    end_minute: int,
    output_locale: object,
) -> str:
    language = session_language(output_locale)
    return (
        "Analyze the clinical-session transcript below and return only a valid JSON object with "
        "the keys theme and summary. The theme must derive directly from the subject discussed, "
        "must not come from a predefined list, and must contain at most 6 words. The summary must "
        f"contain between 70 and 80 words. {language.summary_instruction}. Produce only the derived theme "
        "and summary; the stored literal transcript must remain unchanged. Do not diagnose, invent "
        "facts, or add information that was not spoken. When content is "
        "limited, summarize only the material actually available. "
        f"Interval: {start_minute}-{end_minute} minutes.\n\nTranscript:\n{str(transcript or '').strip()}"
    )


def summary_system_prompt(output_locale: object) -> str:
    language = session_language(output_locale)
    return (
        "You summarize clinical conversations to support a qualified professional. Never diagnose "
        f"or invent content. {language.summary_instruction}."
    )
