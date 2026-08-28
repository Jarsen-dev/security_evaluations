'use client';

import { useEffect, useState } from 'react';

import { CampoFotos } from '@/components/controles/CampoFotos';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { ErrorDeApi, guardarCierre, obtenerCierre, urlFotoControl } from '@/lib/api';
import { useTraduccion } from '@/lib/i18n';
import type { CierrePayload, DetalleCierre, Hallazgo } from '@/lib/types';

/** Tope de evidencias de verificación; el servidor aplica el mismo. */
const MAX_FOTOS = 4;

const VACIO: CierrePayload = {
  hora_hallazgo: '',
  ubicacion: '',
  accion_inmediata: '',
  responsable_accion: '',
  hora_cierre: '',
  accion_pendiente: null,
};

interface ModalCierreHallazgoProps {
  abierto: boolean;
  control: string;
  registroId: string | null;
  onCerrar: () => void;
  /** Se llama tras guardar, para que el panel recargue su listado. */
  onGuardado: (mensaje: string) => void;
  onError: (mensaje: string) => void;
}

/**
 * Cierre de los hallazgos de una hoja.
 *
 * Es el bloque "Acción en caso de anomalía" del formato en papel, sacado del
 * formulario de captura: la solución rara vez ocurre durante la inspección, y
 * dentro del formulario solo se podía anotar en ese momento.
 *
 * Arriba van los problemas en solo lectura, con su evidencia, para que quien
 * cierra vea qué está cerrando sin ir a buscar la hoja.
 */
export function ModalCierreHallazgo({
  abierto,
  control,
  registroId,
  onCerrar,
  onGuardado,
  onError,
}: ModalCierreHallazgoProps) {
  const t = useTraduccion();

  const [detalle, setDetalle] = useState<DetalleCierre | null>(null);
  const [datos, setDatos] = useState<CierrePayload>(VACIO);
  const [fotos, setFotos] = useState<File[]>([]);
  const [cargando, setCargando] = useState(false);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!abierto || registroId === null) {
      return;
    }

    let cancelado = false;
    setCargando(true);
    setDetalle(null);
    setFotos([]);

    obtenerCierre(control, registroId)
      .then((datosCierre) => {
        if (cancelado) {
          return;
        }

        setDetalle(datosCierre);
        // Si ya hay cierre, el modal abre con lo guardado y actualizará.
        setDatos(
          datosCierre.cierre
            ? {
                hora_hallazgo: datosCierre.cierre.hora_hallazgo,
                ubicacion: datosCierre.cierre.ubicacion,
                accion_inmediata: datosCierre.cierre.accion_inmediata,
                responsable_accion: datosCierre.cierre.responsable_accion,
                hora_cierre: datosCierre.cierre.hora_cierre,
                accion_pendiente: datosCierre.cierre.accion_pendiente,
              }
            : VACIO,
        );
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          onError(error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'));
        }
      })
      .finally(() => {
        if (!cancelado) {
          setCargando(false);
        }
      });

    return () => {
      cancelado = true;
    };
    // `onError` y `t` se dejan fuera a propósito: son estables y volverlos a
    // listar solo relanzaría la carga.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abierto, control, registroId]);

  function cambiar(campo: keyof CierrePayload, valor: string) {
    setDatos((previo) => ({ ...previo, [campo]: valor }));
  }

  const yaCerrado = detalle?.cierre != null;

  const completo =
    datos.hora_hallazgo !== '' &&
    datos.ubicacion.trim() !== '' &&
    datos.accion_inmediata.trim() !== '' &&
    datos.responsable_accion.trim() !== '' &&
    datos.hora_cierre !== '';

  async function guardar() {
    if (!completo || registroId === null) {
      return;
    }

    setGuardando(true);

    try {
      await guardarCierre(
        control,
        registroId,
        {
          ...datos,
          ubicacion: datos.ubicacion.trim(),
          accion_inmediata: datos.accion_inmediata.trim(),
          responsable_accion: datos.responsable_accion.trim(),
          accion_pendiente: (datos.accion_pendiente ?? '').trim() || null,
        },
        fotos,
        yaCerrado,
      );

      onGuardado(t(yaCerrado ? 'cierre.actualizado' : 'cierre.guardado'));
      onCerrar();
    } catch (error) {
      onError(error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'));
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={t('cierre.titulo')}
      ancho="lg"
      pie={
        <>
          <Button variante="fantasma" onClick={onCerrar} disabled={guardando}>
            {t('comun.cancelar')}
          </Button>
          <Button
            onClick={() => void guardar()}
            disabled={!completo || cargando}
            cargando={guardando}
          >
            {t('cierre.guardar')}
          </Button>
        </>
      }
    >
      {cargando ? (
        <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
      ) : (
        <div className="flex flex-col gap-5">
          <ListaHallazgos hallazgos={detalle?.hallazgos ?? []} />

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              etiqueta={t('cierre.horaHallazgo')}
              name="cierre-hora-hallazgo"
              type="time"
              value={datos.hora_hallazgo}
              onChange={(evento) => cambiar('hora_hallazgo', evento.target.value)}
              disabled={guardando}
            />

            <Input
              etiqueta={t('cierre.ubicacion')}
              name="cierre-ubicacion"
              value={datos.ubicacion}
              onChange={(evento) => cambiar('ubicacion', evento.target.value)}
              disabled={guardando}
              maxLength={200}
            />
          </div>

          {/* La descripción NO se captura: es el texto que ya escribió quien
              levantó el hallazgo, aquí solo como referencia de qué se cierra. */}
          <Descripcion hallazgos={detalle?.hallazgos ?? []} />

          <Textarea
            etiqueta={t('cierre.accionInmediata')}
            name="cierre-accion"
            placeholder={t('cierre.accionInmediataPlaceholder')}
            value={datos.accion_inmediata}
            onChange={(evento) => cambiar('accion_inmediata', evento.target.value)}
            disabled={guardando}
            maxLength={2000}
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              etiqueta={t('cierre.responsableAccion')}
              name="cierre-responsable"
              placeholder={t('cierre.responsableAccionPlaceholder')}
              value={datos.responsable_accion}
              onChange={(evento) => cambiar('responsable_accion', evento.target.value)}
              disabled={guardando}
              maxLength={150}
            />

            <Input
              etiqueta={t('cierre.horaCierre')}
              name="cierre-hora-cierre"
              type="time"
              value={datos.hora_cierre}
              onChange={(evento) => cambiar('hora_cierre', evento.target.value)}
              disabled={guardando}
            />
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium text-texto">
              {t('cierre.verificacion')}
            </span>
            <p className="text-sm text-texto-tenue">{t('cierre.verificacionAyuda')}</p>

            {/* Al actualizar, las que ya estaban siguen ahí mientras no se
                elijan nuevas: el servidor solo reemplaza si vienen fotos. */}
            {yaCerrado && (detalle?.cierre?.fotos.length ?? 0) > 0 && fotos.length === 0 && (
              <ul className="flex flex-wrap gap-2">
                {detalle?.cierre?.fotos.map((id, indice) => (
                  <li key={id}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- la
                        sirve la API con la cookie de sesión; next/image no
                        puede optimizar una ruta autenticada. */}
                    <img
                      src={urlFotoControl(id)}
                      alt={t('fotos.numero', { numero: indice + 1 })}
                      className="h-24 w-24 rounded-md border border-borde object-cover"
                    />
                  </li>
                ))}
              </ul>
            )}

            <CampoFotos
              id={`cierre-fotos-${control}`}
              fotos={fotos}
              onCambiar={setFotos}
              onError={onError}
              maximo={MAX_FOTOS}
              deshabilitado={guardando}
            />
          </div>

          <Textarea
            etiqueta={t('cierre.accionPendiente')}
            ayuda={t('cierre.accionPendienteAyuda')}
            name="cierre-pendiente"
            value={datos.accion_pendiente ?? ''}
            onChange={(evento) => cambiar('accion_pendiente', evento.target.value)}
            disabled={guardando}
            maxLength={2000}
          />

          {!completo && (
            <p className="text-sm text-texto-tenue">{t('cierre.faltanCampos')}</p>
          )}
        </div>
      )}
    </Modal>
  );
}

