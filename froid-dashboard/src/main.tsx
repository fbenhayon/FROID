import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { normalizarEntradaDireta } from './lib/entrada-direta'
import './index.css'

// ANTES do createRoot, e nao de dentro de um efeito do App.
//
// O HashRouter e construido durante o primeiro render e, sem `#` na URL,
// assume "/" — que redireciona para o login e escreve `#/login`. Qualquer
// normalizacao que rode depois disso encontra a URL ja decidida. Foi assim que
// o convite do NR-1 chegava ao trabalhador como tela de login, com o token
// pendurado na barra de enderecos e nenhuma mensagem de erro.
normalizarEntradaDireta()

const CHUNK_RECOVERY_KEY = 'froid_chunk_recovery'
const CHUNK_RECOVERY_WINDOW_MS = 15_000

function reloadOnceAfterFrontendUpdate() {
  const now = Date.now()
  const previousAttempt = Number(sessionStorage.getItem(CHUNK_RECOVERY_KEY) || 0)
  if (now - previousAttempt < CHUNK_RECOVERY_WINDOW_MS) return false
  sessionStorage.setItem(CHUNK_RECOVERY_KEY, String(now))
  window.location.reload()
  return true
}

window.addEventListener('vite:preloadError', ((event: Event) => {
  event.preventDefault()
  reloadOnceAfterFrontendUpdate()
}) as EventListener)

window.setTimeout(() => {
  sessionStorage.removeItem(CHUNK_RECOVERY_KEY)
}, CHUNK_RECOVERY_WINDOW_MS)

type AppErrorBoundaryState = {
  failed: boolean
}

class AppErrorBoundary extends React.Component<React.PropsWithChildren, AppErrorBoundaryState> {
  state: AppErrorBoundaryState = { failed: false }

  static getDerivedStateFromError(): AppErrorBoundaryState {
    return { failed: true }
  }

  componentDidCatch(error: Error) {
    const message = String(error?.message || error)
    const isFrontendUpdateError =
      /dynamically imported module|failed to fetch.*module|importing a module script/i.test(message)
    if (isFrontendUpdateError) reloadOnceAfterFrontendUpdate()
    console.error('FROID interface recovery', error)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 px-6 text-white">
        <section className="w-full max-w-lg rounded-2xl border border-blue-700 bg-slate-900 p-8 text-center shadow-2xl">
          <h1 className="text-xl font-bold">Não foi possível abrir esta tela</h1>
          <p className="mt-3 text-sm text-slate-300">
            Seus dados permanecem preservados. Recarregue a versão atual do FROID para continuar.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button
              className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-bold text-white hover:bg-blue-500"
              onClick={() => window.location.reload()}
              type="button"
            >
              Tentar novamente
            </button>
            <button
              className="rounded-lg border border-blue-500 px-5 py-3 text-sm font-bold text-white hover:bg-blue-950"
              onClick={() => {
                window.location.hash = '#/dashboard'
                window.location.reload()
              }}
              type="button"
            >
              Voltar ao Dashboard
            </button>
          </div>
        </section>
      </main>
    )
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </React.StrictMode>,
)
