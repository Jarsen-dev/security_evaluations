'use client';

import { useEffect, useRef, useState } from 'react';

import { Combobox } from '@/components/ui/Combobox';
import { ErrorDeApi, buscarInsumosControl } from '@/lib/api';
import { unaLinea, useTraduccion } from '@/lib/i18n';
import type { InsumoParaControl } from '@/lib/types';

/** Mínimo del backend. Con una letra el desplegable barre el catálogo entero. */
const MINIMO = 2;

/** Lo que se espera a que deje de teclear antes de preguntar al servidor. */
const MS_DEBOUNCE = 350;

/**
 * Campo de insumo con búsqueda contra el catálogo.
 *
 * `ui/Combobox` pone el campo, el teclado y la accesibilidad, pero **no
 * filtra**: pinta las opciones que se le pasen. Lo que se añade aquí es la
 * búsqueda remota con debounce y un `AbortController` que cancela la petición
 * anterior en cada tecla, el mismo patrón que usa la pestaña de Stock.
 *
 * La lista sale ordenada del servidor: primero el código exacto, luego los que
 * empiezan por lo tecleado. Teclear un código repetido enseña juntas todas sus
 * descripciones, que es lo que hay que poder distinguir.
 */
export function BuscadorInsumo({
  valor,
  onElegir,
  error,
}: {
  valor: InsumoParaControl | null;
  /** `null` al borrar o cambiar el texto: lo elegido deja de ser válido. */
  onElegir: (insumo: InsumoParaControl | null) => void;
  error?: string;
}) {
  const t = useTraduccion();

  // `unaLinea` y no `t()` a secas: en coreano la traducción viaja con el
  // español pegado por un salto de línea, y aquí se incrusta a media plantilla
  // dentro de un renglón de la lista, que no admite el salto.
  const rotuloExistencia = unaLinea(t('controlInsumos.existencia'));

  const [texto, setTexto] = useState('');
  const [opciones, setOpciones] = useState<InsumoParaControl[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [falloBusqueda, setFalloBusqueda] = useState(false);

  const peticion = useRef<AbortController | null>(null);

  useEffect(() => {
    const consulta = texto.trim();

    if (consulta.length < MINIMO) {
      peticion.current?.abort();
      setOpciones([]);
      setBuscando(false);
      setFalloBusqueda(false);
      return;
    }

    setBuscando(true);
    const temporizador = setTimeout(() => {
      peticion.current?.abort();
      const control = new AbortController();
      peticion.current = control;

      buscarInsumosControl(consulta, control.signal)
        .then((encontrados) => {
          if (control.signal.aborted) {
            return;
          }
          setOpciones(encontrados);
          setFalloBusqueda(false);
        })
        .catch((error_: unknown) => {
          if (control.signal.aborted) {
            return;
          }
          setOpciones([]);
          setFalloBusqueda(error_ instanceof ErrorDeApi || error_ instanceof Error);
        })
        .finally(() => {
          if (!control.signal.aborted) {
            setBuscando(false);
          }
        });
    }, MS_DEBOUNCE);

    return () => clearTimeout(temporizador);
  }, [texto]);

  // Se cancela también al desmontar: cambiar de pestaña con una búsqueda en
  // vuelo dejaría el `setState` apuntando a un componente que ya no está.
  useEffect(() => () => peticion.current?.abort(), []);

  function alTeclear(nuevo: string) {
    setTexto(nuevo);
    // Lo elegido se suelta en cuanto el texto cambia. Sin esto, seguir
    // tecleando después de elegir dejaría el id anterior puesto y se
    // registraría un insumo distinto del que se lee en pantalla.
    if (valor !== null) {
      onElegir(null);
    }
  }

  function alElegir(id: string) {
    const elegido = opciones.find((insumo) => insumo.id === id) ?? null;
    if (elegido !== null) {
      setTexto(etiquetaDe(elegido, rotuloExistencia));
      onElegir(elegido);
    }
  }

  return (
    <Combobox
      etiqueta={t('controlInsumos.insumo')}
      placeholder={t('controlInsumos.insumoPlaceholder')}
      ayuda={t('controlInsumos.insumoAyuda')}
      error={error}
      opciones={opciones.map((insumo) => ({
        valor: insumo.id,
        etiqueta: etiquetaDe(insumo, rotuloExistencia),
      }))}
      valor={valor?.id ?? null}
      onElegir={alElegir}
      texto={texto}
      onTexto={alTeclear}
      // Sin esto, el hueco entre teclear y que llegue la respuesta diría "no
      // hay nada" cuando la verdad es que todavía está buscando.
      vacio={mensajeVacio()}
    />
  );

  function mensajeVacio(): string {
    if (texto.trim().length < MINIMO) {
      return t('controlInsumos.tecleaMas');
    }
    if (buscando) {
      return t('controlInsumos.buscando');
    }
    if (falloBusqueda) {
      return t('controlInsumos.falloBusqueda');
    }
    return t('controlInsumos.sinResultados');
  }
}

/**
 * Cómo se lee un insumo en la lista.
 *
 * El código y la descripción son dato del catálogo y no se traducen. La
 * existencia va rotulada y **sin la unidad de medida**: lo que el inventario
 * cuenta son piezas, así que un frasco de gel de 35 GR con tres frascos en
 * almacén se leería como "3 GR" —tres gramos— y es justo la confusión que este
 * control existe para no cometer.
 */
function etiquetaDe(insumo: InsumoParaControl, rotuloExistencia: string): string {
  return (
    `${insumo.codigo} · ${insumo.descripcion} — ` +
    `${rotuloExistencia}: ${insumo.existencia}`
  );
}
