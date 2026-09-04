'use client';

import { useState } from 'react';

import { BuscadorInsumo } from '@/components/controles/insumos/BuscadorInsumo';
import { ModalTermino } from '@/components/controles/insumos/ModalTermino';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { bilingue, useTraduccion } from '@/lib/i18n';
import type {
  Area,
  ControlInsumoPayload,
  InsumoParaControl,
} from '@/lib/types';

const CLASES_SELECT =
  'h-10 rounded-md border border-borde bg-fondo px-3 text-sm text-texto focus:border-primario';

interface Errores {
  insumo?: string;
  entregadoA?: string;
  area?: string;
  consumo?: string;
}

/**
 * Los cuatro campos de la captura.
 *
 * La pregunta de «¿se terminó?» aparece al enviar y no antes: el operador
 * todavía no ha tecleado el consumo cuando elige el insumo, y la pregunta
 * habla justo de esa cantidad. Se resuelve como estado —el modal contesta y
 * llama a guardar con la respuesta— y no como una promesa suspendida a media
 * función, que es donde viven los envíos dobles.
 */
export function FormularioInsumos({
  areas,
  unidadesParciales,
  guardando,
  onGuardar,
}: {
  areas: Area[];
  unidadesParciales: string[];
  guardando: boolean;
  onGuardar: (datos: ControlInsumoPayload) => Promise<void>;
}) {
  const t = useTraduccion();

  const [insumo, setInsumo] = useState<InsumoParaControl | null>(null);
  const [entregadoA, setEntregadoA] = useState('');
  const [area, setArea] = useState('');
  const [consumo, setConsumo] = useState('');
  const [errores, setErrores] = useState<Errores>({});
  const [preguntando, setPreguntando] = useState(false);

  const cantidad = Number.parseInt(consumo, 10);
  const preguntaTermino =
    insumo !== null && unidadesParciales.includes(insumo.unidad_medida.toUpperCase());

  function validar(): Errores {
    const encontrados: Errores = {};
    if (insumo === null) {
      encontrados.insumo = t('controlInsumos.faltaInsumo');
    }
    if (entregadoA.trim() === '') {
      encontrados.entregadoA = t('controlInsumos.faltaEntregadoA');
    }
    if (area === '') {
      encontrados.area = t('controlInsumos.faltaArea');
    }
    if (!Number.isInteger(cantidad) || cantidad < 1) {
      encontrados.consumo = t('controlInsumos.faltaConsumo');
    }
    return encontrados;
  }

  function enviar() {
    const encontrados = validar();
    setErrores(encontrados);
    if (Object.keys(encontrados).length > 0) {
      return;
    }

    if (preguntaTermino) {
      setPreguntando(true);
      return;
    }

    void guardar(null);
  }

  async function guardar(termino: boolean | null) {
    if (insumo === null) {
      return;
    }

    try {
      await onGuardar({
        insumo_id: insumo.id,
        entregado_a: entregadoA.trim(),
        area,
        consumo: cantidad,
        termino,
      });
    } catch {
      // El panel ya avisó con un toast. Se cierra la pregunta pero NO se
      // limpia lo capturado: si el rechazo fue por existencia insuficiente,
      // basta con corregir el consumo y volver a enviar.
      setPreguntando(false);
      return;
    }

    setPreguntando(false);
    // El área se conserva: quien entrega suele registrar varias salidas
    // seguidas para la misma.
    setInsumo(null);
    setEntregadoA('');
    setConsumo('');
    setErrores({});
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(evento) => {
        evento.preventDefault();
        enviar();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <BuscadorInsumo
            valor={insumo}
            onElegir={(elegido) => {
              setInsumo(elegido);
              setErrores((previos) => ({ ...previos, insumo: undefined }));
            }}
            error={errores.insumo}
          />
        </div>

        <Input
          name="entregado_a"
          etiqueta={t('controlInsumos.entregadoA')}
          placeholder={t('controlInsumos.entregadoAPlaceholder')}
          value={entregadoA}
          maxLength={150}
          onChange={(evento) => setEntregadoA(evento.target.value)}
          error={errores.entregadoA}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="area-insumo" className="text-sm font-medium text-texto">
            {bilingue(t('controlInsumos.area'))}
          </label>
          <select
            id="area-insumo"
            value={area}
            onChange={(evento) => setArea(evento.target.value)}
            aria-invalid={errores.area ? true : undefined}
            className={CLASES_SELECT}
          >
            <option value="">{t('controlInsumos.areaPlaceholder')}</option>
            {areas.map((opcion) => (
              // El área es dato del backend: no se traduce.
              <option key={opcion.value} value={opcion.value}>
                {opcion.label}
              </option>
            ))}
          </select>
          {errores.area && (
            <p role="alert" className="text-sm text-error">
              {bilingue(errores.area)}
            </p>
          )}
        </div>

        <Input
          name="consumo"
          type="number"
          inputMode="numeric"
          min={1}
          step={1}
          etiqueta={t('controlInsumos.consumo')}
          ayuda={t('controlInsumos.consumoAyuda')}
          value={consumo}
          onChange={(evento) => setConsumo(evento.target.value)}
          error={errores.consumo}
        />
      </div>

      <div className="flex justify-end">
        <Button type="submit" cargando={guardando}>
          {bilingue(t('controlInsumos.registrar'))}
        </Button>
      </div>

      <ModalTermino
        abierto={preguntando}
        unidad={insumo?.unidad_medida ?? ''}
        consumo={Number.isInteger(cantidad) ? cantidad : 0}
        guardando={guardando}
        onResponder={(termino) => void guardar(termino)}
        onCancelar={() => setPreguntando(false)}
      />
    </form>
  );
}
