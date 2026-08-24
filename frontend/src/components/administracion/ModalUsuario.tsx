'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';

import { SelectorPermisos } from '@/components/administracion/SelectorPermisos';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { useTraduccion } from '@/lib/i18n';
import type { Permisos, Usuario } from '@/lib/types';

/**
 * Alta y edición de un usuario en el mismo modal.
 *
 * La diferencia entre ambos modos es la contraseña: al crear es obligatoria,
 * al editar se deja vacía para conservar la actual. Es lo que se espera al
 * abrir el modal solo para corregir un correo o ajustar permisos.
 */
interface ModalUsuarioProps {
  abierto: boolean;
  /** `null` para dar de alta; el usuario a modificar en caso contrario. */
  usuario: Usuario | null;
  guardando: boolean;
  onGuardar: (datos: DatosUsuario) => void;
  onCerrar: () => void;
}

export interface DatosUsuario {
  nombre: string;
  username: string;
  email: string;
  /** Vacío al editar significa "no cambiar la contraseña". */
  password: string;
  permisos: Permisos;
}

const VACIO: DatosUsuario = {
  nombre: '',
  username: '',
  email: '',
  password: '',
  permisos: {},
};

const LONGITUD_MINIMA_CONTRASENA = 8;

export function ModalUsuario({
  abierto,
  usuario,
  guardando,
  onGuardar,
  onCerrar,
}: ModalUsuarioProps) {
  const t = useTraduccion();
  const [datos, setDatos] = useState<DatosUsuario>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof DatosUsuario, string>>>(
    {},
  );

  const editando = usuario !== null;

  // Se recarga al abrir, no al montar: el modal vive en el árbol todo el
  // tiempo y sin esto conservaría lo tecleado del usuario anterior.
  useEffect(() => {
    if (!abierto) {
      return;
    }

    setErrores({});
    setDatos(
      usuario === null
        ? VACIO
        : {
            nombre: usuario.nombre,
            username: usuario.username,
            email: usuario.email ?? '',
            password: '',
            permisos: usuario.permisos,
          },
    );
  }, [abierto, usuario]);

  function validar(): boolean {
    // Los mensajes se resuelven al validar, no al declarar el esquema, para
    // que sigan el idioma que esté puesto en ese momento.
    const esquema = z.object({
      nombre: z.string().trim().min(1, t('usuarios.faltaNombre')),
      username: z
        .string()
        .trim()
        .min(1, t('usuarios.faltaUsuario'))
        .refine((valor) => !valor.includes(' '), t('usuarios.usuarioConEspacios')),
      email: z.string().trim().email(t('usuarios.faltaEmail')),
      password: editando
        ? z
            .string()
            .refine(
              (valor) => valor === '' || valor.length >= LONGITUD_MINIMA_CONTRASENA,
              t('usuarios.faltaContrasena'),
            )
        : z.string().min(LONGITUD_MINIMA_CONTRASENA, t('usuarios.faltaContrasena')),
    });

    const resultado = esquema.safeParse(datos);
    if (resultado.success) {
      setErrores({});
      return true;
    }

    const encontrados: Partial<Record<keyof DatosUsuario, string>> = {};
    for (const problema of resultado.error.issues) {
      const campo = problema.path[0];
      if (typeof campo === 'string') {
        encontrados[campo as keyof DatosUsuario] = problema.message;
      }
    }
    setErrores(encontrados);
    return false;
  }

  function enviar() {
    if (!validar()) {
      return;
    }

    onGuardar({
      ...datos,
      nombre: datos.nombre.trim(),
      username: datos.username.trim(),
      email: datos.email.trim(),
    });
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="md"
      titulo={editando ? t('usuarios.editar') : t('usuarios.crear')}
      pie={
        <>
          <Button variante="secundario" onClick={onCerrar}>
            {t('comun.cancelar')}
          </Button>
          <Button onClick={enviar} cargando={guardando}>
            {guardando ? t('comun.guardando') : t('comun.guardar')}
          </Button>
        </>
      }
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(evento) => {
          evento.preventDefault();
          enviar();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            name="nombre"
            etiqueta={t('usuarios.nombre')}
            value={datos.nombre}
            error={errores.nombre}
            autoComplete="off"
            onChange={(evento) => setDatos({ ...datos, nombre: evento.target.value })}
          />

          <Input
            name="username"
            etiqueta={t('usuarios.usuario')}
            value={datos.username}
            error={errores.username}
            autoComplete="off"
            onChange={(evento) => setDatos({ ...datos, username: evento.target.value })}
          />

          <Input
            name="email"
            type="email"
            etiqueta={t('usuarios.email')}
            value={datos.email}
            error={errores.email}
            autoComplete="off"
            onChange={(evento) => setDatos({ ...datos, email: evento.target.value })}
          />

          <Input
            name="password"
            type="password"
            etiqueta={editando ? t('usuarios.contrasenaNueva') : t('usuarios.contrasena')}
            value={datos.password}
            error={errores.password}
            ayuda={
              editando ? t('usuarios.contrasenaOpcional') : t('usuarios.contrasenaAyuda')
            }
            autoComplete="new-password"
            onChange={(evento) => setDatos({ ...datos, password: evento.target.value })}
          />
        </div>

        {usuario?.es_superadmin === true ? (
          <p className="rounded-tarjeta border border-borde bg-fondo-sutil px-4 py-3 text-sm text-texto-suave">
            {t('permisos.superadminTodo')}
          </p>
        ) : (
          <SelectorPermisos
            valor={datos.permisos}
            onCambiar={(permisos) => setDatos({ ...datos, permisos })}
          />
        )}

        {/* Permite enviar con Enter sin duplicar el botón visible del pie. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
