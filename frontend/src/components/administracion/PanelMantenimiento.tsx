'use client';

import { useCallback, useEffect, useState } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { ErrorDeApi, obtenerMantenimiento } from '@/lib/api';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { copiarAlPortapapeles } from '@/lib/navegador';
import type { AccesoPgAdmin, Mantenimiento } from '@/lib/types';

/**
 * Acceso rápido a pgAdmin.
 *
 * pgAdmin no admite iniciar sesión desde una liga externa: su formulario
 * exige un token CSRF propio, así que ningún enlace ni formulario de fuera
 * puede autenticarse. Lo más cerca del "acceso de un clic" que sí funciona
 * es abrir la pestaña con las credenciales ya en el portapapeles.
 */
const TEXTOS: Record<
  AccesoPgAdmin['entorno'],
  { titulo: ClaveTraduccion; detalle: ClaveTraduccion }
> = {
  local: { titulo: 'mantenimiento.local', detalle: 'mantenimiento.localDetalle' },
  produccion: {
    titulo: 'mantenimiento.produccion',
    detalle: 'mantenimiento.produccionDetalle',
  },
};

export function PanelMantenimiento() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  const [datos, setDatos] = useState<Mantenimiento | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const cargar = useCallback(async () => {
    try {
      setDatos(await obtenerMantenimiento());
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('mantenimiento.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function abrir(acceso: AccesoPgAdmin) {
    if (datos === null) {
      return;
    }

    const credenciales = `${datos.email} / ${datos.password}`;

    // Se copia ANTES de abrir la pestaña, y el orden importa: entrando por
    // la IP de la LAN no hay `navigator.clipboard` y el respaldo es
    // `document.execCommand('copy')`, que EXIGE que el documento tenga el
    // foco. Abrir primero se lo lleva a la pestaña nueva y la copia falla en
    // silencio, que es justo lo que hace útil al botón.
    //
    // `copiarAlPortapapeles` y no `navigator.clipboard`: por HTTP esa API ni
    // siquiera existe, no es que falle (ver regla 5 del CLAUDE.md).
    const copiado = await copiarAlPortapapeles(`${datos.email}\t${datos.password}`);

    // El `await` de arriba es de microsegundos, así que la activación del
    // clic sigue vigente y el navegador no lo toma por ventana emergente.
    window.open(acceso.url, '_blank', 'noopener,noreferrer');

    mostrarToast(
      copiado
        ? t('mantenimiento.copiado')
        : t('mantenimiento.falloCopiar', { credenciales }),
      copiado ? 'exito' : 'error',
    );
  }

  if (cargando) {
    return <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>;
  }

  if (errorCarga !== '') {
    return (
      <div
        role="alert"
        className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
      >
        <span>{errorCarga}</span>
        <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
          {t('comun.reintentar')}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold text-texto">
          {t('mantenimiento.titulo')}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">{t('mantenimiento.descripcion')}</p>
      </div>

      <p className="rounded-tarjeta border border-borde bg-fondo-sutil px-4 py-3 text-sm text-texto-suave">
        {t('mantenimiento.aviso')}
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        {datos?.accesos.map((acceso) => (
          <Card key={acceso.entorno}>
            <div className="flex h-full flex-col gap-3">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-semibold text-texto">
                  {t(TEXTOS[acceso.entorno].titulo)}
                </h3>
                {!acceso.disponible && (
                  <Badge tono="alerta">{t('mantenimiento.noConfigurado')}</Badge>
                )}
              </div>

              <p className="text-sm text-texto-suave">
                {t(TEXTOS[acceso.entorno].detalle)}
              </p>

              <p className="break-all font-mono text-xs text-texto-tenue">
                {acceso.disponible
                  ? acceso.url
                  : t('mantenimiento.noConfiguradoDetalle')}
              </p>

              <div className="mt-auto pt-2">
                <Button
                  disabled={!acceso.disponible}
                  onClick={() => void abrir(acceso)}
                >
                  {t('mantenimiento.abrir')}
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>

      {datos !== null && (
        <Card>
          <h3 className="text-sm font-semibold text-texto">
            {t('mantenimiento.credenciales')}
          </h3>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-texto-suave">{t('usuarios.email')}</dt>
            <dd className="font-mono text-texto">{datos.email || '—'}</dd>
            <dt className="text-texto-suave">{t('usuarios.contrasena')}</dt>
            <dd className="font-mono text-texto">{datos.password || '—'}</dd>
          </dl>
        </Card>
      )}
    </div>
  );
}
