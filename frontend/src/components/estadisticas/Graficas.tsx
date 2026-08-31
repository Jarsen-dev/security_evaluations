'use client';

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ReactNode } from 'react';

import { COLORES, COLOR_POR_RANGO, ESTILO_TOOLTIP } from '@/components/estadisticas/colores';
import { Card } from '@/components/ui/Card';
import { bilingue, unaLinea, useTraduccion } from '@/lib/i18n';
import type {
  EstadisticaArea,
  EstadisticaPregunta,
  PuntoLineaTiempo,
  RangoDistribucion,
} from '@/lib/types';

const ALTURA = 300;
const TOP_PREGUNTAS = 10;

/** Contenedor común: título, descripción y estado vacío. */
function Panel({
  titulo,
  descripcion,
  hayDatos,
  children,
}: {
  titulo: string;
  descripcion?: string;
  hayDatos: boolean;
  children: ReactNode;
}) {
  const t = useTraduccion();

  return (
    <Card>
      <h2 className="font-medium text-texto">{bilingue(titulo)}</h2>
      {descripcion && <p className="mt-0.5 text-sm text-texto-tenue">{bilingue(descripcion)}</p>}

      <div className="mt-4" style={{ height: ALTURA }}>
        {hayDatos ? (
          <ResponsiveContainer width="100%" height="100%">
            {children as React.ReactElement}
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-texto-tenue">
            {bilingue(t('graficas.sinDatos'))}
          </div>
        )}
      </div>
    </Card>
  );
}

const EJE = { stroke: COLORES.texto, fontSize: 12 };

// --- 1. Participación por área ---------------------------------------------

export function GraficaParticipacion({ datos }: { datos: EstadisticaArea[] }) {
  const t = useTraduccion();
  const hayMetas = datos.some((fila) => fila.meta !== null);

  return (
    <Panel
      titulo={t('graficas.participacion')}
      descripcion={
        hayMetas
          ? t('graficas.participacionConMetas')
          : t('graficas.participacionSinMetas')
      }
      hayDatos={datos.length > 0}
    >
      <BarChart data={datos} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORES.rejilla} vertical={false} />
        <XAxis dataKey="label" tick={EJE} angle={-25} textAnchor="end" height={60} />
        <YAxis tick={EJE} allowDecimals={false} />
        <Tooltip contentStyle={ESTILO_TOOLTIP} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
        <Legend wrapperStyle={{ fontSize: 12, color: COLORES.texto }} />
        <Bar
          dataKey="intentos"
          name={unaLinea(t('cuestionarios.respuestas'))}
          fill={COLORES.primario}
          radius={[4, 4, 0, 0]}
        />
        {hayMetas && (
          <Bar
            dataKey="meta"
            name={unaLinea(t('graficas.meta'))}
            fill={COLORES.meta}
            radius={[4, 4, 0, 0]}
          />
        )}
      </BarChart>
    </Panel>
  );
}

// --- 2. Calificación promedio por área -------------------------------------

