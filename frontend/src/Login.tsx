import { useState } from "react";
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
      <h2>Вход в систему</h2>
      <p className="hint">Windows · браузер · серверная обработка аудио</p>
      <form onSubmit={handleSubmit} className="login-form">
        <label>
          Логин
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button className="btn btn-primary" type="submit" disabled={loading}>
          {loading ? "Вход…" : "Войти"}
        </button>
      </form>
      <p className="login-roles">
        Роли: <strong>admin</strong> — аудит и пользователи; <strong>operator</strong> — загрузка и
        редактирование; <strong>viewer</strong> — просмотр и экспорт.
      </p>
    </div>
  );
}
