'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';

import { CLASES_SEMAFORO, CLAVES_SEMAFORO, clasificar } from '@/components/catalogo/semaforo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { useTraduccion } from '@/lib/i18n';
import { cn } from '@/lib/utils';
import type { Insumo } from '@/lib/types';

/**
 * Alta y edición de un insumo en el mismo modal.
 *
 * Los números viajan como texto mientras se teclea: un `<input type="number">`
 * controlado por un `number` no deja borrar el contenido para escribir otro
 * valor, y aquí se corrigen existencias a mano todo el tiempo.
 */
interface ModalInsumoProps {
  abierto: boolean;
  /** `null` para dar de alta; el insumo a modificar en caso contrario. */
  insumo: Insumo | null;
  categorias: string[];
  guardando: boolean;
  onGuardar: (datos: DatosInsumo) => void;
  onCerrar: () => void;
}

export interface DatosInsumo {
  nombre: string;
  descripcion: string;
  categoria: string;
  proveedor: string;
  ubicacion: string;
  cantidad: string;
  minimo: string;
  maximo: string;
}

const VACIO: DatosInsumo = {
  nombre: '',
  descripcion: '',
  categoria: '',
  proveedor: '',
  ubicacion: '',
  cantidad: '0',
  minimo: '0',
  maximo: '0',
};

const CLASES_CAMPO =
  'h-10 w-full rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

export function ModalInsumo({
  abierto,
  insumo,
  categorias,
  guardando,
  onGuardar,
  onCerrar,
}: ModalInsumoProps) {
  const t = useTraduccion();
  const [datos, setDatos] = useState<DatosInsumo>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof DatosInsumo, string>>>({});

  const editando = insumo !== null;
  const vistaPrevia = clasificar(datos.cantidad, datos.minimo, datos.maximo);

  // Se recarga al abrir, no al montar: el modal vive en el árbol todo el
  // tiempo y sin esto conservaría lo tecleado del insumo anterior.
  useEffect(() => {
    if (!abierto) {
      return;
    }

    setErrores({});
    setDatos(
      insumo === null
        ? VACIO
        : {
            nombre: insumo.nombre,
            descripcion: insumo.descripcion ?? '',
            categoria: insumo.categoria,
            proveedor: insumo.proveedor ?? '',
            ubicacion: insumo.ubicacion ?? '',
            cantidad: String(insumo.cantidad),
            minimo: String(insumo.minimo),
            maximo: String(insumo.maximo),
          },
    );
  }, [abierto, insumo]);

  function validar(): boolean {
    // Los mensajes se resuelven al validar, no al declarar el esquema, para
    // que sigan el idioma que esté puesto en ese momento.
    const entero = z
      .string()
      .trim()
      .refine(
        (valor) => /^\d+$/.test(valor),
        t('catalogo.numeroInvalido'),
      );

    const esquema = z
      .object({
        nombre: z.string().trim().min(1, t('catalogo.faltaNombre')),
        categoria: z.string().trim().min(1, t('catalogo.faltaCategoria')),
        cantidad: entero,
        minimo: entero,
        maximo: entero,
      })
      .refine(
        // El backend aplica la misma regla, pero atraparla aquí deja el
        // mensaje junto al campo en vez de en un toast genérico.
        ({ minimo, maximo }) =>
          !/^\d+$/.test(minimo) || !/^\d+$/.test(maximo) || Number(maximo) >= Number(minimo),
        { message: t('catalogo.rangoInvertido'), path: ['maximo'] },
      );

    const resultado = esquema.safeParse(datos);
    if (resultado.success) {
      setErrores({});
      return true;
    }

    const encontrados: Partial<Record<keyof DatosInsumo, string>> = {};
    for (const problema of resultado.error.issues) {
      const campo = problema.path[0];
      if (typeof campo === 'string') {
        encontrados[campo as keyof DatosInsumo] = problema.message;
      }
    }
    setErrores(encontrados);
    return false;
  }

  function enviar() {
    if (!validar()) {
      return;
    }
    onGuardar(datos);
  }

  return (
    <Modal
      abierto={abierto}
      onCerrar={onCerrar}
      ancho="md"
      titulo={editando ? t('catalogo.editar') : t('catalogo.crear')}
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
          <div className="sm:col-span-2">
            <Input
              name="nombre"
              etiqueta={t('catalogo.nombre')}
              value={datos.nombre}
              error={errores.nombre}
              ayuda={t('catalogo.nombreAyuda')}
              autoComplete="off"
              onChange={(evento) => setDatos({ ...datos, nombre: evento.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="categoria" className="text-sm font-medium text-texto">
              {t('catalogo.categoria')}
            </label>
            <select
              id="categoria"
              className={CLASES_CAMPO}
              value={datos.categoria}
              aria-invalid={errores.categoria ? true : undefined}
              onChange={(evento) =>
                setDatos({ ...datos, categoria: evento.target.value })
              }
            >
              <option value="">—</option>
              {categorias.map((categoria) => (
                <option key={categoria} value={categoria}>
                  {categoria}
                </option>
              ))}
            </select>
            {errores.categoria && (
              <p role="alert" className="text-sm text-error">
                {errores.categoria}
              </p>
            )}
          </div>

          <Input
            name="proveedor"
            etiqueta={t('catalogo.proveedor')}
            value={datos.proveedor}
            autoComplete="off"
            onChange={(evento) => setDatos({ ...datos, proveedor: evento.target.value })}
          />

          <div className="sm:col-span-2">
            <Textarea
              name="descripcion"
              etiqueta={t('catalogo.descripcionCampo')}
              rows={2}
              value={datos.descripcion}
              onChange={(evento) =>
                setDatos({ ...datos, descripcion: evento.target.value })
              }
            />
          </div>

          <div className="sm:col-span-2">
            <Input
              name="ubicacion"
              etiqueta={t('catalogo.ubicacion')}
              value={datos.ubicacion}
              autoComplete="off"
              onChange={(evento) =>
                setDatos({ ...datos, ubicacion: evento.target.value })
              }
            />
          </div>

          <Input
            name="cantidad"
            etiqueta={t('catalogo.cantidad')}
            inputMode="numeric"
            value={datos.cantidad}
            error={errores.cantidad}
            onChange={(evento) => setDatos({ ...datos, cantidad: evento.target.value })}
          />

          <div className="grid grid-cols-2 gap-3">
            <Input
              name="minimo"
              etiqueta={t('catalogo.minimo')}
              inputMode="numeric"
              value={datos.minimo}
              error={errores.minimo}
              onChange={(evento) => setDatos({ ...datos, minimo: evento.target.value })}
            />
            <Input
              name="maximo"
              etiqueta={t('catalogo.maximo')}
              inputMode="numeric"
              value={datos.maximo}
              error={errores.maximo}
              onChange={(evento) => setDatos({ ...datos, maximo: evento.target.value })}
            />
          </div>
        </div>

        {/* Adelanto del semáforo mientras se teclea; lo definitivo lo decide
            el servidor al guardar. */}
        {vistaPrevia !== null && (
          <p
            className={cn(
              'rounded-tarjeta border px-4 py-2 text-sm',
              CLASES_SEMAFORO[vistaPrevia],
            )}
          >
            {t(CLAVES_SEMAFORO[vistaPrevia])}
          </p>
        )}

        {/* Permite enviar con Enter sin duplicar el botón visible del pie. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
