'use client';

import { useEffect, useState } from 'react';
import { z } from 'zod';

import { CLASES_SEMAFORO, CLAVES_SEMAFORO, clasificar } from '@/components/catalogo/semaforo';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { bilingue, useTraduccion } from '@/lib/i18n';
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
  unidades: string[];
  guardando: boolean;
  onGuardar: (datos: DatosInsumo) => void;
  onCerrar: () => void;
}

export interface DatosInsumo {
  codigo: string;
  descripcion: string;
  categoria: string;
  unidad_medida: string;
  proveedor: string;
  ubicacion: string;
  piezas_por_empaque: string;
  existencia: string;
  minimo: string;
  maximo: string;
}

const VACIO: DatosInsumo = {
  codigo: '',
  descripcion: '',
  categoria: '',
  unidad_medida: '',
  proveedor: '',
  ubicacion: '',
  // Una caja trae al menos una pieza; la existencia de un insumo recién dado
  // de alta sí arranca en cero.
  piezas_por_empaque: '1',
  existencia: '0',
  minimo: '0',
  maximo: '0',
};

const CLASES_CAMPO =
  'h-10 w-full rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

export function ModalInsumo({
  abierto,
  insumo,
  categorias,
  unidades,
  guardando,
  onGuardar,
  onCerrar,
}: ModalInsumoProps) {
  const t = useTraduccion();
  const [datos, setDatos] = useState<DatosInsumo>(VACIO);
  const [errores, setErrores] = useState<Partial<Record<keyof DatosInsumo, string>>>({});

  const editando = insumo !== null;
  const vistaPrevia = clasificar(datos.existencia, datos.minimo, datos.maximo);

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
            codigo: insumo.codigo,
            descripcion: insumo.descripcion ?? '',
            categoria: insumo.categoria,
            unidad_medida: insumo.unidad_medida,
            proveedor: insumo.proveedor ?? '',
            ubicacion: insumo.ubicacion ?? '',
            piezas_por_empaque: String(insumo.piezas_por_empaque),
            existencia: String(insumo.existencia),
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
        codigo: z.string().trim().min(1, t('catalogo.faltaCodigo')),
        // Obligatoria: es lo único que distingue a dos insumos con el mismo
        // código, y el índice único de la base es la pareja de los dos.
        descripcion: z.string().trim().min(1, t('catalogo.faltaDescripcion')),
        categoria: z.string().trim().min(1, t('catalogo.faltaCategoria')),
        unidad_medida: z.string().trim().min(1, t('catalogo.faltaUnidad')),
        // Las piezas por caja son el único número que no admite cero: con
        // cero, una recepción daría entrada a nada.
        piezas_por_empaque: z
          .string()
          .trim()
          .refine(
            (valor) => /^\d+$/.test(valor) && Number(valor) >= 1,
            t('catalogo.piezasInvalidas'),
          ),
        existencia: entero,
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
            {bilingue(t('comun.cancelar'))}
          </Button>
          <Button onClick={enviar} cargando={guardando}>
            {bilingue(guardando ? t('comun.guardando') : t('comun.guardar'))}
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
              name="codigo"
              etiqueta={t('catalogo.codigo')}
              value={datos.codigo}
              error={errores.codigo}
              ayuda={t('catalogo.codigoAyuda')}
              autoComplete="off"
              onChange={(evento) => setDatos({ ...datos, codigo: evento.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="categoria" className="text-sm font-medium text-texto">
              {bilingue(t('catalogo.categoria'))}
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

          <div className="flex flex-col gap-1.5">
            <label htmlFor="unidad_medida" className="text-sm font-medium text-texto">
              {bilingue(t('catalogo.unidadMedida'))}
            </label>
            <select
              id="unidad_medida"
              className={CLASES_CAMPO}
              value={datos.unidad_medida}
              aria-invalid={errores.unidad_medida ? true : undefined}
              onChange={(evento) =>
                setDatos({ ...datos, unidad_medida: evento.target.value })
              }
            >
              <option value="">—</option>
              {unidades.map((unidad) => (
                <option key={unidad} value={unidad}>
                  {unidad}
                </option>
              ))}
            </select>
            {errores.unidad_medida && (
              <p role="alert" className="text-sm text-error">
                {errores.unidad_medida}
              </p>
            )}
          </div>

          <div className="sm:col-span-2">
            <Input
              name="proveedor"
              etiqueta={t('catalogo.proveedor')}
              value={datos.proveedor}
              autoComplete="off"
              onChange={(evento) =>
                setDatos({ ...datos, proveedor: evento.target.value })
              }
            />
          </div>

          <div className="sm:col-span-2">
            <Textarea
              name="descripcion"
              etiqueta={t('catalogo.descripcionCampo')}
              ayuda={t('catalogo.descripcionAyuda')}
              error={errores.descripcion}
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
            name="piezas_por_empaque"
            etiqueta={t('catalogo.piezasPorCaja')}
            ayuda={t('catalogo.piezasPorCajaAyuda')}
            inputMode="numeric"
            value={datos.piezas_por_empaque}
            error={errores.piezas_por_empaque}
            onChange={(evento) =>
              setDatos({ ...datos, piezas_por_empaque: evento.target.value })
            }
          />

          <Input
            name="existencia"
            etiqueta={t('catalogo.existencia')}
            ayuda={t('catalogo.existenciaAyuda')}
            inputMode="numeric"
            value={datos.existencia}
            error={errores.existencia}
            onChange={(evento) => setDatos({ ...datos, existencia: evento.target.value })}
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
            {bilingue(t(CLAVES_SEMAFORO[vistaPrevia]))}
          </p>
        )}

        {/* Permite enviar con Enter sin duplicar el botón visible del pie. */}
        <button type="submit" className="hidden" aria-hidden tabIndex={-1} />
      </form>
    </Modal>
  );
}
