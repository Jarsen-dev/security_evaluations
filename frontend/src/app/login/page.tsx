'use client';

import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';
import { z } from 'zod';

import { SelectorIdioma } from '@/components/SelectorIdioma';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Logo } from '@/components/ui/Logo';
import { ErrorDeApi, iniciarSesion } from '@/lib/api';
import { ProveedorIdioma, useTraduccion } from '@/lib/i18n';

// Los mensajes se resuelven al validar, no al declarar el esquema: el idioma
// puede cambiar entre un render y otro.
const esquemaLogin = z.object({
  username: z.string().min(1, 'faltaUsuario'),
  password: z.string().min(1, 'faltaContrasena'),
});

type ErroresCampo = Partial<Record<'username' | 'password', string>>;

/**
 * La pantalla de acceso vive fuera del grupo `(panel)`, así que monta su
 * propio proveedor de idioma: quien todavía no entra también debe poder leerla
 * en su lengua.
 */
export default function PaginaLogin() {
  return (
    <ProveedorIdioma>
      <FormularioLogin />
    </ProveedorIdioma>
  );
}

function FormularioLogin() {
  const router = useRouter();
  const t = useTraduccion();

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
        if (campo === 'username') {
          nuevos.username = t('login.faltaUsuario');
        }
        if (campo === 'password') {
          nuevos.password = t('login.faltaContrasena');
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
          : t('login.fallo'),
      );
      setEnviando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {/* También aquí: quien todavía no entra tiene que poder leer la
            pantalla en su idioma. */}
        <div className="mb-4 flex justify-end">
          <SelectorIdioma />
        </div>

        <header className="mb-8 text-center">
          <Logo alto={56} sobreFondoOscuro className="mb-5" />

          <h1 className="text-xl font-semibold text-texto">{t('login.titulo')}</h1>
          <p className="mt-1 text-sm text-texto-suave">{t('login.subtitulo')}</p>
        </header>

        <form
          onSubmit={manejarEnvio}
          className="flex flex-col gap-4 rounded-tarjeta border border-borde bg-fondo-elevado p-6"
          noValidate
        >
          <Input
            etiqueta={t('login.usuario')}
            name="username"
            autoComplete="username"
            autoFocus
            value={username}
            onChange={(evento) => setUsername(evento.target.value)}
            error={errores.username}
            disabled={enviando}
          />

          <Input
            etiqueta={t('login.contrasena')}
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
            {enviando ? t('login.verificando') : t('login.entrar')}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-texto-tenue">{t('login.nota')}</p>
      </div>
    </main>
  );
}
