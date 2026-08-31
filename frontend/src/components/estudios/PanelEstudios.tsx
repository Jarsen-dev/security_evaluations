'use client';

import { useCallback, useEffect, useState } from 'react';

import { FormularioEstudio } from '@/components/estudios/FormularioEstudio';
import { TablaEstudios } from '@/components/estudios/TablaEstudios';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  actualizarEstudio,
  crearEstudio,
  descargarExcelEstudios,
  eliminarEstudio,
  listarEstudios,
  obtenerCatalogoEstudios,
} from '@/lib/api';
import { avisarCambioDeAvisos } from '@/lib/avisos';
import { bilingue, useTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { CatalogoEstudios, Estudio, EstudioPayload } from '@/lib/types';

/**
 * Pestaña de estudios y capacitaciones.
 *
 * El formulario de arriba da de alta y también edita: al elegir un renglón de
 * la tabla se llena con lo capturado y el botón cambia a "Guardar cambios".
 */
export function PanelEstudios() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { puede } = useSesion();

  const [catalogo, setCatalogo] = useState<CatalogoEstudios | null>(null);
  const [estudios, setEstudios] = useState<Estudio[]>([]);
  const [editando, setEditando] = useState<Estudio | null>(null);
  const [porEliminar, setPorEliminar] = useState<Estudio | null>(null);
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [eliminando, setEliminando] = useState(false);
  const [descargando, setDescargando] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');

  const puedeEditar = puede('estudios', 'editar');

  const cargar = useCallback(async () => {
    try {
      setEstudios(await listarEstudios());
      setErrorCarga('');
    } catch (error) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('estudios.falloCarga'),
      );
    } finally {
      setCargando(false);
    }
  }, [t]);

  useEffect(() => {
    let cancelado = false;

    obtenerCatalogoEstudios()
      .then((datos) => {
        if (!cancelado) {
          setCatalogo(datos);
        }
      })
      .catch((error: unknown) => {
        if (!cancelado) {
          setErrorCarga(
            error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
          );
        }
      });

    return () => {
      cancelado = true;
    };
  }, [t]);

  useEffect(() => {
    void cargar();
  }, [cargar]);

  async function guardar(datos: EstudioPayload) {
    setGuardando(true);

    try {
      if (editando === null) {
        await crearEstudio(datos);
        mostrarToast(t('estudios.guardado'), 'exito');
      } else {
        await actualizarEstudio(editando.id, datos);
        mostrarToast(t('estudios.actualizado'), 'exito');
        setEditando(null);
      }

      await cargar();
      // La fecha de vencimiento pudo cambiar: la campana se recarga.
      avisarCambioDeAvisos();
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
      // Se relanza para que el formulario no borre lo capturado.
      throw error;
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarEstudio(porEliminar.id);
      if (editando?.id === porEliminar.id) {
        setEditando(null);
      }
      await cargar();
      avisarCambioDeAvisos();
      mostrarToast(t('estudios.eliminado'), 'exito');
      setPorEliminar(null);
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setEliminando(false);
    }
  }

  async function descargar() {
    setDescargando(true);

    try {
      await descargarExcelEstudios();
    } catch (error) {
      mostrarToast(
        error instanceof ErrorDeApi ? error.message : t('comun.errorGenerico'),
        'error',
      );
    } finally {
      setDescargando(false);
    }
  }

  function editar(estudio: Estudio) {
    setEditando(estudio);
    // El formulario está arriba de la tabla: sin esto, al elegir un renglón de
    // abajo no se ve que haya pasado nada.
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold text-texto">{bilingue(t('estudios.titulo'))}</h1>
        <p className="mt-1 text-sm text-texto-suave">{bilingue(t('estudios.descripcion'))}</p>
      </div>

      {errorCarga && (
        <p
          role="alert"
          className="rounded-md border border-error bg-error-suave px-3 py-2 text-sm text-error"
        >
          {errorCarga}
        </p>
      )}

      {catalogo !== null && (
        <FormularioEstudio
          catalogo={catalogo}
          estudio={editando}
          onGuardar={guardar}
          onCancelar={() => setEditando(null)}
          guardando={guardando}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-texto">{bilingue(t('estudios.registros'))}</h2>

        <Button
          variante="secundario"
          onClick={() => void descargar()}
          cargando={descargando}
          disabled={estudios.length === 0}
        >
          {bilingue(t('comun.descargarExcel'))}
        </Button>
      </div>

      {cargando || catalogo === null ? (
        <p className="text-sm text-texto-suave">{bilingue(t('comun.cargando'))}</p>
      ) : (
        <TablaEstudios
          catalogo={catalogo}
          estudios={estudios}
          onEditar={editar}
          onEliminar={setPorEliminar}
          puedeEditar={puedeEditar}
        />
      )}

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('estudios.confirmarEliminar')}
        mensaje={t('estudios.confirmarEliminarDetalle')}
        procesando={eliminando}
        onConfirmar={() => void eliminar()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
