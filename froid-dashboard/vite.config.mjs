import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // A faixa da marca dos relatórios precisa virar data URI, e não um arquivo
    // em /assets. O documento imprimível abre com window.open("") seguido de
    // document.write, ou seja, numa janela about:blank: URL relativa não
    // resolve ali, e URL absoluta quebraria o documento salvo em PDF e aberto
    // fora da rede. Embutida, a faixa sobrevive à impressão offline — que é o
    // uso real de um documento clínico.
    //
    // O sufixo ?inline seria o caminho natural, mas no Vite 5 ele só vale para
    // CSS; para imagem só chegou no Vite 6. Então a decisão vem daqui, por
    // arquivo, em vez de subir o assetsInlineLimit global e passar a embutir
    // tudo que for pequeno no projeto inteiro.
    assetsInlineLimit: (filePath) => {
      if (filePath.includes("relatorio-logo")) return true;
      return undefined; // demais arquivos: comportamento padrão do Vite
    },
  },
});
