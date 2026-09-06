"""A CSP nao pode desligar a analise acustica em silencio.

Apurado em 06/09/2026. A analise acustica do FROID captura PCM cru do
microfone do paciente por um AudioWorklet, e o modulo do worklet e servido a
partir de um Blob criado na propria pagina (`froid-acoustic.ts`).

`script-src` nao tinha `blob:`. `worker-src` tinha — mas worker-src governa
Worker, SharedWorker e ServiceWorker; **worklet e buscado sob script-src**. O
navegador do paciente recusava o modulo, `startF0Capture` caia no catch e
devolvia uma funcao de parada vazia, e NENHUM byte de audio subia. Em toda
sessao, para todo paciente, desde que a CSP entrou.

O que tornou o defeito dificil de achar foi a assimetria: a leitura FACIAL
funcionava e a acustica nao, saindo as duas da MESMA pagina, com a mesma
autenticacao, para o mesmo servidor. O MediaPipe carrega de cdn.jsdelivr.net,
que estava liberado; o worklet carrega de blob:, que nao estava.

Uma politica de seguranca que desliga um subsistema inteiro sem erro visivel e
o pior tipo de configuracao errada. Este teste existe para que a proxima
revisao da CSP nao a desligue de novo.
"""

import os
import re
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CADDYFILE = os.path.join(RAIZ, "Caddyfile")

with open(CADDYFILE, encoding="utf-8") as arquivo:
    CONFIG = arquivo.read()


def _diretiva(nome: str) -> str:
    """O conteudo de uma diretiva da CSP, como o navegador a lera."""
    politica = re.search(
        r'Content-Security-Policy\s+"([^"]+)"', CONFIG
    )
    assert politica, "Content-Security-Policy ausente do Caddyfile"
    for parte in politica.group(1).split(";"):
        parte = parte.strip()
        if parte.split(" ")[0] == nome:
            return parte
    return ""


class CspNaoDesligaACapturaAcustica(unittest.TestCase):
    def test_a_politica_existe(self):
        self.assertIn("Content-Security-Policy", CONFIG)

    def test_script_src_aceita_blob(self):
        """O AudioWorklet do PCM. Sem isto a sessao roda sem voz do paciente."""
        script_src = _diretiva("script-src")
        self.assertTrue(script_src, "script-src ausente")
        self.assertIn(
            "blob:",
            script_src,
            "sem blob: em script-src o AudioWorklet e recusado e a analise "
            "acustica nao envia nada — foi o defeito de 06/09/2026",
        )

    def test_worker_src_continua_aceitando_blob(self):
        """Nao e substituto de script-src, e tambem nao pode sair."""
        self.assertIn("blob:", _diretiva("worker-src"))

    def test_o_cdn_do_mediapipe_continua_liberado(self):
        """A leitura facial depende dele em script-src e em worker-src."""
        self.assertIn("https://cdn.jsdelivr.net", _diretiva("script-src"))
        self.assertIn("https://cdn.jsdelivr.net", _diretiva("worker-src"))

    def test_o_envio_ao_backend_continua_liberado(self):
        """`connect-src 'self'` e o POST do PCM e dos blendshapes."""
        self.assertIn("'self'", _diretiva("connect-src"))

    def test_a_politica_nao_afrouxou_onde_nao_devia(self):
        """Preservado o que a CSP existe para impedir."""
        self.assertIn("frame-ancestors 'none'", CONFIG)
        self.assertIn("object-src 'none'", CONFIG)
        self.assertIn("default-src 'self'", CONFIG)


if __name__ == "__main__":
    unittest.main()
