import { useState } from "react";
import { APP_TAGLINE } from "./branding";
import { login, type AuthUser } from "./auth";

interface Props {
  onSuccess: (user: AuthUser) => void;
  authRequired: boolean;
}

export default function Login({ onSuccess, authRequired }: Props) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const user = await login(username, password);
      onSuccess(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка входа");
    } finally {
      setLoading(false);
    }
  };

  if (!authRequired) {
    return (
      <div className="login-panel">
        <p className="hint">Авторизация отключена (режим разработки).</p>
        <button className="btn btn-primary" onClick={() => onSuccess({ username: "dev", role: "operator" })}>
          Продолжить
        </button>
      </div>
    );
  }

  return (
    <div className="login-panel">
      <h2>Вход</h2>
      <p className="hint" style={{ textAlign: "center", marginBottom: 0 }}>
        {APP_TAGLINE}
      </p>
      <div className="login-shell carbon-panel">
        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Логин
            <input
              className="input-theme"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
            />
          </label>
          <label>
            Пароль
            <input
              className="input-theme"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn btn-primary" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Вход…" : "Войти"}
          </button>
        </form>
      </div>
      <p className="login-roles">
        Роли: <strong>admin</strong> — аудит; <strong>operator</strong> — загрузка; <strong>viewer</strong> — просмотр.
      </p>
      <p className="hint" style={{ marginTop: 12, textAlign: "center" }}>
        Первый вход: логин <strong>admin</strong>, пароль <strong>admin</strong> (если не меняли в Railway).
        <br />
        Пароль <code>DEFAULT_ADMIN_PASSWORD</code> действует только при первом создании БД.
      </p>
    </div>
  );
}
