'use client';

import { useCallback, useEffect, useState } from 'react';

import { ModalPunto, type DatosPunto } from '@/components/rondines/ModalPunto';
import { ModalQrPunto } from '@/components/rondines/ModalQrPunto';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  actualizarPuntoRondin,
  crearPuntoRondin,
  descargarQrPuntos,
  eliminarPuntoRondin,
  listarPuntosRondin,
} from '@/lib/api';
import { bilingue, useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { PuntoRondin, PuntoRondinPayload } from '@/lib/types';

function aPayload(datos: DatosPunto): PuntoRondinPayload {
  return {
    numero: Number(datos.numero),
    nombre: datos.nombre.trim(),
    ubicacion: datos.ubicacion.trim() || null,
    activo: datos.activo,
  };
}

export function PanelPuntos() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  // La API rechaza con 403 lo que este usuario no puede hacer; aquí solo se
  // esconden los botones para no ofrecerlo.
  const puedeEditar = puede('rondines', 'editar');

  const [puntos, setPuntos] = useState<PuntoRondin[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [modalAbierto, setModalAbierto] = useState(false);
  const [editando, setEditando] = useState<PuntoRondin | null>(null);
  const [guardando, setGuardando] = useState(false);

  const [verQr, setVerQr] = useState<PuntoRondin | null>(null);
  const [porEliminar, setPorEliminar] = useState<PuntoRondin | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [imprimiendo, setImprimiendo] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);

    try {
      setPuntos(await listarPuntosRondin());
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('puntosRondin.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function mostrarFallo(error: unknown, respaldo: ClaveTraduccion) {
    mostrarToast(error instanceof ErrorDeApi ? error.message : t(respaldo), 'error');
  }

  async function guardar(datos: DatosPunto) {
    setGuardando(true);

    try {
      if (editando === null) {
        await crearPuntoRondin(aPayload(datos));
        mostrarToast(t('puntosRondin.creado'), 'exito');
      } else {
        await actualizarPuntoRondin(editando.id, aPayload(datos));
        mostrarToast(t('puntosRondin.actualizadoOk'), 'exito');
      }

      setModalAbierto(false);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'puntosRondin.falloGuardar');
    } finally {
      setGuardando(false);
    }
  }

  async function imprimir() {
    setImprimiendo(true);

    try {
      await descargarQrPuntos();
    } catch (error: unknown) {
      // El endpoint responde 422 si no hay puntos activos: se avisa en un
      // toast en vez de guardar el JSON del error como si fuera el PDF.
      mostrarFallo(error, 'puntosRondin.falloImprimir');
    } finally {
      setImprimiendo(false);
    }
  }

  async function confirmarEliminacion() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarPuntoRondin(porEliminar.id);
      mostrarToast(t('puntosRondin.eliminado'), 'exito');
      setPorEliminar(null);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'puntosRondin.falloEliminar');
    } finally {
      setEliminando(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-base font-semibold text-texto">
            {bilingue(t('puntosRondin.titulo'))}
          </h2>
          <p className="mt-1 text-sm text-texto-suave">
            {bilingue(t('puntosRondin.descripcion'))}
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variante="secundario"
            cargando={imprimiendo}
            onClick={() => void imprimir()}
          >
            {bilingue(t('puntosRondin.imprimir'))}
          </Button>

          <Button
            onClick={() => {
              setEditando(null);
              setModalAbierto(true);
            }}
          >
            {bilingue(t('puntosRondin.nuevo'))}
          </Button>
        </div>
      </div>

      {cargando ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : errorCarga !== '' ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {bilingue(t('comun.reintentar'))}
          </Button>
        </div>
      ) : puntos.length === 0 ? (
        <div className="rounded-tarjeta border border-dashed border-borde px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto">{bilingue(t('puntosRondin.vacio'))}</p>
          <p className="mt-2 text-sm text-texto-suave">{bilingue(t('puntosRondin.vacioAyuda'))}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-tarjeta border border-borde">
          <table className="w-full min-w-[44rem] text-sm">
            <thead className="bg-fondo-sutil">
              <tr>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.numero'))}
                </th>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.nombre'))}
                </th>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.ubicacion'))}
                </th>
                <th
                  scope="col"
                  className="px-5 py-3 text-left font-medium text-texto-suave"
                >
                  {bilingue(t('puntosRondin.estado'))}
                </th>
                <th scope="col" className="px-5 py-3 text-right">
                  <span className="sr-only">{bilingue(t('comun.acciones'))}</span>
                </th>
              </tr>
            </thead>

            <tbody>
              {puntos.map((punto) => (
                <tr key={punto.id} className="border-t border-borde">
                  <td className="px-5 py-3 font-medium text-texto">{punto.numero}</td>
                  <td className="px-5 py-3 text-texto">{punto.nombre}</td>
                  <td className="px-5 py-3 text-texto-suave">
                    {punto.ubicacion ?? '—'}
                  </td>
                  <td className="px-5 py-3">
                    <Badge tono={punto.activo ? 'exito' : 'neutro'}>
                      {bilingue(punto.activo
                        ? t('puntosRondin.activo')
                        : t('puntosRondin.inactivo'))}
                    </Badge>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex justify-end gap-2">
                      <Button
                        variante="secundario"
                        tamano="sm"
                        onClick={() => setVerQr(punto)}
                      >
                        {bilingue(t('puntosRondin.verCodigo'))}
                      </Button>

                      {puedeEditar && (
                        <>
                          <Button
                            variante="secundario"
                            tamano="sm"
                            onClick={() => {
                              setEditando(punto);
                              setModalAbierto(true);
                            }}
                          >
                            {bilingue(t('comun.editar'))}
                          </Button>
                          <Button
                            variante="peligro"
                            tamano="sm"
                            onClick={() => setPorEliminar(punto)}
                          >
                            {bilingue(t('comun.eliminar'))}
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ModalPunto
        abierto={modalAbierto}
        punto={editando}
        guardando={guardando}
        onGuardar={(datos) => void guardar(datos)}
        onCerrar={() => setModalAbierto(false)}
      />

      <ModalQrPunto punto={verQr} onCerrar={() => setVerQr(null)} />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('puntosRondin.confirmarEliminar')}
        mensaje={
          porEliminar === null
            ? ''
            : t('puntosRondin.confirmarEliminarDetalle', {
                nombre: `${porEliminar.numero} — ${porEliminar.nombre}`,
              })
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