export function GraficaPromedioPorArea({
  datos,
  umbral,
}: {
  datos: EstadisticaArea[];
  umbral: number;
}) {
  const t = useTraduccion();

  // Solo áreas con intentos, ordenadas de mayor a menor promedio.
  const ordenados = datos
    .filter((fila) => fila.intentos > 0 && fila.promedio !== null)
    .sort((a, b) => (b.promedio ?? 0) - (a.promedio ?? 0));

  return (
    <Panel
      titulo={t('graficas.promedioArea')}
      descripcion={t('graficas.promedioAreaDetalle', { umbral })}
      hayDatos={ordenados.length > 0}
    >
      <BarChart
        data={ordenados}
        layout="vertical"
        margin={{ top: 8, right: 16, left: 20, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={COLORES.rejilla} horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={EJE} />
        <YAxis type="category" dataKey="label" tick={EJE} width={90} />
        <Tooltip
          contentStyle={ESTILO_TOOLTIP}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          formatter={(valor: number) => [`${valor}%`, unaLinea(t('graficas.promedio'))]}
        />
        <Bar dataKey="promedio" radius={[0, 4, 4, 0]}>
          {ordenados.map((fila) => (
            <Cell
              key={fila.area}
              fill={(fila.promedio ?? 0) >= umbral ? COLORES.exito : COLORES.error}
            />
          ))}
        </Bar>
      </BarChart>
    </Panel>
  );
}

// --- 3. Distribución de calificaciones -------------------------------------

export function GraficaDistribucion({ datos }: { datos: RangoDistribucion[] }) {
  const t = useTraduccion();
  const hayDatos = datos.some((fila) => fila.cantidad > 0);

  return (
    <Panel
      titulo={t('graficas.distribucion')}
      descripcion={t('graficas.distribucionDetalle')}
      hayDatos={hayDatos}
    >
      <BarChart data={datos} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORES.rejilla} vertical={false} />
        <XAxis dataKey="rango" tick={EJE} />
        <YAxis tick={EJE} allowDecimals={false} />
        <Tooltip
          contentStyle={ESTILO_TOOLTIP}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          formatter={(valor: number) => [valor, unaLinea(t('metas.personas'))]}
        />
        <Bar dataKey="cantidad" radius={[4, 4, 0, 0]}>
          {datos.map((fila) => (
            <Cell key={fila.rango} fill={COLOR_POR_RANGO[fila.rango] ?? COLORES.primario} />
          ))}
        </Bar>
      </BarChart>
    </Panel>
  );
}

// --- 4. Preguntas con mayor índice de error --------------------------------

export function GraficaPreguntasFalladas({ datos }: { datos: EstadisticaPregunta[] }) {
  const t = useTraduccion();

  const top = datos
    .filter((pregunta) => pregunta.total_respuestas > 0)
    .sort((a, b) => (b.porcentaje_error ?? 0) - (a.porcentaje_error ?? 0))
    .slice(0, TOP_PREGUNTAS)
    .map((pregunta) => ({
      ...pregunta,
      // El eje no puede mostrar la pregunta completa; el tooltip sí la trae.
      etiqueta:
        pregunta.texto.length > 42 ? `${pregunta.texto.slice(0, 42)}…` : pregunta.texto,
    }));

  return (
    <Panel
      titulo={t('graficas.falladas')}
      descripcion={t('graficas.falladasDetalle')}
      hayDatos={top.length > 0}
    >
      <BarChart
        data={top}
        layout="vertical"
        margin={{ top: 8, right: 16, left: 20, bottom: 0 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke={COLORES.rejilla} horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tick={EJE} unit="%" />
        <YAxis type="category" dataKey="etiqueta" tick={{ ...EJE, fontSize: 11 }} width={230} />
        <Tooltip
          contentStyle={ESTILO_TOOLTIP}
          cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          formatter={(valor: number, _nombre, entrada) => [
            `${valor}% (${entrada.payload.incorrectas} de ${entrada.payload.total_respuestas})`,
            unaLinea(t('graficas.incorrectas')),
          ]}
          labelFormatter={(_etiqueta, carga) => carga?.[0]?.payload?.texto ?? ''}
        />
        <Bar dataKey="porcentaje_error" fill={COLORES.error} radius={[0, 4, 4, 0]} />
      </BarChart>
    </Panel>
  );
}

// --- 5. Respuestas por día -------------------------------------------------

export function GraficaLineaTiempo({ datos }: { datos: PuntoLineaTiempo[] }) {
  const t = useTraduccion();

  return (
    <Panel
      titulo={t('graficas.porDia')}
      descripcion={t('graficas.porDiaDetalle')}
      hayDatos={datos.length > 0}
    >
      <LineChart data={datos} margin={{ top: 8, right: 16, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORES.rejilla} />
        <XAxis dataKey="fecha" tick={EJE} />
        <YAxis yAxisId="izq" tick={EJE} allowDecimals={false} />
        <YAxis yAxisId="der" orientation="right" domain={[0, 100]} tick={EJE} />
        <Tooltip contentStyle={ESTILO_TOOLTIP} />
        <Legend wrapperStyle={{ fontSize: 12, color: COLORES.texto }} />
        <Line
          yAxisId="izq"
          type="monotone"
          dataKey="cantidad"
          name={unaLinea(t('cuestionarios.respuestas'))}
          stroke={COLORES.primario}
          strokeWidth={2}
          dot={{ r: 3 }}
        />
        <Line
          yAxisId="der"
          type="monotone"
          dataKey="promedio"
          name={unaLinea(t('graficas.promedioPorcentaje'))}
          stroke={COLORES.exito}
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={{ r: 3 }}
        />
      </LineChart>
    </Panel>
  );
}
