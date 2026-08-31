'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { bilingue, unaLinea, useIdioma } from '@/lib/i18n';
import type { MesPendientePci } from '@/lib/types';

/**
 * Los meses que el sistema cerró y nadie ha explicado.
 *
 * Se pinta arriba del todo y no se puede descartar: es la única forma de que
 * el hueco no se quede ahí para siempre. Lo que **no** hace es bloquear la
 * captura del mes en curso — castigar al operador de hoy por el descuido de
 * otro no completa ningún histórico.
 *
 * Trata los pendientes como lista y no como "el mes anterior": con un hueco de
 * tres meses, el singular dejaría dos invisibles.
 */
interface SolicitudUrgenteProps {
  pendientes: MesPendientePci[];
  onGuardar: (anio: number, mes: number, motivo: string) => Promise<void>;
  guardando: boolean;
}

export function SolicitudUrgente({
  pendientes,
  onGuardar,
  guardando,
}: SolicitudUrgenteProps) {
  const { t, locale } = useIdioma();
  const [motivos, setMotivos] = useState<Record<string, string>>({});

  if (pendientes.length === 0) {
    return null;
  }

  function clave(pendiente: MesPendientePci): string {
    return `${pendiente.anio}-${pendiente.mes}`;
  }

  return (
    <section
      role="alert"
      className="flex flex-col gap-4 rounded-tarjeta border border-error bg-error-suave px-5 py-4"
    >
      <div>
        <h2 className="text-base font-semibold text-error">
          {bilingue(t('pciMtto.urgenteTitulo'))}
        </h2>
        <p className="mt-1 text-sm text-texto-suave">
          {bilingue(t('pciMtto.urgenteDetalle'))}
        </p>
      </div>

      <ul className="flex flex-col gap-4">
        {pendientes.map((pendiente) => {
          const id = clave(pendiente);
          const texto = motivos[id] ?? '';
          const nombreMes = new Intl.DateTimeFormat(locale, {
            month: 'long',
            year: 'numeric',
          }).format(new Date(pendiente.anio, pendiente.mes - 1, 1));

          return (
            <li key={id} className="flex flex-col gap-2">
              <Textarea
                etiqueta={nombreMes}
                name={`motivo-${id}`}
                rows={2}
                value={texto}
                placeholder={unaLinea(t('pciMtto.motivoPlaceholder'))}
                onChange={(evento) =>
                  setMotivos((previos) => ({
                    ...previos,
                    [id]: evento.target.value,
                  }))
                }
                disabled={guardando}
                maxLength={2000}
              />

              <div className="flex justify-end">
                <Button
                  variante="peligro"
                  onClick={() =>
                    void onGuardar(pendiente.anio, pendiente.mes, texto.trim())
                  }
                  disabled={texto.trim() === ''}
                  cargando={guardando}
                >
                  {bilingue(t('pciMtto.urgenteGuardar'))}
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
