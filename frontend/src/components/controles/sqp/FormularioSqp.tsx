'use client';

import { useMemo, useState } from 'react';

import { AvisoBorrador, BotonReiniciar } from '@/components/controles/AvisoBorrador';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useBorrador } from '@/hooks/useBorrador';
import { useTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type {
  Area,
  CatalogoSqp,
  InspeccionSqpPayload,
  RespuestaSqpPayload,
  ValorSqp,
} from '@/lib/types';
import { cn, fechaDeHoy } from '@/lib/utils';

interface FormularioSqpProps {
  catalogo: CatalogoSqp;
  areas: Area[];
  onGuardar: (datos: InspeccionSqpPayload) => Promise<void>;
  guardando: boolean;
}

interface EstadoRespuesta {
  valor: ValorSqp | null;
  observaciones: string;
}

const OPCIONES: ReadonlyArray<{
  valor: ValorSqp;
  clave: 'respuestaConforme' | 'respuestaInconforme' | 'respuestaNa';
}> = [
  { valor: 'si', clave: 'respuestaConforme' },
  { valor: 'no', clave: 'respuestaInconforme' },
  { valor: 'na', clave: 'respuestaNa' },
];

/** Clases de cada botón según su estado. El "NO" resalta: es el hallazgo. */
const SELECCIONADO: Record<ValorSqp, string> = {
  si: 'border-exito bg-exito-suave text-exito',
  no: 'border-error bg-error-suave text-error',
  na: 'border-borde-fuerte bg-fondo-sutil text-texto',
};

export function FormularioSqp({
  catalogo,
  areas,
  onGuardar,
  guardando,
}: FormularioSqpProps) {
  const t = useTraduccion();

  const [fecha, setFecha] = useState(fechaDeHoy);
  const [area, setArea] = useState('');
  const [encargado, setEncargado] = useState('');
  const [cargo, setCargo] = useState('');
  const [sustancias, setSustancias] = useState('');
  const [respuestas, setRespuestas] = useState<Record<number, EstadoRespuesta>>({});

  const lineasSustancias = useMemo(
    () => sustancias.split('\n').filter((linea) => linea.trim() !== ''),
    [sustancias],
  );

  // Lo capturado sobrevive a cambiar de pestaña, salir del panel o recargar.
  // La fecha no cuenta como contenido: arranca con la de hoy sola.
  const { usuario } = useSesion();
  const hayContenido =
    area !== '' ||
    encargado.trim() !== '' ||
    cargo.trim() !== '' ||
    sustancias.trim() !== '' ||
    Object.keys(respuestas).length > 0;

  const borrador = useBorrador(
    usuario ? `${usuario.username}:sqp` : null,
    { fecha, area, encargado, cargo, sustancias, respuestas },
    hayContenido,
    (guardado) => {
      setFecha(guardado.fecha);
      setArea(guardado.area);
      setEncargado(guardado.encargado);
      setCargo(guardado.cargo);
      setSustancias(guardado.sustancias);
      setRespuestas(guardado.respuestas);
    },
  );

  /** Vacía la hoja entera. El botón de reiniciar sí borra fecha y área. */
  function limpiar() {
    setFecha(fechaDeHoy());
    setArea('');
    setEncargado('');
    setCargo('');
    setSustancias('');
    setRespuestas({});
  }

  const contestados = catalogo.puntos.filter(
    (punto) => respuestas[punto.orden]?.valor != null,
  ).length;

  const noSinObservaciones = catalogo.puntos.filter((punto) => {
    const respuesta = respuestas[punto.orden];
    return respuesta?.valor === 'no' && respuesta.observaciones.trim() === '';
  }).length;

  const faltanPuntos = catalogo.puntos.length - contestados;
  const faltaEncabezado = area === '' || encargado.trim() === '';
  const sinSustancias = lineasSustancias.length === 0;

  const puedeGuardar =
    !faltaEncabezado && faltanPuntos === 0 && noSinObservaciones === 0 && !sinSustancias;

  function responder(orden: number, valor: ValorSqp) {
    setRespuestas((previas) => ({
      ...previas,
      [orden]: {
        valor,
        // Al dejar de ser "NO", la observación deja de tener sentido.
        observaciones: valor === 'no' ? (previas[orden]?.observaciones ?? '') : '',
      },
    }));
  }

  function observar(orden: number, texto: string) {
    setRespuestas((previas) => ({
      ...previas,
      [orden]: { valor: previas[orden]?.valor ?? null, observaciones: texto },
    }));
  }

  async function guardar() {
    if (!puedeGuardar) {
      return;
    }

    const payload: RespuestaSqpPayload[] = [];

    for (const punto of catalogo.puntos) {
      const respuesta = respuestas[punto.orden];

      // `puedeGuardar` ya garantizó que están todas contestadas; esto es para
      // que el compilador lo sepa también.
      if (respuesta?.valor == null) {
        return;
      }

      payload.push({
        orden: punto.orden,
        valor: respuesta.valor,
        observaciones: respuesta.valor === 'no' ? respuesta.observaciones.trim() : null,
      });
    }

    try {
      await onGuardar({
        fecha,
        area,
        encargado: encargado.trim(),
        cargo: cargo.trim() || null,
        sustancias: lineasSustancias.join('\n'),
        respuestas: payload,
      });
    } catch {
      // El panel ya mostró el error; se conserva lo capturado.
      return;
    }

    // La fecha y el área se conservan a propósito: en un recorrido se
    // capturan varias áreas seguidas el mismo día.
    setRespuestas({});
    setSustancias('');
    setEncargado('');
    setCargo('');
    borrador.descartar();
  }

  // Se agrupa por sección para reproducir el orden del formato en papel.
  const porSeccion = catalogo.secciones.map((seccion) => ({
    seccion,
    puntos: catalogo.puntos.filter((punto) => punto.seccion === seccion),
  }));

  return (
    <div className="flex flex-col gap-5">
      <AvisoBorrador fecha={borrador.esDeOtroDia ? borrador.fecha : null} />

      <Card className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          etiqueta={t('comun.fecha')}
          name="fecha-sqp"
          type="date"
          value={fecha}
          onChange={(evento) => setFecha(evento.target.value)}
          disabled={guardando}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="area-sqp" className="text-sm font-medium text-texto">
            {t('comun.area')}
          </label>
          <select
            id="area-sqp"
            value={area}
            onChange={(evento) => setArea(evento.target.value)}
            disabled={guardando}
            className="h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario"
          >
            <option value="">—</option>
            {areas.map((opcion) => (
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
        </div>

        <Input
          etiqueta={t('sqp.encargado')}
          name="encargado-sqp"
          value={encargado}
          placeholder={t('sqp.encargadoPlaceholder')}
          onChange={(evento) => setEncargado(evento.target.value)}
          disabled={guardando}
        />

        <Input
          etiqueta={t('sqp.cargo')}
          name="cargo-sqp"
          value={cargo}
          placeholder={t('sqp.cargoPlaceholder')}
          onChange={(evento) => setCargo(evento.target.value)}
          disabled={guardando}
        />
      </Card>

      {porSeccion.map(({ seccion, puntos }) => (
        <Card key={seccion} className="flex flex-col gap-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-texto-suave">
            {seccion}
          </h3>

          {puntos.map((punto) => {
            const respuesta = respuestas[punto.orden];

            return (
              <div
                key={punto.orden}
                className="flex flex-col gap-3 border-t border-borde pt-4 first:border-t-0 first:pt-0"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <p className="text-sm text-texto">
                    <span className="mr-2 font-medium text-texto-suave">
                      {punto.codigo}
                    </span>
                    {punto.texto}
                  </p>

                  <div
                    role="radiogroup"
                    aria-label={punto.texto}
                    className="flex shrink-0 gap-2"
                  >
                    {OPCIONES.map((opcion) => {
                      const activa = respuesta?.valor === opcion.valor;

                      return (
                        <button
                          key={opcion.valor}
                          type="button"
                          role="radio"
                          aria-checked={activa}
                          onClick={() => responder(punto.orden, opcion.valor)}
                          disabled={guardando}
                          className={cn(
                            'h-tactil w-32 rounded-md border text-sm font-semibold transition-colors',
                            'disabled:cursor-not-allowed disabled:opacity-50',
                            activa
                              ? SELECCIONADO[opcion.valor]
                              : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
                          )}
                        >
                          {t(`sqp.${opcion.clave}`)}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* La observación solo aparece —y solo es obligatoria— en el NO. */}
                {respuesta?.valor === 'no' && (
                  <Textarea
                    name={`observaciones-${punto.orden}`}
                    value={respuesta.observaciones}
                    placeholder={t('sqp.observacionesPlaceholder')}
                    onChange={(evento) => observar(punto.orden, evento.target.value)}
                    disabled={guardando}
                    error={
                      respuesta.observaciones.trim() === ''
                        ? t('comun.obligatorio')
                        : undefined
                    }
                  />
                )}
              </div>
            );
          })}
        </Card>
      ))}

      <Card className="flex flex-col gap-3">
        <Textarea
          etiqueta={t('sqp.sustancias')}
          name="sustancias-sqp"
          value={sustancias}
          rows={6}
          placeholder={t('sqp.sustanciasAyuda')}
          onChange={(evento) => setSustancias(evento.target.value)}
          disabled={guardando}
        />
        <p className="text-sm text-texto-tenue">
          {t('sqp.sustanciasContador', { total: lineasSustancias.length })}
        </p>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-texto-suave">
          {faltanPuntos > 0
            ? t('sqp.faltanPuntos', { total: faltanPuntos })
            : noSinObservaciones > 0
              ? t('sqp.faltanObservaciones', { total: noSinObservaciones })
              : sinSustancias
                ? t('sqp.faltanSustancias')
                : t('sqp.progreso', {
                    contestados,
                    total: catalogo.puntos.length,
                  })}
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <BotonReiniciar
            hayContenido={hayContenido}
            deshabilitado={guardando}
            onReiniciar={() => {
              limpiar();
              borrador.descartar();
            }}
          />

          <Button
            tamano="lg"
            onClick={() => void guardar()}
            disabled={!puedeGuardar}
            cargando={guardando}
          >
            {t('sqp.guardarInspeccion')}
          </Button>
        </div>
      </div>
    </div>
  );
}
