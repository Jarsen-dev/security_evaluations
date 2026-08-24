'use client';

import { useCallback, useEffect, useState } from 'react';

import { ModalUsuario, type DatosUsuario } from '@/components/administracion/ModalUsuario';
import { TablaUsuarios } from '@/components/administracion/TablaUsuarios';
import { Button } from '@/components/ui/Button';
import { DialogoConfirmacion } from '@/components/ui/DialogoConfirmacion';
import { useToast } from '@/components/ui/Toast';
import {
  ErrorDeApi,
  actualizarUsuario,
  cambiarEstadoUsuario,
  crearUsuario,
  eliminarUsuario,
  listarUsuarios,
} from '@/lib/api';
import { useTraduccion, type ClaveTraduccion } from '@/lib/i18n';
import { useSesion } from '@/lib/sesion';
import type { Usuario } from '@/lib/types';

/** Gestión de los usuarios del panel: alta, edición, desactivación y borrado. */
export function PanelUsuarios() {
  const t = useTraduccion();
  const { mostrarToast } = useToast();
  const { usuario: enSesion, recargar: recargarSesion } = useSesion();

  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState('');

  const [modalAbierto, setModalAbierto] = useState(false);
  const [editando, setEditando] = useState<Usuario | null>(null);
  const [guardando, setGuardando] = useState(false);

  const [procesandoId, setProcesandoId] = useState<string | null>(null);
  const [porEliminar, setPorEliminar] = useState<Usuario | null>(null);
  const [eliminando, setEliminando] = useState(false);

  const cargar = useCallback(async () => {
    try {
      setUsuarios(await listarUsuarios());
      setErrorCarga('');
    } catch (error: unknown) {
      setErrorCarga(
        error instanceof ErrorDeApi ? error.message : t('usuarios.falloCarga'),
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

  async function guardar(datos: DatosUsuario) {
    setGuardando(true);

    try {
      if (editando === null) {
        await crearUsuario({ ...datos, permisos: datos.permisos });
        mostrarToast(t('usuarios.creado'), 'exito');
      } else {
        await actualizarUsuario(editando.id, {
          nombre: datos.nombre,
          username: datos.username,
          email: datos.email,
          // Vacío significa "conserva la actual": no se manda el campo.
          ...(datos.password === '' ? {} : { password: datos.password }),
          permisos: datos.permisos,
        });
        mostrarToast(t('usuarios.actualizado'), 'exito');

        // Si el superadministrador se editó a sí mismo, el encabezado tiene
        // que reflejarlo sin obligarlo a recargar la página.
        if (editando.id === enSesion?.id) {
          await recargarSesion();
        }
      }

      setModalAbierto(false);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'usuarios.falloGuardar');
    } finally {
      setGuardando(false);
    }
  }

  async function alternarActivo(usuario: Usuario) {
    setProcesandoId(usuario.id);

    try {
      await cambiarEstadoUsuario(usuario.id, !usuario.activo);
      mostrarToast(
        usuario.activo ? t('usuarios.desactivado') : t('usuarios.activado'),
        'exito',
      );
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'usuarios.falloEstado');
    } finally {
      setProcesandoId(null);
    }
  }

  async function confirmarEliminacion() {
    if (porEliminar === null) {
      return;
    }

    setEliminando(true);

    try {
      await eliminarUsuario(porEliminar.id);
      mostrarToast(t('usuarios.eliminado'), 'exito');
      setPorEliminar(null);
      await cargar();
    } catch (error: unknown) {
      mostrarFallo(error, 'usuarios.falloEliminar');
    } finally {
      setEliminando(false);
    }
  }

  function abrirAlta() {
    setEditando(null);
    setModalAbierto(true);
  }

  function abrirEdicion(usuario: Usuario) {
    setEditando(usuario);
    setModalAbierto(true);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-texto">{t('usuarios.titulo')}</h2>
          <p className="mt-1 text-sm text-texto-suave">{t('usuarios.descripcion')}</p>
        </div>

        <Button onClick={abrirAlta}>{t('usuarios.nuevo')}</Button>
      </div>

      {cargando ? (
        <p className="text-sm text-texto-suave">{t('comun.cargando')}</p>
      ) : errorCarga !== '' ? (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-tarjeta border border-error bg-error-suave px-4 py-3 text-sm text-texto"
        >
          <span>{errorCarga}</span>
          <Button variante="secundario" tamano="sm" onClick={() => void cargar()}>
            {t('comun.reintentar')}
          </Button>
        </div>
      ) : usuarios.length === 0 ? (
        <div className="rounded-tarjeta border border-dashed border-borde px-6 py-12 text-center">
          <p className="text-sm font-medium text-texto">{t('usuarios.vacio')}</p>
          <p className="mt-2 text-sm text-texto-suave">{t('usuarios.vacioAyuda')}</p>
        </div>
      ) : (
        <TablaUsuarios
          usuarios={usuarios}
          idPropio={enSesion?.id}
          procesandoId={procesandoId}
          onEditar={abrirEdicion}
          onAlternarActivo={(usuario) => void alternarActivo(usuario)}
          onEliminar={setPorEliminar}
        />
      )}

      <ModalUsuario
        abierto={modalAbierto}
        usuario={editando}
        guardando={guardando}
        onGuardar={(datos) => void guardar(datos)}
        onCerrar={() => setModalAbierto(false)}
      />

      <DialogoConfirmacion
        abierto={porEliminar !== null}
        titulo={t('usuarios.confirmarEliminar')}
        mensaje={
          porEliminar === null
            ? ''
            : t('usuarios.confirmarEliminarDetalle', { nombre: porEliminar.nombre })
        }
        procesando={eliminando}
        onConfirmar={() => void confirmarEliminacion()}
        onCancelar={() => setPorEliminar(null)}
      />
    </div>
  );
}
