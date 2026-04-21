package froid.consent

# Verifica se um escopo especifico esta ativo para o paciente
default scope_allowed = false

scope_allowed {
    input.requested_scope == input.active_scopes[_]
}

# Verifica se houve revogacao recente
default has_revocation = false

has_revocation {
    input.revoked_scopes[_] == input.requested_scope
}