/** Los problemas de la hoja, con su evidencia. Solo lectura. */
export function ListaHallazgos({ hallazgos }: { hallazgos: Hallazgo[] }) {
  const t = useTraduccion();

  if (hallazgos.length === 0) {
    return <p className="text-sm text-texto-suave">{t('cierre.sinProblemas')}</p>;
  }

  return (
    <section className="flex flex-col gap-3 rounded-md border border-error bg-error-suave/30 p-4">
      <h3 className="text-sm font-semibold text-texto">{t('cierre.problemas')}</h3>

      <ul className="flex flex-col gap-3">
        {hallazgos.map((hallazgo, indice) => (
          <li
            key={`${hallazgo.orden ?? 'registro'}-${indice}`}
            className="flex flex-col gap-2 border-t border-borde pt-3 first:border-t-0 first:pt-0"
          >
            <p className="text-sm font-medium text-texto">
              {hallazgo.orden !== null && (
                <span className="mr-2 text-texto-tenue">{hallazgo.orden + 1}.</span>
              )}
              {hallazgo.etiqueta}
            </p>

            {hallazgo.observaciones && (
              <p className="text-sm text-texto-suave">{hallazgo.observaciones}</p>
            )}

            {hallazgo.fotos.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {hallazgo.fotos.map((id, posicion) => (
                  <li key={id}>
                    <a href={urlFotoControl(id)} target="_blank" rel="noreferrer">
                      {/* eslint-disable-next-line @next/next/no-img-element -- ver arriba */}
                      <img
                        src={urlFotoControl(id)}
                        alt={t('fotos.numero', { numero: posicion + 1 })}
                        className="h-20 w-20 rounded-md border border-borde object-cover"
                      />
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

/** La descripción del problema, derivada de las observaciones. */
function Descripcion({ hallazgos }: { hallazgos: Hallazgo[] }) {
  const t = useTraduccion();

  const texto = hallazgos
    .map((hallazgo) => hallazgo.observaciones)
    .filter((observacion): observacion is string => Boolean(observacion))
    .join('\n');

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-sm font-medium text-texto">{t('cierre.descripcion')}</span>
      <p className="whitespace-pre-line rounded-md border border-borde bg-fondo-sutil px-3 py-2 text-sm text-texto-suave">
        {texto || '—'}
      </p>
      <p className="text-sm text-texto-tenue">{t('cierre.descripcionAyuda')}</p>
    </div>
  );
}
