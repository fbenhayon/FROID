import { useEffect, useMemo } from "react";

import tokensCss from "./institutional/froid-tokens.css?raw";
import cienciaHtml from "./institutional/ciencia.html?raw";
import homeHtml from "./institutional/home.html?raw";
import profissionaisHtml from "./institutional/profissionais.html?raw";
import tecnologiaHtml from "./institutional/tecnologia.html?raw";

type StaticInstitutionalPageProps = {
  fallbackTitle: string;
  html: string;
};

function extractPage(html: string, fallbackTitle: string) {
  const title = html.match(/<title>([\s\S]*?)<\/title>/i)?.[1]?.trim() || fallbackTitle;
  const body = html.match(/<body[^>]*>([\s\S]*?)<\/body>/i)?.[1] || html;

  return {
    markup: body.split("assets/images/").join("/froid-institutional/images/"),
    title,
  };
}

function StaticInstitutionalPage({ fallbackTitle, html }: StaticInstitutionalPageProps) {
  const page = useMemo(() => extractPage(html, fallbackTitle), [fallbackTitle, html]);

  useEffect(() => {
    document.title = page.title;
  }, [page.title]);

  return (
    <>
      <style>{tokensCss}</style>
      <div dangerouslySetInnerHTML={{ __html: page.markup }} />
    </>
  );
}

export function HomePage() {
  return <StaticInstitutionalPage fallbackTitle="FROID" html={homeHtml} />;
}

export function FroidSciencePage() {
  return <StaticInstitutionalPage fallbackTitle="FROID - Ciencia" html={cienciaHtml} />;
}

export function FroidTechnologyPage() {
  return <StaticInstitutionalPage fallbackTitle="FROID - Tecnologia" html={tecnologiaHtml} />;
}

export function FroidProfessionalsPage() {
  return <StaticInstitutionalPage fallbackTitle="FROID - Profissionais" html={profissionaisHtml} />;
}
