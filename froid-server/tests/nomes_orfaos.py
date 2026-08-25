"""Nomes carregados que nao existem em escopo algum: o NameError antes do deploy.

Analisador de escopo lexico sobre a AST. Para cada nome LIDO, sobe a cadeia de
escopos — comprehension, funcao, funcoes que a envolvem, modulo, builtins — e
acusa o que nao existe em nenhum deles.

Existe porque um NameError num caminho protegido por `except Exception` nao
aparece: o codigo importa, os testes passam, o deploy sobe, e a falha so se
manifesta como um efeito que ninguem liga a ela. Foi o que aconteceu duas
vezes neste servidor, e as duas custaram dias.
"""
import ast, builtins, io, sys

MODULO = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__"}


def _liga(no, nomes):
    """Nomes que ESTE no introduz no escopo em que aparece."""
    if isinstance(no, (ast.Import, ast.ImportFrom)):
        for a in no.names:
            nomes.add((a.asname or a.name).split(".")[0])
    elif isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        nomes.add(no.name)
    elif isinstance(no, ast.Name) and isinstance(no.ctx, (ast.Store, ast.Del)):
        nomes.add(no.id)
    elif isinstance(no, ast.ExceptHandler) and no.name:
        nomes.add(no.name)
    elif isinstance(no, (ast.Global, ast.Nonlocal)):
        nomes.update(no.names)


def _escopo_de(no):
    """Todos os nomes ligados dentro de um escopo, sem descer em escopos filhos."""
    nomes = set()
    args = getattr(no, "args", None)
    if args is not None:
        for a in args.posonlyargs + args.args + args.kwonlyargs:
            nomes.add(a.arg)
        if args.vararg:
            nomes.add(args.vararg.arg)
        if args.kwarg:
            nomes.add(args.kwarg.arg)

    pilha = list(ast.iter_child_nodes(no))
    while pilha:
        filho = pilha.pop()
        _liga(filho, nomes)
        # Comprehensions e lambdas tem escopo proprio, mas o alvo delas nao
        # escapa; funcoes aninhadas so contribuem o proprio nome.
        if isinstance(filho, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        pilha.extend(ast.iter_child_nodes(filho))
    return nomes


def orfaos(caminho):
    with io.open(caminho, encoding="utf-8") as arquivo:
        src = arquivo.read()
    arvore = ast.parse(src)
    achados = []

    def visitar(no, cadeia):
        # Um escopo enxerga o proprio, todos os que o envolvem, e o modulo.
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            cadeia = cadeia + [_escopo_de(no)]
        elif isinstance(no, ast.ClassDef):
            cadeia = cadeia + [_escopo_de(no)]
        elif isinstance(no, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            alvos = set()
            for gerador in no.generators:
                for sub in ast.walk(gerador.target):
                    if isinstance(sub, ast.Name):
                        alvos.add(sub.id)
            cadeia = cadeia + [alvos]

        for filho in ast.iter_child_nodes(no):
            if isinstance(filho, ast.Name) and isinstance(filho.ctx, ast.Load):
                if not any(filho.id in escopo for escopo in cadeia):
                    dono = getattr(no, "name", "<modulo>")
                    achados.append((dono, filho.lineno, filho.id))
            visitar(filho, cadeia)

    visitar(arvore, [MODULO | _escopo_de(arvore)])
    return achados


if __name__ == "__main__":
    total = 0
    for caminho in sys.argv[1:]:
        for _dono, linha, nome in sorted(set(orfaos(caminho)), key=lambda x: x[1]):
            print(f"{caminho}:{linha}  ->  '{nome}'")
            total += 1
    print(f"total: {total}")
