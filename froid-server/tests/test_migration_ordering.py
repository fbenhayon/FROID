from collections import defaultdict
from pathlib import Path
import re
import unittest


SERVER_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS = SERVER_DIR / "migrations"

# Colisões que já foram aplicadas em produção e não podem ser renomeadas sem
# mexer no registro do banco. Elas aplicaram na ordem certa por acaso — nenhuma
# das duas depende da outra, e a ordenação alfabética as separou de forma
# favorável. Ficam registradas aqui como dívida conhecida, não como padrão.
#
# Origem: a linha de produção e a linha do módulo NR-1 seguiram em paralelo a
# partir do mesmo commit, e cada uma numerou a sua sem enxergar a outra.
GRANDFATHERED_COLLISIONS = {"010", "011"}


def migration_files():
    return sorted(path.stem for path in MIGRATIONS.glob("*.sql"))


def by_prefix():
    grouped = defaultdict(list)
    for stem in migration_files():
        match = re.match(r"^(\d+)_", stem)
        assert match, f"{stem} não começa com um número de ordem"
        grouped[match.group(1)].append(stem)
    return grouped


class MigrationOrderingTests(unittest.TestCase):
    def test_every_migration_starts_with_an_order_number(self):
        for stem in migration_files():
            self.assertRegex(
                stem, r"^\d{3}_[a-z0-9_]+$",
                f"{stem}: use três dígitos e minúsculas, para que a ordem "
                f"alfabética coincida com a ordem de aplicação",
            )

    def test_no_new_number_collision(self):
        """Duas migrations com o mesmo número é uma bomba-relógio.

        ensure_schema aplica na ordem alfabética do nome do arquivo. Com
        números repetidos, quem roda primeiro passa a depender do resto do
        nome — e no dia em que uma delas precisar da outra, o banco quebra na
        aplicação, em produção, no meio de um login.
        """
        collisions = {
            number: sorted(stems)
            for number, stems in by_prefix().items()
            if len(stems) > 1
        }
        novas = {
            number: stems
            for number, stems in collisions.items()
            if number not in GRANDFATHERED_COLLISIONS
        }
        self.assertEqual(
            novas, {},
            "Nova colisão de numeração: renumere antes de aplicar. "
            f"{novas}",
        )

    def test_grandfathered_collisions_did_not_grow(self):
        # Se uma terceira migration entrar num número já colidido, a ordenação
        # alfabética deixa de ser previsível.
        for number in GRANDFATHERED_COLLISIONS:
            stems = by_prefix().get(number, [])
            self.assertLessEqual(
                len(stems), 2,
                f"O número {number} já colidia; não acrescente uma terceira: {stems}",
            )

    def test_next_number_is_free(self):
        """O próximo número a usar não pode já estar ocupado."""
        numbers = sorted(int(number) for number in by_prefix())
        proximo = f"{max(numbers) + 1:03d}"
        self.assertNotIn(
            proximo, by_prefix(),
            f"O próximo número livre deveria ser {proximo}",
        )

    def test_migration_registers_its_own_name(self):
        """Cada arquivo precisa gravar exatamente o seu nome em schema_migrations.

        Se o nome gravado divergir do nome do arquivo, a migration reaplica a
        cada inicialização — e uma reaplicação que não seja idempotente derruba
        o login de todo mundo.
        """
        for path in sorted(MIGRATIONS.glob("*.sql")):
            content = path.read_text(encoding="utf-8")
            self.assertIn(
                f"'{path.stem}'", content,
                f"{path.name} não registra o próprio nome em schema_migrations",
            )

    def test_every_migration_is_transactional(self):
        for path in sorted(MIGRATIONS.glob("*.sql")):
            content = path.read_text(encoding="utf-8")
            self.assertIn("BEGIN;", content, f"{path.name} sem BEGIN")
            self.assertIn("COMMIT;", content, f"{path.name} sem COMMIT")


if __name__ == "__main__":
    unittest.main()
