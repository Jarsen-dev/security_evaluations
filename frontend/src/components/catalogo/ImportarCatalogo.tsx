'use client';

import { useRef, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { ErrorDeApi, URL_PLANTILLA_CATALOGO, importarCatalogoExcel } from '@/lib/api';
import { useTraduccion } from '@/lib/i18n';
import type { ErrorImportacion } from '@/lib/types';

/**
 * Carga masiva del catálogo desde un Excel.
 *
 * Los insumos nuevos se dan de alta y los que ya existen se omiten, así que
 * volver a subir un archivo no pisa lo capturado. Una fila con problemas no
 * invalida el resto: se reporta su número para corregirla en el origen.
 */
export function ImportarCatalogo({ onImportado }: { onImportado: () => void }) {
  const t = useTraduccion();
  const selectorArchivo = useRef<HTMLInputElement>(null);

  const [importando, setImportando] = useState(false);
  const [resumen, setResumen] = useState('');
  const [errores, setErrores] = useState<ErrorImportacion[]>([]);
  const [errorGeneral, setErrorGeneral] = useState('');

  async function importar(archivo: File) {
    setImportando(true);
    setResumen('');
    setErrores([]);
    setErrorGeneral('');

    try {
      const resultado = await importarCatalogoExcel(archivo);
      setResumen(
        t('importarCatalogo.resultado', {
          creados: resultado.creados,
          omitidos: resultado.omitidos,
        }),
      );
      setErrores(resultado.errores);

      if (resultado.creados > 0) {
        onImportado();
      }
    } catch (error: unknown) {
      setErrorGeneral(
        error instanceof ErrorDeApi ? error.message : t('importarCatalogo.fallo'),
      );
    } finally {
      setImportando(false);
      // Sin esto no se puede volver a elegir el mismo archivo tras corregirlo.
      if (selectorArchivo.current) {
        selectorArchivo.current.value = '';
      }
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={selectorArchivo}
          type="file"
          className="hidden"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          onChange={(evento) => {
            const archivo = evento.target.files?.[0];
            if (archivo) {
              void importar(archivo);
            }
          }}
        />

        <Button
          variante="secundario"
          cargando={importando}
          onClick={() => selectorArchivo.current?.click()}
        >
          {importando ? t('importarCatalogo.importando') : t('importarCatalogo.boton')}
        </Button>

        {/* La cookie httpOnly de sesión viaja sola en una descarga directa. */}
        <a
          href={URL_PLANTILLA_CATALOGO}
          download
          className="text-sm text-primario underline underline-offset-2 hover:text-primario-hover"
        >
          {t('importarCatalogo.plantilla')}
        </a>

      </div>

      <p className="text-sm text-texto-tenue">{t('importarCatalogo.nota')}</p>

      {resumen !== '' && (
        <p role="status" className="text-sm text-exito">
          {resumen}
        </p>
      )}

      {errorGeneral !== '' && (
        <p
          role="alert"
          className="rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          {errorGeneral}
        </p>
      )}

      {errores.length > 0 && (
        <div
          role="alert"
          className="rounded-tarjeta border border-alerta bg-alerta-suave px-4 py-3 text-sm text-texto"
        >
          <p className="font-medium">
            {t('importarCatalogo.filasConProblemas', { total: errores.length })}
          </p>
          <ul className="mt-2 flex flex-col gap-1">
            {errores.map((error) => (
              <li key={`${error.fila}-${error.mensaje}`}>
                <span className="font-medium">
                  {t('importarCatalogo.fila', { numero: error.fila })}
                </span>{' '}
                {error.mensaje}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
