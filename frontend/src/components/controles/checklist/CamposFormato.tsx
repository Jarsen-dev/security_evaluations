'use client';

import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { useIdioma } from '@/lib/i18n';
import type { CampoFormato } from '@/lib/types';
import { cn } from '@/lib/utils';

interface CamposFormatoProps {
  campos: CampoFormato[];
  valores: Record<string, string>;
  onCambiar: (clave: string, valor: string) => void;
  deshabilitado?: boolean;
  /** Prefijo de los `id`, para que dos bloques no colisionen. */
  prefijo: string;
}

/**
 * Dibuja un grupo de campos del formato a partir del catálogo.
 *
 * Lo usan el encabezado de la hoja y cada uno de sus bloques del pie; qué
 * campos existen, de qué tipo son y cuáles son obligatorios lo decide el
 * backend, nunca este componente.
 */
export function CamposFormato({
  campos,
  valores,
  onCambiar,
  deshabilitado,
  prefijo,
}: CamposFormatoProps) {
  const { t, idioma } = useIdioma();

  /** El formato es bilingüe: se muestra la línea del idioma del panel. */
  function etiqueta(campo: CampoFormato): string {
    return idioma === 'ko' && campo.etiqueta_ko ? campo.etiqueta_ko : campo.etiqueta;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {campos.map((campo) => {
        const id = `${prefijo}-${campo.clave}`;
        const valor = valores[campo.clave] ?? '';
        const falta = campo.obligatorio && valor.trim() === '';

        if (campo.tipo === 'texto_largo') {
          return (
            <div key={campo.clave} className="sm:col-span-2 lg:col-span-3">
              <Textarea
                etiqueta={etiqueta(campo)}
                name={id}
                value={valor}
                onChange={(evento) => onCambiar(campo.clave, evento.target.value)}
                disabled={deshabilitado}
                maxLength={2000}
              />
            </div>
          );
        }

        if (campo.tipo === 'opcion') {
          return (
            <div key={campo.clave} className="flex flex-col gap-1.5">
              <span className="text-sm font-medium text-texto">{etiqueta(campo)}</span>
              <div role="radiogroup" aria-label={etiqueta(campo)} className="flex gap-2">
                {campo.opciones.map((opcion) => {
                  const activa = valor === opcion;

                  return (
                    <button
                      key={opcion}
                      type="button"
                      role="radio"
                      aria-checked={activa}
                      onClick={() => onCambiar(campo.clave, activa ? '' : opcion)}
                      disabled={deshabilitado}
                      className={cn(
                        'h-10 flex-1 rounded-md border px-3 text-sm font-medium transition-colors',
                        'disabled:cursor-not-allowed disabled:opacity-50',
                        activa
                          ? 'border-primario bg-primario-suave text-primario'
                          : 'border-borde text-texto-suave hover:border-borde-fuerte hover:text-texto',
                      )}
                    >
                      {opcion}
                    </button>
                  );
                })}
              </div>
              {falta && <p className="text-sm text-texto-tenue">{t('comun.obligatorio')}</p>}
            </div>
          );
        }

        return (
          <Input
            key={campo.clave}
            etiqueta={
              campo.unidad ? `${etiqueta(campo)} (${campo.unidad})` : etiqueta(campo)
            }
            name={id}
            // `time` da el selector de hora del celular; `decimal` el teclado
            // numérico con punto.
            type={campo.tipo === 'hora' ? 'time' : 'text'}
            inputMode={campo.tipo === 'numero' ? 'decimal' : undefined}
            value={valor}
            onChange={(evento) => onCambiar(campo.clave, evento.target.value)}
            disabled={deshabilitado}
            maxLength={150}
          />
        );
      })}
    </div>
  );
}
