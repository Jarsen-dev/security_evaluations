'use client';

import { useCallback, useEffect, useState } from 'react';

import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { ModalCuestionario } from '@/components/cuestionarios/ModalCuestionario';
import { ModalQR } from '@/components/cuestionarios/ModalQR';
import { TarjetaCuestionario } from '@/components/cuestionarios/TarjetaCuestionario';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { useTraduccion } from '@/lib/i18n';
import { copiarAlPortapapeles } from '@/lib/navegador';
import {
  ErrorDeApi,
  actualizarCuestionario,
  descargarCuestionarioPdf,
  duplicarCuestionario,
  eliminarCuestionario,
  listarCuestionarios,
} from '@/lib/api';
import type { CuestionarioResumen } from '@/lib/types';

/**
 * Pestaña "Cuestionarios" del panel.
 *
 * Vivía en `app/(panel)/cuestionarios/page.tsx`; ahora la página es solo el
 * contenedor de las dos pestañas internas y esta es una de ellas.
 */
export function PanelCuestionarios() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();

  const [cuestionarios, setCuestionarios] = useState<CuestionarioResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [modalAbierto, setModalAbierto] = useState(false);
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [porEliminar, setPorEliminar] = useState<CuestionarioResumen | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [qrDe, setQrDe] = useState<CuestionarioResumen | null>(null);
  const [imprimiendoId, setImprimiendoId] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    try {
      setCuestionarios(await listarCuestionarios());
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi
          ? error.message
          : t('cuestionarios.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  function abrirCreacion() {
    setEditandoId(null);
    setModalAbierto(true);
  }

  function abrirEdicion(id: string) {
    setEditandoId(id);
    setModalAbierto(true);
  }

  async function duplicar(cuestionario: CuestionarioResumen) {
    try {
      await duplicarCuestionario(cuestionario.id);
      await cargar();
      mostrarToast(t('cuestionarios.duplicado'), 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('cuestionarios.falloDuplicar'),
        'error',
      );
    }
  }

  async function alternarActivo(cuestionario: CuestionarioResumen) {
    try {
      await actualizarCuestionario(cuestionario.id, { activo: !cuestionario.activo });
      await cargar();
      mostrarToast(
        cuestionario.activo
          ? t('cuestionarios.desactivado')
          : t('cuestionarios.activado'),
        'exito',
      );
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi
          ? error.message
          : t('cuestionarios.falloEstado'),
        'error',
      );
    }
  }

  async function copiarLiga(cuestionario: CuestionarioResumen) {
    const base = (process.env.NEXT_PUBLIC_BASE_URL ?? '').replace(/\/$/, '');
    const url = `${base}/r/${cuestionario.token_publico}`;

    if (await copiarAlPortapapeles(url)) {
      mostrarToast(t('qr.ligaCopiada'), 'exito');
    } else {
      mostrarToast(`Copia la liga manualmente: ${url}`, 'error');
    }
  }

  async function imprimir(cuestionario: CuestionarioResumen) {
    setImprimiendoId(cuestionario.id);

    try {
      await descargarCuestionarioPdf(cuestionario.id);
      mostrarToast(t('cuestionarios.pdfDescargado'), 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('cuestionarios.falloPdf'),
        'error',
      );
    } finally {
      setImprimiendoId(null);
    }
  }

  async function confirmarEliminacion() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarCuestionario(porEliminar.id);
      await cargar();
      mostrarToast(t('cuestionarios.eliminado'), 'exito');
      setPorEliminar(null);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('cuestionarios.falloEliminar'),
        'error',
      );
    } finally {
      setEliminando(false);
    }
  }

  const respuestasDelEditado =
    cuestionarios.find((c) => c.id === editandoId)?.total_respuestas ?? 0;

  return (
    <section>
      <div className="mb-6 flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold text-texto">
          {t('encabezado.cuestionarios')}
        </h1>
        <Button onClick={abrirCreacion}>{t('modalCuestionario.nuevo')}</Button>
      </div>

      {cargando && <p className="text-texto-suave">{t('comun.cargando')}</p>}

      {!cargando && errorCarga && (
        <p
          role="alert"
          className="rounded-tarjeta border border-error bg-error-suave p-4 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {!cargando && !errorCarga && cuestionarios.length === 0 && (
        <div className="rounded-tarjeta border border-dashed border-borde p-10 text-center">
          <p className="text-texto-suave">{t('cuestionarios.vacio')}</p>
          <p className="mt-1 text-sm text-texto-tenue">{t('cuestionarios.vacioAyuda')}</p>
        </div>
      )}

      {!cargando && cuestionarios.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {cuestionarios.map((cuestionario) => (
            <TarjetaCuestionario
              key={cuestionario.id}
              cuestionario={cuestionario}
              onEditar={() => abrirEdicion(cuestionario.id)}
              onVerQR={() => setQrDe(cuestionario)}
              onCopiarLiga={() => void copiarLiga(cuestionario)}
              onImprimir={() => void imprimir(cuestionario)}
              imprimiendo={imprimiendoId === cuestionario.id}
              onDuplicar={() => void duplicar(cuestionario)}
              onAlternarActivo={() => void alternarActivo(cuestionario)}
              onEliminar={() => setPorEliminar(cuestionario)}
            />
          ))}
        </div>
      )}

      <ModalCuestionario
        abierto={modalAbierto}
        cuestionarioId={editandoId}
        totalRespuestas={respuestasDelEditado}
        onCerrar={() => setModalAbierto(false)}
        onGuardado={(_, esNuevo) => {
          setModalAbierto(false);
          void cargar();
          mostrarToast(
            esNuevo ? t('cuestionarios.creado') : t('cuestionarios.cambiosGuardados'),
            'exito',
          );
        }}
      />

      <ModalQR
        abierto={qrDe !== null}
        cuestionario={qrDe}
        onCerrar={() => setQrDe(null)}
      />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('cuestionarios.confirmarEliminar')}
        mensaje={
          porEliminar
            ? t('cuestionarios.confirmarEliminarDetalle', {
                nombre: porEliminar.nombre,
                preguntas: porEliminar.total_preguntas,
                respuestas: porEliminar.total_respuestas,
              })
            : ''
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </section>
  );
}
