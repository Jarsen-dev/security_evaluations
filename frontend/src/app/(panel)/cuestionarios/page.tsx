'use client';

import { useCallback, useEffect, useState } from 'react';

import { DialogoConfirmacion } from '@/components/cuestionarios/DialogoConfirmacion';
import { ModalCuestionario } from '@/components/cuestionarios/ModalCuestionario';
import { ModalQR } from '@/components/cuestionarios/ModalQR';
import { TarjetaCuestionario } from '@/components/cuestionarios/TarjetaCuestionario';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { copiarAlPortapapeles } from '@/lib/navegador';
import {
  ErrorDeApi,
  actualizarCuestionario,
  duplicarCuestionario,
  eliminarCuestionario,
  listarCuestionarios,
} from '@/lib/api';
import type { CuestionarioResumen } from '@/lib/types';

export default function PaginaCuestionarios() {
  const { mostrarToast } = useToast();

  const [cuestionarios, setCuestionarios] = useState<CuestionarioResumen[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [modalAbierto, setModalAbierto] = useState(false);
  const [editandoId, setEditandoId] = useState<string | null>(null);
  const [porEliminar, setPorEliminar] = useState<CuestionarioResumen | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [qrDe, setQrDe] = useState<CuestionarioResumen | null>(null);

  const cargar = useCallback(async () => {
    try {
      setCuestionarios(await listarCuestionarios());
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudieron cargar los cuestionarios.',
      );
    } finally {
      setCargando(false);
    }
  }, []);

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
      mostrarToast('Cuestionario duplicado. La copia queda inactiva.', 'exito');
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : 'No se pudo duplicar.',
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
          ? 'Cuestionario desactivado. La liga pública deja de aceptar respuestas.'
          : 'Cuestionario activado.',
        'exito',
      );
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi
          ? error.message
          : 'No se pudo cambiar el estado.',
        'error',
      );
    }
  }

  async function copiarLiga(cuestionario: CuestionarioResumen) {
    const base = (process.env.NEXT_PUBLIC_BASE_URL ?? '').replace(/\/$/, '');
    const url = `${base}/r/${cuestionario.token_publico}`;

    if (await copiarAlPortapapeles(url)) {
      mostrarToast('Liga copiada al portapapeles.', 'exito');
    } else {
      mostrarToast(`Copia la liga manualmente: ${url}`, 'error');
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
      mostrarToast('Cuestionario eliminado.', 'exito');
      setPorEliminar(null);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : 'No se pudo eliminar.',
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
        <h1 className="text-xl font-semibold text-texto">Cuestionarios</h1>
        <Button onClick={abrirCreacion}>Nuevo cuestionario</Button>
      </div>

      {cargando && <p className="text-texto-suave">Cargando cuestionarios…</p>}

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
          <p className="text-texto-suave">Todavía no hay cuestionarios.</p>
          <p className="mt-1 text-sm text-texto-tenue">
            Crea el primero con el botón “Nuevo cuestionario”.
          </p>
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
            esNuevo ? 'Cuestionario creado.' : 'Cambios guardados.',
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
        titulo="Eliminar cuestionario"
        mensaje={
          porEliminar
            ? `Se eliminará “${porEliminar.nombre}” junto con sus ${porEliminar.total_preguntas} pregunta(s) y ${porEliminar.total_respuestas} respuesta(s). Esta acción no se puede deshacer.`
            : ''
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </section>
  );
}
