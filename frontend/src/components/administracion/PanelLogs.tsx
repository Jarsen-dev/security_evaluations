'use client';

import { useCallback, useEffect, useState } from 'react';

import { TablaLogs } from '@/components/administracion/TablaLogs';
import { Button } from '@/components/ui/Button';
import { ErrorDeApi, listarBitacora, listarUsuariosBitacora } from '@/lib/api';
import { useTraduccion } from '@/lib/i18n';
import type { BitacoraPaginada, FiltrosBitacora } from '@/lib/types';

const SIN_FILTROS: FiltrosBitacora = {};

/** Bitácora de actividad: 50 registros por página, con filtros de fecha y usuario. */
export function PanelLogs() {
  const t = useTraduccion();

  const [datos, setDatos] = useState<BitacoraPaginada | null>(null);
  const [usuarios, setUsuarios] = useState<string[]>([]);
  const [filtros, setFiltros] = useState<FiltrosBitacora>(SIN_FILTROS);
  const [pagina, setPagina] = useState(1);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const hayFiltros = Object.values(filtros).some((valor) => valor !== undefined);

  // El catálogo del `<select>` se pide una sola vez: sale de la bitácora, así
  // que incluye a quien ya fue eliminado del sistema.
  useEffect(() => {
    let cancelado = false;

    listarUsuariosBitacora()
      .then((lista) => {
        if (!cancelado) setUsuarios(lista);
      })
      .catch(() => {
        // El filtro por usuario se queda vacío; el resto de la pantalla
        // funciona igual y no vale la pena molestar con un error.
      });

    return () => {
      cancelado = true;
    };
  }, []);

  const cargar = useCallback(async () => {
    setCargando(true);

    try {
      setDatos(await listarBitacora(filtros, pagina));
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(error instanceof ErrorDeApi ? error.message : t('logs.falloCarga'));
    } finally {
      setCargando(false);
    }
  }, [filtros, pagina, t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function cambiarFiltros(siguientes: FiltrosBitacora) {
    // Cambiar un filtro con la página 7 abierta dejaría una lista vacía sin
    // explicación: se vuelve al principio.
    setPagina(1);
    setFiltros(siguientes);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-base font-semibold text-texto">{t('logs.titulo')}</h2>
        <p className="mt-1 text-sm text-texto-suave">{t('logs.descripcion')}</p>
      </div>

      {errorCarga !== '' && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {t('comun.reintentar')}
          </Button>
        </div>
      )}

      <TablaLogs
        datos={datos}
        cargando={cargando}
        hayFiltros={hayFiltros}
        onPagina={setPagina}
        filtros={filtros}
        usuarios={usuarios}
        onFiltros={cambiarFiltros}
        onLimpiar={() => cambiarFiltros(SIN_FILTROS)}
      />
    </div>
  );
}
