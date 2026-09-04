import React, { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import {
  AccessCard,
  LinkDeDesenvolvimento,
  botaoClasse,
  campoClasse,
  postAuthJson,
} from "../components/access/AccessShell";

/**
 * Cadastro de nova senha de acesso ao portal do paciente.
 *
 * Fica fora de PatientPortalPage por dois motivos. O portal é a maior página
 * do painel — relatórios, consentimentos, pedidos de privacidade — e quem chega
 * aqui está justamente trancado do lado de fora, sem nada disso para carregar.
 * E a tela tem dois estados que não são do portal: pedir o link e, de volta do
 * e-mail, definir a senha.
 *
 * O caminho pelo Google continua na tela de acesso e resolve outro caso: quem
 * tem conta Google no mesmo endereço. Este aqui é para quem não tem.
 */

/* Mesmas chaves de PatientPortalPage e PatientInvitePage. sessionStorage, e não
   localStorage: a sessão do paciente morre com a aba. */
const PATIENT_TOKEN_KEY = "froid_patient_token";
const PATIENT_USER_KEY = "froid_patient_user";

const SENHA_MINIMA_PACIENTE = 8;

export const PatientPasswordResetPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get("token") || "", [searchParams]);
  const [identificador, setIdentificador] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [pedido, setPedido] = useState(false);
  const [devLink, setDevLink] = useState("");

  const pedirLink = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      // O mesmo campo do login aceita CPF ou e-mail, e o servidor decide pelo
      // "@" como interpretar. Quem esqueceu a senha raramente lembra qual dos
      // dois usou no aceite do convite.
      const data = await postAuthJson("/api/patient-auth/password-reset", {
        document: identificador.trim(),
      });
      setDevLink(String(data.dev_link || ""));
      setPedido(true);
    } catch (err: any) {
      setError(err.message || "Não foi possível enviar o link");
    } finally {
      setLoading(false);
    }
  };

  const definirSenha = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    if (password !== passwordConfirm) {
      setError("A confirmação da senha não confere");
      return;
    }
    setLoading(true);
    try {
      const data = await postAuthJson(
        "/api/patient-auth/password-reset/confirm",
        { token, password, password_confirm: passwordConfirm },
      );
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem(PATIENT_TOKEN_KEY, String(data.token || ""));
        if (data.patient) {
          window.sessionStorage.setItem(
            PATIENT_USER_KEY,
            JSON.stringify(data.patient),
          );
        }
      }
      navigate("/paciente", { replace: true });
    } catch (err: any) {
      setError(err.message || "Não foi possível cadastrar a nova senha");
    } finally {
      setLoading(false);
    }
  };

  const voltar = (
    <Link to="/paciente" className="mt-4 block text-center text-sm text-cyan-400">
      Voltar para o acesso do paciente
    </Link>
  );

  if (token) {
    return (
      <AccessCard
        titulo="Cadastrar nova senha"
        subtitulo="Ao concluir, as sessões abertas neste cadastro serão encerradas e você entra no portal."
      >
        <form onSubmit={definirSenha} className="space-y-3">
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            required
            minLength={SENHA_MINIMA_PACIENTE}
            autoComplete="new-password"
            placeholder={
              "nova senha (mínimo " + SENHA_MINIMA_PACIENTE + " caracteres)"
            }
            className={campoClasse}
          />
          <input
            value={passwordConfirm}
            onChange={(event) => setPasswordConfirm(event.target.value)}
            type="password"
            required
            minLength={SENHA_MINIMA_PACIENTE}
            autoComplete="new-password"
            placeholder="repita a nova senha"
            className={campoClasse}
          />
          <button disabled={loading} className={botaoClasse}>
            {loading ? "Salvando..." : "Salvar e entrar no portal"}
          </button>
        </form>
        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
        {voltar}
      </AccessCard>
    );
  }

  return (
    <AccessCard
      titulo="Nova senha de acesso"
      subtitulo="Informe o CPF ou o e-mail do seu cadastro. Enviaremos ao e-mail registrado um link para cadastrar a nova senha."
    >
      {pedido ? (
        <p className="text-sm text-slate-300">
          Se este cadastro existir no FROID e tiver e-mail registrado, o link
          acabou de ser enviado. Ele vale por uma hora e só pode ser usado uma
          vez. Confira também a caixa de spam.
        </p>
      ) : (
        <form onSubmit={pedirLink} className="space-y-3">
          <input
            value={identificador}
            onChange={(event) => setIdentificador(event.target.value)}
            required
            autoComplete="username"
            placeholder="000.000.000-00 ou seu@email.com"
            className={campoClasse}
          />
          <button disabled={loading} className={botaoClasse}>
            {loading ? "Enviando..." : "Enviar link de nova senha"}
          </button>
        </form>
      )}
      <LinkDeDesenvolvimento link={devLink} />
      {error && <p className="mt-3 text-sm text-red-400">{error}</p>}
      <p className="mt-4 text-[11px] leading-5 text-slate-500">
        O cadastro feito só com telefone não tem endereço para onde enviar o
        link. Nesse caso, peça ao profissional que reenvie o convite.
      </p>
      {voltar}
    </AccessCard>
  );
};
