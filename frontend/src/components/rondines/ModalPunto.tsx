'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { useTraduccion } from '@/lib/i18n';
import type { PuntoRondin } from '@/lib/types';

interface ModalPuntoProps {
  abierto: boolean;
  /** `null` para dar de alta; el punto a modificar en caso contrario. */
  punto: PuntoRondin | null;
  guardando: boolean;
  onGuardar: (datos: DatosPunto) => void;
  onCerrar: () => void;
}

export interface DatosPunto {
  numero: string;
  nombre: string;
  ubicacion: string;
  activo: boolean;
}

const VACIO: DatosPunto = { numero: '', nombre: '', ubicacion: '', activo: true };

export function ModalPunto({
  abierto,
  punto,
  guardando,
  onGuardar,
  onCerrar,
}: ModalPuntoProps) {
  const t = useTraduccion();
  const [datos, setDatos] = useState<DatosPunto>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof DatosPunto, string>>>({});

  const editando = punto !== null;

  // Se recarga al abrir, no al montar: el modal vive en el árbol todo el
  // tiempo y sin esto conservaría lo tecleado del punto anterior.
  useEffect(() => {
    if (!abierto) {
      return;
    }

    setErrores({});
    setDatos(
      punto === null
        ? VACIO
        : {
            numero: String(punto.numero),
            nombre: punto.nombre,
            ubicacion: punto.ubicacion ?? '',
            activo: punto.activo,
          },
    );
  }, [abierto, punto]);

  function validar(): boolean {
    // Los mensajes se resuelven al validar, no al declarar el esquema, para
    // que sigan el idioma que esté puesto en ese momento.
    const esquema = z.object({
      numero: z
        .string()
        .trim()
        .refine((valor) => /^\d+$/.test(valor) && Number(valor) >= 1, {
          message: t('puntosRondin.faltaNumero'),
        }),
      nombre: z.string().trim().min(1, t('puntosRondin.faltaNombre')),
    });

    const resultado = esquema.safeParse(datos);
    if (resultado.success) {
      setErrores({});
      return true;
    }

    const encontrados: Partial<Record<keyof DatosPunto, string>> = {};
    for (const problema of resultado.error.issues) {
      const campo = problema.path[0];
      if (typeof campo === 'string') {
        encontrados[campo as keyof DatosPunto] = problema.message;
      }
    }
    setErrores(encontrados);
    return false;
  }

  function enviar() {
    if (validar()) {
      onGuardar(datos);
    }
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="sm"
      titulo={editando ? t('puntosRondin.editar') : t('puntosRondin.crear')}
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
        <Input
          name="numero"
          etiqueta={t('puntosRondin.numero')}
          inputMode="numeric"
          value={datos.numero}
          error={errores.numero}
          ayuda={t('puntosRondin.numeroAyuda')}
          onChange={(evento) => setDatos({ ...datos, numero: evento.target.value })}
        />

        <Input
          name="nombre"
          etiqueta={t('puntosRondin.nombre')}
          value={datos.nombre}
          error={errores.nombre}
          autoComplete="off"
          onChange={(evento) => setDatos({ ...datos, nombre: evento.target.value })}
        />

        <Input
          name="ubicacion"
          etiqueta={t('puntosRondin.ubicacion')}
          value={datos.ubicacion}
          autoComplete="off"
          onChange={(evento) => setDatos({ ...datos, ubicacion: evento.target.value })}
        />

        {editando && (
          <label className="flex items-center gap-2 text-sm text-texto">
            <input
              type="checkbox"
              className="h-4 w-4 accent-primario"
              checked={datos.activo}
              onChange={(evento) =>
                setDatos({ ...datos, activo: evento.target.checked })
              }
            />
            {t('puntosRondin.activo')}
          </label>
        )}

        {/* Permite enviar con Enter sin duplicar el botón visible del pie. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
