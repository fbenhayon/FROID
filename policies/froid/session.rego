package froid.session

import data.froid.consent

# Decisao principal: a sessao pode iniciar?
default allow = false

allow {
    count(effective_scopes) > 0
    not has_any_revocation
}

# Calcula effective_scopes = intersection(active, requested)
effective_scopes[scope] {
    scope := input.requested_scopes[_]
    scope == input.active_scopes[_]
}

# Verifica se algum escopo solicitado foi revogado
has_any_revocation {
    input.requested_scopes[_] == input.revoked_scopes[_]
}

# Mapeia escopos efetivos para modulos habilitados
enabled_modules[module] {
    scope := effective_scopes[_]
    module := data.froid.modules.scope_to_module[scope]
}

# Modulos bloqueados = todos - habilitados
blocked_modules[module] {
    module := data.froid.modules.all_modules[_]
    not enabled_modules[module]
}

# Razao do bloqueio - usando um array / set ou definindo default e regras mutuamente exclusivas
default block_reason = ""

block_reason = "Escopo revogado pelo titular" {
    has_any_revocation
} else = "Nenhum escopo valido na intersecao" {
    not allow
    count(effective_scopes) == 0
} else = "" {
    allow
}
