'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';

import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type { Extintor, ExtintorPayload } from '@/lib/types';

const CLASES_SELECT =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

interface DatosExtintor {
  folio: string;
  modelo: string;
  capacidad: string;
  tipo: string;
  ubicacion: string;
  vencimiento: string;
}

const VACIO: DatosExtintor = {
  folio: '',
  modelo: '',
  capacidad: '',
  tipo: '',
  ubicacion: '',
  vencimiento: '',
};

/** Alta y edición de una ficha, en el mismo modal. */
export function ModalExtintor({
  abierto,
  extintor,
  tipos,
  guardando,
  onGuardar,
  onCerrar,
}: {
  abierto: boolean;
  /** `null` para dar de alta; la ficha a modificar en caso contrario. */
  extintor: Extintor | null;
  tipos: string[];
  guardando: boolean;
  onGuardar: (datos: ExtintorPayload) => Promise<void>;
  onCerrar: () => void;
}) {
  const t = useTraduccion();

  const [datos, setDatos] = useState<DatosExtintor>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof DatosExtintor, string>>>(
    {},
  );

  const editando = extintor !== null;

  // Se recarga al abrir, no al montar: el modal vive en el árbol todo el
  // tiempo y sin esto conservaría lo tecleado de la ficha anterior.
  useEffect(() => {
    if (!abierto) {
      return;
    }
    setErrores({});
    setDatos(
      extintor === null
        ? VACIO
        : {
            folio: extintor.folio,
            modelo: extintor.modelo,
            capacidad: extintor.capacidad,
            tipo: extintor.tipo,
            ubicacion: extintor.ubicacion,
            vencimiento: extintor.vencimiento,
          },
    );
  }, [abierto, extintor]);

  function validar(): boolean {
    // Los mensajes se resuelven al validar y no al declarar el esquema, para
    // que sigan el idioma que esté puesto en ese momento.
    const esquema = z.object({
      folio: z.string().trim().min(1, t('extintores.faltaFolio')),
      modelo: z.string().trim().min(1, t('extintores.faltaModelo')),
      capacidad: z.string().trim().min(1, t('extintores.faltaCapacidad')),
      tipo: z.string().trim().min(1, t('extintores.faltaTipo')),
      ubicacion: z.string().trim().min(1, t('extintores.faltaUbicacion')),
      vencimiento: z
        .string()
        .refine((valor) => /^\d{4}-\d{2}-\d{2}$/.test(valor), t('extintores.faltaVencimiento')),
    });

    const resultado = esquema.safeParse(datos);
    if (resultado.success) {
      setErrores({});
      return true;
    }

    const encontrados: Partial<Record<keyof DatosExtintor, string>> = {};
    for (const problema of resultado.error.issues) {
      const campo = problema.path[0];
      if (typeof campo === 'string') {
        encontrados[campo as keyof DatosExtintor] = problema.message;
      }
    }
    setErrores(encontrados);
    return false;
  }

  async function enviar() {
    if (!validar()) {
      return;
    }
    await onGuardar({
      folio: datos.folio.trim(),
      modelo: datos.modelo.trim(),
      capacidad: datos.capacidad.trim(),
      tipo: datos.tipo,
      ubicacion: datos.ubicacion.trim(),
      vencimiento: datos.vencimiento,
    });
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      titulo={editando ? t('extintores.editar') : t('extintores.registrar')}
      ancho="md"
      pie={
        <>
          <Button variante="fantasma" onClick={onCerrar} disabled={guardando}>
            {bilingue(t('comun.cancelar'))}
          </Button>
          <Button onClick={() => void enviar()} cargando={guardando}>
            {bilingue(t('comun.guardar'))}
          </Button>
        </>
      }
    >
      <form
        className="grid gap-4 sm:grid-cols-2"
        onSubmit={(evento) => {
          evento.preventDefault();
          void enviar();
        }}
      >
        <Input
          name="folio"
          etiqueta={t('extintores.folio')}
          ayuda={t('extintores.folioAyuda')}
          value={datos.folio}
          maxLength={20}
          onChange={(e) => setDatos({ ...datos, folio: e.target.value })}
          error={errores.folio}
        />
        <Input
          name="modelo"
          etiqueta={t('extintores.modelo')}
          value={datos.modelo}
          maxLength={100}
          onChange={(e) => setDatos({ ...datos, modelo: e.target.value })}
          error={errores.modelo}
        />
        <Input
          name="capacidad"
          etiqueta={t('extintores.capacidad')}
          ayuda={t('extintores.capacidadAyuda')}
          value={datos.capacidad}
          maxLength={50}
          onChange={(e) => setDatos({ ...datos, capacidad: e.target.value })}
          error={errores.capacidad}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="tipo-extintor" className="text-sm font-medium text-texto">
            {bilingue(t('extintores.tipo'))}
          </label>
          <select
            id="tipo-extintor"
            value={datos.tipo}
            onChange={(e) => setDatos({ ...datos, tipo: e.target.value })}
            aria-invalid={errores.tipo ? true : undefined}
            className={CLASES_SELECT}
          >
            <option value="">{t('extintores.tipoPlaceholder')}</option>
            {/* Del catálogo del backend: no se escriben a mano. */}
            {tipos.map((tipo) => (
              <option key={tipo} value={tipo}>
                {tipo}
              </option>
            ))}
          </select>
          {errores.tipo && (
            <p role="alert" className="text-sm text-error">
              {bilingue(errores.tipo)}
            </p>
          )}
        </div>

        <Input
          name="ubicacion"
          etiqueta={t('extintores.ubicacion')}
          value={datos.ubicacion}
          maxLength={150}
          onChange={(e) => setDatos({ ...datos, ubicacion: e.target.value })}
          error={errores.ubicacion}
        />
        <Input
          name="vencimiento"
          type="date"
          etiqueta={t('extintores.vencimiento')}
          ayuda={t('extintores.vencimientoAyuda')}
          value={datos.vencimiento}
          onChange={(e) => setDatos({ ...datos, vencimiento: e.target.value })}
          error={errores.vencimiento}
        />

        {/* Permite enviar con Enter sin duplicar el botón visible del pie. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
