'use client';

import { useEffect, useState } from 'react';

import { useIdioma } from '@/lib/i18n';
import { determinarTurno, type Turno } from '@/lib/turno';
import { cn } from '@/lib/utils';

/**
 * Ayuda visual del encabezado: en qué turno está la planta ahora mismo.
 *
 * No es el dato que se guarda en ningún registro —eso lo calcula el backend
 * al confirmar un control (ver `automatico` en `controles_catalogo.py`)—,
 * así que basta con la hora del navegador y refrescarla cada minuto.
 */
export function IndicadorTurno() {
  const { t } = useIdioma();

  // Arranca en `null` y el turno se calcula en un efecto, igual que
  // `ProveedorIdioma` hace con el idioma guardado: resolverlo durante el
  // render daría un HTML distinto al del servidor y Next descartaría la
  // hidratación. Aquí no es una diferencia teórica —el contenedor del SSR
  // corre en UTC y la planta en UTC-6, así que a las 15:00 el servidor
  // pintaba 🌙 y el navegador ☀️— y además el servidor **nunca** puede saber
  // la zona horaria de quien mira: no se arregla poniéndole TZ al contenedor.
  const [turno, setTurno] = useState<Turno | null>(null);

  useEffect(() => {
    setTurno(determinarTurno());
    const intervalo = setInterval(() => setTurno(determinarTurno()), 60_000);
    return () => clearInterval(intervalo);
  }, []);

  // En el servidor y hasta hidratar no se dibuja nada: es preferible que la
  // insignia aparezca un instante después a que anuncie el turno equivocado.
  if (turno === null) {
    return null;
  }

  const esNoche = turno === 'noche';

  return (
    <span
      aria-label={t(esNoche ? 'encabezado.turnoNocheAyuda' : 'encabezado.turnoDiaAyuda')}
      className={cn(
        'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-semibold',
        esNoche
          ? 'border-turno-noche bg-turno-noche-suave text-turno-noche'
          : 'border-alerta bg-alerta-suave text-alerta',
      )}
    >
      <span aria-hidden="true">{esNoche ? '🌙' : '☀️'}</span>
      {t(esNoche ? 'encabezado.turnoNoche' : 'encabezado.turnoDia')}
    </span>
  );
}
