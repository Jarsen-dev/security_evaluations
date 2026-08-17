'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Logo } from '@/components/ui/Logo';
import { ErrorDeApi, iniciarSesion } from '@/lib/api';

const esquemaLogin = z.object({
  username: z.string().min(1, 'Escribe tu usuario.'),
  password: z.string().min(1, 'Escribe tu contraseña.'),
});

type ErroresCampo = Partial<Record<'username' | 'password', string>>;

export default function PaginaLogin() {
  const router = useRouter();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [errores, setErrores] = useState<ErroresCampo>({});
  const [errorGeneral, setErrorGeneral] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function manejarEnvio(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErrorGeneral('');

    const resultado = esquemaLogin.safeParse({ username, password });
    if (!resultado.success) {
      const nuevos: ErroresCampo = {};
      for (const problema of resultado.error.issues) {
        const campo = problema.path[0];
        if (campo === 'username' || campo === 'password') {
          nuevos[campo] = problema.message;
        }
      }
      setErrores(nuevos);
      return;
    }

    setErrores({});
    setEnviando(true);

    try {
      await iniciarSesion(resultado.data);
      // `refresh` obliga al middleware a reevaluar la cookie recién puesta;
      // sin él, la navegación usaría el estado previo cacheado.
      router.refresh();
      router.replace('/cuestionarios');
    } catch (error) {
      setErrorGeneral(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo iniciar sesión. Intenta de nuevo.',
      );
      setEnviando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <header className="mb-8 text-center">
          <Logo alto={56} sobreFondoOscuro className="mb-5" />

          <h1 className="text-xl font-semibold text-texto">
            Evaluación de Conocimientos
          </h1>
          <p className="mt-1 text-sm text-texto-suave">Acceso al panel de administración</p>
        </header>

        <form
          onSubmit={manejarEnvio}
          className="flex flex-col gap-4 rounded-tarjeta border border-borde bg-fondo-elevado p-6"
          noValidate
        >
          <Input
            etiqueta="Usuario"
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(evento) => setUsername(evento.target.value)}
            error={errores.username}
            disabled={enviando}
          />

          <Input
            etiqueta="Contraseña"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(evento) => setPassword(evento.target.value)}
            error={errores.password}
            disabled={enviando}
          />

          {errorGeneral && (
            <p
              role="alert"
              className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
            >
              {errorGeneral}
            </p>
          )}

          <Button type="submit" tamano="lg" cargando={enviando} className="mt-2 w-full">
            {enviando ? 'Verificando…' : 'Entrar'}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-texto-tenue">
          El personal que contesta cuestionarios no necesita cuenta: accede por la
          liga o el código QR.
        </p>
      </div>
    </main>
  );
}
